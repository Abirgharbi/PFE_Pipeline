"""Service module: thin GitHub REST API client used by the ingestion stage.

Role in the pipeline
---------------------
`GitHubService` wraps `requests` with retry/backoff, pagination, and rate
limiting, and exposes higher-level fetch methods used by
`fetch_issues.py`, `fetch_prs.py` and `fetch_commits.py` to build the raw
JSON artifacts under `data/`.

Inputs
------
- GitHub REST API v3 (`https://api.github.com`), authenticated via a
  personal access token read from an environment variable (default
  `GITHUB_TOKEN`, configurable via the `token_env` constructor argument).

Outputs
-------
- Python dicts/lists representing issues, comments, pull requests, PR files,
  and commits. This module does not write any files itself; callers persist
  the results.

This module has no CLI entry point; it is imported, not run directly.
"""

import os
import re
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class GitHubService:
    """Minimal GitHub REST API client for the STM32Cube ingestion pipeline.

    Handles authentication, HTTP retries (via `urllib3.Retry`), pagination,
    and configurable inter-request sleeps to stay under GitHub's rate limits.
    """

    def __init__(
        self,
        owner: str,
        token_env: str | None = "GITHUB_TOKEN",
        issues_sleep: float = 0.2,
        comments_sleep: float = 0.1,
        prs_sleep: float = 0.2,
        pr_details_sleep: float = 0.1,
        commits_sleep: float = 0.1,
        request_timeout: float = 30.0,
        max_request_attempts: int = 3,
    ) -> None:
        """Configure the client and its underlying `requests.Session`.

        Args:
            owner: GitHub organization/user that owns the target repos.
            token_env: Name of the environment variable holding the GitHub
                token. If unset/None, requests are made unauthenticated
                (much lower rate limits).
            issues_sleep: Delay (seconds) between issue list pages.
            comments_sleep: Delay between issue comments pages.
            prs_sleep: Delay between pull request list pages.
            pr_details_sleep: Delay between PR detail/files/commits requests.
            commits_sleep: Delay between commit detail requests.
            request_timeout: Per-request timeout in seconds.
            max_request_attempts: Max attempts for `_safe_get` before giving up
                on transient network errors (separate from the HTTP-level
                `Retry` adapter, which handles 429/5xx responses).
        """
        self.owner = owner
        self.issues_sleep = issues_sleep
        self.comments_sleep = comments_sleep
        self.prs_sleep = prs_sleep
        self.pr_details_sleep = pr_details_sleep
        self.commits_sleep = commits_sleep
        self.request_timeout = request_timeout
        self.max_request_attempts = max_request_attempts

        token = os.environ.get(token_env) if token_env else None

        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)

        retry_cfg = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry_cfg)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _safe_get(self, url: str, params: dict[str, Any], context: str) -> requests.Response | None:
        """Perform a GET request with manual retries for transient network errors.

        This is a second layer of resilience on top of the `Retry` adapter
        (which only kicks in for actual HTTP responses like 429/5xx); this
        catches lower-level exceptions such as connection resets/timeouts.

        Args:
            url: Target URL.
            params: Query parameters.
            context: Human-readable description used in log messages.

        Returns:
            The `requests.Response`, or None if all attempts failed.
        """
        for attempt in range(1, self.max_request_attempts + 1):
            try:
                return self.session.get(url, params=params, timeout=self.request_timeout)
            except requests.exceptions.RequestException as exc:
                print(f"  [WARN] {context} failed (attempt {attempt}/{self.max_request_attempts}): {exc}")
                if attempt == self.max_request_attempts:
                    print(f"  [ERROR] {context} failed after retries.")
                    return None
                # Linear backoff: wait longer on each subsequent attempt.
                time.sleep(1.5 * attempt)

    def _extract_issue_numbers(self, *texts: str | None) -> list[int]:
        """Extract issue numbers referenced in free-form text (PR/commit bodies).

        Scans for several common GitHub referencing conventions: bare "#123",
        "issues/123" or "issue/123" URLs, "issue #123" wording, and resolver
        verbs like "fixes #123" / "closes #123".

        Args:
            *texts: Any number of text fragments to scan (e.g. title and body).

        Returns:
            A de-duplicated list of issue numbers, in first-seen order.
        """
        issue_numbers: list[int] = []
        seen: set[int] = set()

        patterns = [
            r"#(\d+)",
            r"(?:issues|issue)/(\d+)",
            r"\bissue\s*#?\s*(\d+)\b",
            r"\b(?:fixe[sd]?|close[sd]?|resolve[sd]?)\s*:?\s*#?(\d+)\b",
        ]

        for text in texts:
            if not text:
                continue
            for pattern in patterns:
                for match in re.findall(pattern, text, flags=re.IGNORECASE):
                    issue_number = int(match)
                    if issue_number in seen:
                        continue
                    seen.add(issue_number)
                    issue_numbers.append(issue_number)

        return issue_numbers

    def fetch_all_issues(self, repo: str) -> list[dict[str, Any]]:
        """Fetch all issues (all states) for a repo, including their comments.

        Note: GitHub's `/issues` endpoint also returns pull requests; entries
        containing a `pull_request` key are skipped since PRs are fetched
        separately via `fetch_all_pull_requests`.

        Args:
            repo: Repository name (without owner).

        Returns:
            A list of issue dicts with title, state, labels, timestamps, body,
            comments, and the GitHub URL.
        """
        issues: list[dict[str, Any]] = []
        page = 1

        while True:
            url = f"https://api.github.com/repos/{self.owner}/{repo}/issues"
            params = {
                "state": "all",
                "per_page": 100,
                "page": page,
            }
            print(f"[{repo}] Fetch issues page {page} ...")
            resp = self._safe_get(url, params, context=f"fetch issues page {page} for {repo}")
            if resp is None:
                break
            if resp.status_code != 200:
                print(f"  HTTP error {resp.status_code}: {resp.text}")
                break

            data = resp.json()
            if not data:
                # Empty page means we've paginated past the last page.
                break

            for item in data:
                if "pull_request" in item:
                    # Skip PRs surfaced by the issues endpoint; handled separately.
                    continue

                issue_number = item["number"]
                comments_url = item["comments_url"]
                comments = self.fetch_comments(repo, issue_number, comments_url)

                issues.append(
                    {
                        "repo": repo,
                        "issue_number": issue_number,
                        "title": item.get("title") or "",
                        "state": item.get("state"),
                        "labels": [lbl["name"] for lbl in item.get("labels", [])],
                        "created_at": item.get("created_at"),
                        "closed_at": item.get("closed_at"),
                        "body": item.get("body") or "",
                        "comments": comments,
                        "github_url": item.get("html_url"),
                    }
                )

            page += 1
            time.sleep(self.issues_sleep)

        return issues

    def fetch_comments(
        self,
        repo: str,
        issue_number: int,
        comments_url: str,
    ) -> list[dict[str, Any]]:
        """Fetch all comments for a single issue, following pagination.

        Args:
            repo: Repository name (used for logging only).
            issue_number: Issue number (used for logging only).
            comments_url: The `comments_url` field from the issue payload.

        Returns:
            A list of comment dicts (author, created_at, body).
        """
        comments: list[dict[str, Any]] = []
        page = 1

        while True:
            params = {"per_page": 100, "page": page}
            print(f"    [{repo} #{issue_number}] Fetch comments page {page} ...")
            resp = self._safe_get(
                comments_url,
                params,
                context=f"fetch comments page {page} for {repo} #{issue_number}",
            )
            if resp is None:
                break
            if resp.status_code != 200:
                print(f"      HTTP error {resp.status_code} on comments: {resp.text}")
                break

            data = resp.json()
            if not data:
                break

            for c in data:
                comments.append(
                    {
                        "author": (c.get("user") or {}).get("login"),
                        "created_at": c.get("created_at"),
                        "body": c.get("body") or "",
                    }
                )

            page += 1
            time.sleep(self.comments_sleep)

        return comments

    def fetch_all_pull_requests(self, repo: str) -> list[dict[str, Any]]:
        """Fetch all pull requests (all states) for a repo, with full detail.

        For each PR summary returned by the list endpoint, fetches the full
        detail (including linked issues and changed files) via
        `fetch_pull_request_detail`.

        Args:
            repo: Repository name (without owner).

        Returns:
            A list of enriched PR detail dicts.
        """
        pull_requests: list[dict[str, Any]] = []
        page = 1

        while True:
            url = f"https://api.github.com/repos/{self.owner}/{repo}/pulls"
            params = {
                "state": "all",
                "per_page": 100,
                "page": page,
            }
            print(f"[{repo}] Fetch pull requests page {page} ...")
            resp = self._safe_get(url, params, context=f"fetch pull requests page {page} for {repo}")
            if resp is None:
                break
            if resp.status_code != 200:
                print(f"  HTTP error {resp.status_code} on pull requests: {resp.text}")
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                pr_number = item["number"]
                detail = self.fetch_pull_request_detail(repo, pr_number)
                if detail is None:
                    continue
                pull_requests.append(detail)

            page += 1
            time.sleep(self.prs_sleep)

        return pull_requests

    def fetch_pull_request_detail(self, repo: str, pr_number: int) -> dict[str, Any] | None:
        """Fetch full detail for one pull request, including its changed files.

        Args:
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            A dict with PR metadata (state, merge info, refs, counts) plus
            `linked_issue_numbers` (parsed from title/body) and
            `files_changed`; or None if the request failed.
        """
        url = f"https://api.github.com/repos/{self.owner}/{repo}/pulls/{pr_number}"
        resp = self._safe_get(url, {}, context=f"fetch pull request #{pr_number} for {repo}")
        if resp is None:
            return None
        if resp.status_code != 200:
            print(f"  HTTP error {resp.status_code} on pull request #{pr_number}: {resp.text}")
            return None

        item = resp.json()
        files_changed = self.fetch_pull_request_files(repo, pr_number)
        linked_issue_numbers = self._extract_issue_numbers(item.get("title"), item.get("body"))

        time.sleep(self.pr_details_sleep)

        return {
            "repo": repo,
            "pr_number": pr_number,
            "title": item.get("title") or "",
            "state": item.get("state"),
            "merged": bool(item.get("merged")),
            "draft": bool(item.get("draft")),
            "author": (item.get("user") or {}).get("login"),
            "labels": [lbl["name"] for lbl in item.get("labels", [])],
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "closed_at": item.get("closed_at"),
            "merged_at": item.get("merged_at"),
            "body": item.get("body") or "",
            "github_url": item.get("html_url"),
            "head_ref": ((item.get("head") or {}).get("ref")),
            "base_ref": ((item.get("base") or {}).get("ref")),
            "merge_commit_sha": item.get("merge_commit_sha"),
            "commits_count": item.get("commits", 0),
            "review_comments_count": item.get("review_comments", 0),
            "comments_count": item.get("comments", 0),
            "changed_files_count": item.get("changed_files", 0),
            "additions": item.get("additions", 0),
            "deletions": item.get("deletions", 0),
            "linked_issue_numbers": linked_issue_numbers,
            "files_changed": files_changed,
        }

    def fetch_pull_request_files(self, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch the list of files changed by a pull request, following pagination.

        Args:
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            A list of dicts describing each changed file (filename, status,
            additions/deletions/changes, blob/raw URLs).
        """
        files_changed: list[dict[str, Any]] = []
        page = 1

        while True:
            url = f"https://api.github.com/repos/{self.owner}/{repo}/pulls/{pr_number}/files"
            params = {"per_page": 100, "page": page}
            print(f"    [{repo} PR #{pr_number}] Fetch files page {page} ...")
            resp = self._safe_get(
                url,
                params,
                context=f"fetch pull request files page {page} for {repo} #{pr_number}",
            )
            if resp is None:
                break
            if resp.status_code != 200:
                print(f"      HTTP error {resp.status_code} on pull request files: {resp.text}")
                break

            data = resp.json()
            if not data:
                break

            for item in data:
                files_changed.append(
                    {
                        "filename": item.get("filename"),
                        "status": item.get("status"),
                        "additions": item.get("additions", 0),
                        "deletions": item.get("deletions", 0),
                        "changes": item.get("changes", 0),
                        "previous_filename": item.get("previous_filename"),
                        "blob_url": item.get("blob_url"),
                        "raw_url": item.get("raw_url"),
                    }
                )

            page += 1
            time.sleep(self.pr_details_sleep)

        return files_changed

    def fetch_pull_request_commits(self, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Fetch the raw commit summaries associated with a pull request.

        Note: this returns the GitHub API's summary payload as-is (not the
        normalized shape used elsewhere); full detail is resolved separately
        by `fetch_commit_detail` in `fetch_commits_for_pull_requests`.

        Args:
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            A list of raw commit summary dicts from the GitHub API.
        """
        commits: list[dict[str, Any]] = []
        page = 1

        while True:
            url = f"https://api.github.com/repos/{self.owner}/{repo}/pulls/{pr_number}/commits"
            params = {"per_page": 100, "page": page}
            print(f"    [{repo} PR #{pr_number}] Fetch commits page {page} ...")
            resp = self._safe_get(
                url,
                params,
                context=f"fetch pull request commits page {page} for {repo} #{pr_number}",
            )
            if resp is None:
                break
            if resp.status_code != 200:
                print(f"      HTTP error {resp.status_code} on pull request commits: {resp.text}")
                break

            data = resp.json()
            if not data:
                break

            commits.extend(data)
            page += 1
            time.sleep(self.commits_sleep)

        return commits

    def fetch_commit_detail(self, repo: str, sha: str) -> dict[str, Any] | None:
        """Fetch full detail for a single commit by SHA.

        Args:
            repo: Repository name.
            sha: Commit SHA.

        Returns:
            A normalized commit dict (author, committer, message, timestamps,
            stats, files_changed with per-file patches, and
            `linked_issue_numbers` parsed from the commit message); or None
            if the request failed.
        """
        url = f"https://api.github.com/repos/{self.owner}/{repo}/commits/{sha}"
        resp = self._safe_get(url, {}, context=f"fetch commit {sha} for {repo}")
        if resp is None:
            return None
        if resp.status_code != 200:
            print(f"  HTTP error {resp.status_code} on commit {sha}: {resp.text}")
            return None

        item = resp.json()
        commit_info = item.get("commit") or {}
        files = item.get("files") or []

        return {
            "repo": repo,
            "sha": item.get("sha"),
            "author": ((item.get("author") or {}).get("login")) or ((commit_info.get("author") or {}).get("name")),
            "committer": ((item.get("committer") or {}).get("login")) or ((commit_info.get("committer") or {}).get("name")),
            "message": commit_info.get("message") or "",
            "authored_at": (commit_info.get("author") or {}).get("date"),
            "committed_at": (commit_info.get("committer") or {}).get("date"),
            "github_url": item.get("html_url"),
            "parents": [parent.get("sha") for parent in item.get("parents", []) if parent.get("sha")],
            "stats": {
                "additions": (item.get("stats") or {}).get("additions", 0),
                "deletions": (item.get("stats") or {}).get("deletions", 0),
                "total": (item.get("stats") or {}).get("total", 0),
            },
            "files_changed": [
                {
                    "filename": file_item.get("filename"),
                    "status": file_item.get("status"),
                    "additions": file_item.get("additions", 0),
                    "deletions": file_item.get("deletions", 0),
                    "changes": file_item.get("changes", 0),
                    "previous_filename": file_item.get("previous_filename"),
                    "patch": file_item.get("patch"),
                }
                for file_item in files
            ],
            "linked_issue_numbers": self._extract_issue_numbers(commit_info.get("message")),
        }

    def fetch_commits_for_pull_requests(
        self,
        repo: str,
        pull_requests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Resolve and de-duplicate full commit details for a set of pull requests.

        Iterates over each PR's commits (via `fetch_pull_request_commits`) and
        fetches full detail once per unique SHA (via `fetch_commit_detail`),
        since the same commit can be shared across multiple PRs (e.g. after a
        rebase). Each resulting commit record aggregates the set of PR numbers
        and linked issue numbers across all PRs it belongs to.

        Args:
            repo: Repository name.
            pull_requests: PR detail dicts (as returned by
                `fetch_pull_request_detail`), used for their `pr_number` and
                `linked_issue_numbers`.

        Returns:
            A de-duplicated list of commit dicts, sorted by committed date
            then SHA.
        """
        commits_by_sha: dict[str, dict[str, Any]] = {}

        for pull_request in pull_requests:
            pr_number = pull_request.get("pr_number")
            if pr_number is None:
                continue

            linked_issue_numbers = [int(num) for num in pull_request.get("linked_issue_numbers") or []]
            commit_summaries = self.fetch_pull_request_commits(repo, pr_number)

            for summary in commit_summaries:
                sha = summary.get("sha")
                if not sha:
                    continue

                if sha not in commits_by_sha:
                    # Only fetch full commit detail once per unique SHA (expensive call).
                    detail = self.fetch_commit_detail(repo, sha)
                    if detail is None:
                        continue
                    detail["pr_numbers"] = []
                    commits_by_sha[sha] = detail

                record = commits_by_sha[sha]
                pr_numbers = set(record.get("pr_numbers") or [])
                pr_numbers.add(pr_number)
                record["pr_numbers"] = sorted(pr_numbers)

                issue_numbers = set(record.get("linked_issue_numbers") or [])
                issue_numbers.update(linked_issue_numbers)
                record["linked_issue_numbers"] = sorted(issue_numbers)

                time.sleep(self.commits_sleep)

        commits = list(commits_by_sha.values())
        commits.sort(key=lambda item: ((item.get("committed_at") or ""), item.get("sha") or ""))
        return commits
