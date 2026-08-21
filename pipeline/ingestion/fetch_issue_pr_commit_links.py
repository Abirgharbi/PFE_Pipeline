"""Ingestion stage: build issue <-> pull request <-> commit linkage records.

Role in the pipeline
---------------------
This script cross-references the three raw artifacts produced earlier in
`pipeline/ingestion` (issues, pull requests, commits) to compute, per issue,
a resolution-status heuristic ("was this issue actually fixed, and how
confidently do we know?"). This linkage is a key evidence signal consumed by
later enrichment/delivery stages (e.g. diagnostic cards, resolver cases) that
need to say "this issue was resolved by PR #123 / commit abc123".

Inputs
------
- Config: resolved via `shared.utils.paths.get_config_path()` (default
  `shared/config/config_all_series.json`, overridable with `STM32CUBE_CONFIG`).
  Uses `repos`.
- `data/raw_issues_<repo>.json` (from `fetch_issues.py`)
- `data/raw_prs_<repo>.json` (from `fetch_prs.py`)
- `data/raw_commits_<repo>.json` (from `fetch_commits.py`)

Outputs (per repo, under `data/`)
---------------------------------
- `issue_pr_commit_links_<repo>.json`: full linkage records for every issue
  (including unlinked ones), each with evidence, `link_score`,
  `link_confidence` and `resolution_status`.
- `issue_pr_commit_links_<repo>_linked_only.json`: subset with `link_score > 0`.
- `issue_pr_commit_links_<repo>_summary.json`: aggregate counts (link rate,
  resolution-status breakdown, top linked issues) for quick QA.

How to run
----------
No CLI arguments; run as a module:
`python -m pipeline.ingestion.fetch_issue_pr_commit_links`.
Requires the three raw JSON inputs above to already exist for each repo
(missing/unparseable files are treated as empty lists, not fatal errors).
"""

import json
import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any

from shared.utils.paths import DATA_DIR, get_config_path


# Generic verbs/keywords ('fix', 'closes', 'issue', ...) that indicate a commit
# message is *talking about* an issue, as opposed to an incidental "#123".
COMMIT_ISSUE_SIGNAL_RE = re.compile(
    r"\b(fix(?:e[sd])?|close[sd]?|resolve[sd]?|reference[sd]?|refs?|issue[s]?)\b",
    re.IGNORECASE,
)
# Bare '#123' style reference (weak signal on its own — see extract_issue_numbers_from_commit_message).
COMMIT_ISSUE_NUMBER_RE = re.compile(r"#(\d+)")
# Explicit "issue 123" / "issue #123" wording (strong signal).
COMMIT_ISSUE_WORD_NUMBER_RE = re.compile(r"\bissue[s]?\s*#?(\d+)\b", re.IGNORECASE)
# Full GitHub issue URL (strong signal).
COMMIT_ISSUE_URL_RE = re.compile(r"/issues/(\d+)\b", re.IGNORECASE)


def load_config() -> dict:
    """Load and parse the active pipeline configuration JSON file.

    Returns:
        The parsed configuration as a dict.
    """
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def load_json_array(path) -> list[dict[str, Any]]:
    """Load a JSON file expected to contain a top-level array.

    Missing files, unparseable JSON, or a non-list payload are all treated as
    "no data yet" rather than raised as errors, since upstream ingestion
    stages may not have produced every artifact for every repo.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed list, or an empty list if unavailable/invalid.
    """
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return payload
    return []


def is_merge_like_commit(commit: dict[str, Any]) -> bool:
    """Detect auto-generated merge commits ("Merge branch"/"Merge pull request").

    These commits carry no meaningful code evidence on their own and are
    excluded from the "meaningful commit" counts used for confidence scoring.

    Args:
        commit: A commit record with a `message` field.

    Returns:
        True if the commit message looks like an automatic merge commit.
    """
    message = (commit.get("message") or "").strip().lower()
    return message.startswith("merge branch") or message.startswith("merge pull request")


def extract_issue_numbers_from_commit_message(message: str | None) -> list[int]:
    """Extract issue references from commit text for commit-only linkage fallback."""
    text = (message or "").strip()
    if not text:
        return []

    has_signal = bool(COMMIT_ISSUE_SIGNAL_RE.search(text))
    has_issue_context = bool(COMMIT_ISSUE_WORD_NUMBER_RE.search(text) or COMMIT_ISSUE_URL_RE.search(text))

    out: list[int] = []
    seen: set[int] = set()

    # Explicit "issue <id>" or issue URLs are strong anchors even without fix/close verbs.
    for regex in (COMMIT_ISSUE_WORD_NUMBER_RE, COMMIT_ISSUE_URL_RE, COMMIT_ISSUE_NUMBER_RE):
        for match in regex.findall(text):
            value = int(match)
            if value <= 0 or value in seen:
                continue
            seen.add(value)
            out.append(value)

    # Guardrail: bare "#123" without resolver verbs or issue context is often PR noise.
    if out and not has_signal and not has_issue_context:
        return []

    return out


def score_and_confidence(
    explicit_pr_count: int,
    merged_pr_count: int,
    meaningful_commit_count: int,
    merged_pr_with_file_evidence: bool,
) -> tuple[float, str]:
    """Compute a heuristic link score (0-1) and a discrete confidence label.

    The score is a weighted combination of independent evidence signals
    (explicit PR link, merged PR, meaningful commits, commit-only linkage,
    file-changed evidence on merge-heavy PRs) rather than a single boolean,
    so partial/weak evidence still produces a meaningful ranking.

    Args:
        explicit_pr_count: Number of PRs that explicitly reference the issue.
        merged_pr_count: Number of those PRs that were merged.
        meaningful_commit_count: Number of non-merge commits linked to the issue.
        merged_pr_with_file_evidence: Whether at least one merged PR actually
            changed files (guards against merge-only PRs with no real diff).

    Returns:
        A tuple of (score in [0, 1], confidence label in
        {"high", "medium", "low", "none"}).
    """
    score = 0.0
    if explicit_pr_count > 0:
        score += 0.5
    if merged_pr_count > 0:
        score += 0.3
    elif explicit_pr_count > 0:
        score += 0.1
    if meaningful_commit_count > 0:
        score += 0.2

    # Commit-only linkage is weaker than PR linkage but better than unlinked.
    if explicit_pr_count == 0 and meaningful_commit_count > 0:
        score += 0.15

    # Prevent merge-heavy PR histories from being under-scored when files changed.
    if merged_pr_count > 0 and merged_pr_with_file_evidence and meaningful_commit_count == 0:
        score += 0.08

    score = min(score, 1.0)

    if score >= 0.9:
        confidence = "high"
    elif score >= 0.5:
        confidence = "medium"
    elif score > 0.0:
        confidence = "low"
    else:
        confidence = "none"
    return score, confidence


def derive_resolution_status(
    explicit_pr_count: int,
    merged_pr_count: int,
    meaningful_commit_count: int,
    merged_pr_with_file_evidence: bool,
) -> str:
    """Classify an issue's resolution status from its linkage evidence.

    Args:
        explicit_pr_count: Number of PRs that explicitly reference the issue.
        merged_pr_count: Number of those PRs that were merged.
        meaningful_commit_count: Number of non-merge commits linked to the issue.
        merged_pr_with_file_evidence: Whether a merged PR actually changed files.

    Returns:
        One of "merged_fix", "candidate_fix", "commit_only_candidate",
        "reference_only", or "unlinked", ordered from strongest to weakest evidence.
    """
    if merged_pr_count > 0 and (meaningful_commit_count > 0 or merged_pr_with_file_evidence):
        return "merged_fix"
    if explicit_pr_count > 0 and meaningful_commit_count > 0:
        return "candidate_fix"
    if meaningful_commit_count > 0:
        return "commit_only_candidate"
    if explicit_pr_count > 0:
        return "reference_only"
    return "unlinked"


def build_links_for_repo(
    repo: str,
    issues: list[dict[str, Any]],
    pull_requests: list[dict[str, Any]],
    commits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one linkage record per issue, cross-referencing PRs and commits.

    For each issue this resolves: PRs that explicitly mention it, commits
    explicitly linked to it (via PR body or commit message), commits inferred
    from message text, and commits reachable transitively through its linked
    PRs. It then scores the overall link strength via `score_and_confidence`
    and `derive_resolution_status`.

    Args:
        repo: Repository name (used to tag each output record).
        issues: Raw issue records (from `raw_issues_<repo>.json`).
        pull_requests: Raw PR records (from `raw_prs_<repo>.json`).
        commits: Raw commit records (from `raw_commits_<repo>.json`).

    Returns:
        A list of linkage records, one per issue with a valid `issue_number`,
        sorted by issue number.
    """
    pr_by_issue: dict[int, list[dict[str, Any]]] = defaultdict(list)
    pr_by_number: dict[int, dict[str, Any]] = {}

    for pull_request in pull_requests:
        pr_number = pull_request.get("pr_number")
        if not isinstance(pr_number, int):
            continue
        pr_by_number[pr_number] = pull_request
        for issue_number in pull_request.get("linked_issue_numbers") or []:
            if isinstance(issue_number, int):
                pr_by_issue[issue_number].append(pull_request)

    commit_by_issue_explicit: dict[int, list[dict[str, Any]]] = defaultdict(list)
    commit_by_issue_message: dict[int, list[dict[str, Any]]] = defaultdict(list)
    commits_by_pr: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for commit in commits:
        explicit_issue_numbers = [num for num in (commit.get("linked_issue_numbers") or []) if isinstance(num, int)]
        inferred_issue_numbers = extract_issue_numbers_from_commit_message(commit.get("message"))

        explicit_set = set(explicit_issue_numbers)
        for issue_number in explicit_issue_numbers:
            commit_by_issue_explicit[issue_number].append(commit)
        for issue_number in inferred_issue_numbers:
            if issue_number in explicit_set:
                continue
            commit_by_issue_message[issue_number].append(commit)

        for pr_number in commit.get("pr_numbers") or []:
            if isinstance(pr_number, int):
                commits_by_pr[pr_number].append(commit)

    links: list[dict[str, Any]] = []
    for issue in issues:
        issue_number = issue.get("issue_number")
        if not isinstance(issue_number, int):
            continue

        explicit_prs = pr_by_issue.get(issue_number, [])
        explicit_pr_numbers = sorted(
            [pr["pr_number"] for pr in explicit_prs if isinstance(pr.get("pr_number"), int)]
        )

        explicit_commits = commit_by_issue_explicit.get(issue_number, [])
        message_inferred_commits = commit_by_issue_message.get(issue_number, [])
        explicit_commit_shas = sorted(
            [c["sha"] for c in explicit_commits if isinstance(c.get("sha"), str)]
        )
        message_inferred_commit_shas = sorted(
            [c["sha"] for c in message_inferred_commits if isinstance(c.get("sha"), str)]
        )

        pr_linked_commit_shas: set[str] = set()
        for pr_number in explicit_pr_numbers:
            for commit in commits_by_pr.get(pr_number, []):
                sha = commit.get("sha")
                if isinstance(sha, str):
                    pr_linked_commit_shas.add(sha)

        all_commit_shas = sorted(set(explicit_commit_shas) | set(message_inferred_commit_shas) | pr_linked_commit_shas)
        linked_prs = [pr_by_number[pn] for pn in explicit_pr_numbers if pn in pr_by_number]
        all_linked_commits: list[dict[str, Any]] = []
        commit_by_sha = {c.get("sha"): c for c in commits if isinstance(c.get("sha"), str)}
        for sha in all_commit_shas:
            commit_item = commit_by_sha.get(sha)
            if not commit_item:
                continue
            all_linked_commits.append(commit_item)

        merge_like_commits = [c for c in all_linked_commits if is_merge_like_commit(c)]
        linked_commits = [c for c in all_linked_commits if not is_merge_like_commit(c)]
        linked_commit_shas = sorted(
            [c["sha"] for c in linked_commits if isinstance(c.get("sha"), str)]
        )
        merge_like_commit_shas = sorted(
            [c["sha"] for c in merge_like_commits if isinstance(c.get("sha"), str)]
        )

        merged_prs = [pr for pr in linked_prs if pr.get("merged")]
        merged_pr_count = len(merged_prs)
        merged_pr_with_file_evidence_pr_numbers = sorted(
            [
                int(pr.get("pr_number"))
                for pr in merged_prs
                if isinstance(pr.get("pr_number"), int) and int(pr.get("changed_files_count") or 0) > 0
            ]
        )
        merged_pr_with_file_evidence = bool(merged_pr_with_file_evidence_pr_numbers)
        merged_pr_changed_files_total = sum(int(pr.get("changed_files_count") or 0) for pr in merged_prs)

        score, confidence = score_and_confidence(
            explicit_pr_count=len(explicit_pr_numbers),
            merged_pr_count=merged_pr_count,
            meaningful_commit_count=len(linked_commit_shas),
            merged_pr_with_file_evidence=merged_pr_with_file_evidence,
        )
        resolution_status = derive_resolution_status(
            explicit_pr_count=len(explicit_pr_numbers),
            merged_pr_count=merged_pr_count,
            meaningful_commit_count=len(linked_commit_shas),
            merged_pr_with_file_evidence=merged_pr_with_file_evidence,
        )

        links.append(
            {
                "repo": repo,
                "issue_number": issue_number,
                "issue_title": issue.get("title") or "",
                "issue_labels": issue.get("labels") or [],
                "issue_state": issue.get("state"),
                "issue_url": issue.get("github_url"),
                "linked_pr_numbers": explicit_pr_numbers,
                "linked_commit_shas": linked_commit_shas,
                "linked_prs": [
                    {
                        "pr_number": pr.get("pr_number"),
                        "title": pr.get("title") or "",
                        "state": pr.get("state"),
                        "merged": bool(pr.get("merged")),
                        "github_url": pr.get("github_url"),
                        "changed_files_count": pr.get("changed_files_count", 0),
                        "merge_commit_sha": pr.get("merge_commit_sha"),
                    }
                    for pr in linked_prs
                ],
                "linked_commits": [
                    {
                        "sha": c.get("sha"),
                        "message": c.get("message") or "",
                        "committed_at": c.get("committed_at"),
                        "github_url": c.get("github_url"),
                        "pr_numbers": c.get("pr_numbers") or [],
                        "stats": c.get("stats") or {},
                    }
                    for c in linked_commits
                ],
                "evidence": {
                    "explicit_pr_numbers": explicit_pr_numbers,
                    "explicit_commit_shas": explicit_commit_shas,
                    "message_inferred_commit_shas": message_inferred_commit_shas,
                    "commits_via_linked_prs": sorted(pr_linked_commit_shas),
                    "merge_like_commit_shas": merge_like_commit_shas,
                    "merged_pr_count": merged_pr_count,
                    "merged_pr_with_file_evidence": merged_pr_with_file_evidence,
                    "merged_pr_with_file_evidence_pr_numbers": merged_pr_with_file_evidence_pr_numbers,
                    "merged_pr_changed_files_total": merged_pr_changed_files_total,
                },
                "merged_pr_with_file_evidence": merged_pr_with_file_evidence,
                "link_score": round(score, 2),
                "link_confidence": confidence,
                "resolution_status": resolution_status,
            }
        )

    links.sort(key=lambda item: item.get("issue_number") or 0)
    return links


def main() -> None:
    """Entry point: build and write issue/PR/commit linkage artifacts per repo.

    For each configured repo, loads the three raw JSON inputs (issues, PRs,
    commits), computes linkage records via `build_links_for_repo`, and writes
    the full, linked-only, and summary JSON files under `DATA_DIR`.
    """
    cfg = load_config()
    repos = cfg.get("repos", [])
    data_dir = DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        repo_slug = repo.lower()
        issues_path = data_dir / f"raw_issues_{repo_slug}.json"
        prs_path = data_dir / f"raw_prs_{repo_slug}.json"
        commits_path = data_dir / f"raw_commits_{repo_slug}.json"

        issues = load_json_array(issues_path)
        pull_requests = load_json_array(prs_path)
        commits = load_json_array(commits_path)

        links = build_links_for_repo(repo, issues, pull_requests, commits)
        out_file = data_dir / f"issue_pr_commit_links_{repo_slug}.json"
        out_file.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

        linked_only = [item for item in links if item.get("link_score", 0) > 0]
        linked_only_file = data_dir / f"issue_pr_commit_links_{repo_slug}_linked_only.json"
        linked_only_file.write_text(
            json.dumps(linked_only, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        summary = {
            "repo": repo,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "issues_total": len(links),
            "linked_issues": len(linked_only),
            "unlinked_issues": len(links) - len(linked_only),
            "link_rate": round((len(linked_only) / len(links)) if links else 0.0, 4),
            "resolution_status_counts": {
                "merged_fix": len([x for x in linked_only if x.get("resolution_status") == "merged_fix"]),
                "candidate_fix": len([x for x in linked_only if x.get("resolution_status") == "candidate_fix"]),
                "commit_only_candidate": len(
                    [x for x in linked_only if x.get("resolution_status") == "commit_only_candidate"]
                ),
                "reference_only": len([x for x in linked_only if x.get("resolution_status") == "reference_only"]),
            },
            "merged_pr_with_file_evidence_cases": len(
                [x for x in linked_only if x.get("merged_pr_with_file_evidence")]
            ),
            "top_linked_issue_numbers": [
                item.get("issue_number")
                for item in sorted(
                    linked_only,
                    key=lambda x: (
                        len(x.get("linked_pr_numbers") or []),
                        len(x.get("linked_commit_shas") or []),
                        x.get("link_score") or 0,
                    ),
                    reverse=True,
                )[:20]
            ],
        }
        summary_file = data_dir / f"issue_pr_commit_links_{repo_slug}_summary.json"
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        linked_count = len(linked_only)
        print(
            f"[{repo}] {len(links)} issue link records generated ({linked_count} linked issues) -> {out_file}"
        )
        print(f"[{repo}] linked-only file -> {linked_only_file}")
        print(f"[{repo}] summary file -> {summary_file}")


if __name__ == "__main__":
    main()