"""Interactive TF-IDF retrieval simulation over enriched "issues" documents (V2).

Despite the module's `test_` prefix, this is an interactive manual-testing
tool (not a pytest test): it builds a TF-IDF index over the title + `clean_text`
of valid issue docs for one repo and lets a human type free-text questions in
a REPL loop to inspect which issues would be retrieved, approximating what a
RAG retriever would surface before delivery/chunking.

NOTE: This module is near-identical to `test_tfidf_search_issues_v2.py`
(same repo, same TF-IDF approach) except it also builds an unused `ids` list
and defaults `top_k` to 10 instead of 5 with a slightly different print
format. It appears to be an earlier/duplicate version kept alongside the v2
script — see the "issues/ambiguities" note in the calling task.

Role in the evaluation stage: cheap, dependency-light (scikit-learn only)
sanity check of retrieval quality — no LLM or embeddings service required —
useful for spotting missing/duplicate/noisy `clean_text` content that would
hurt real semantic retrieval too.

Inputs:
    - `data/docs_issues_<repo>_v2.json` (repo hardcoded to "STM32CubeH7" in
      `main()`; pass a different value to `build_tfidf()` when calling
      programmatically).

Outputs:
    - Console-only: for each typed question, prints top-K matches with
      cosine-similarity score, issue number/title, layer/severity/board/
      component, and the GitHub URL. No files are written.

CLI usage:
    python pipeline/evaluation/test_tfidf_search_issues.py
    Then type a question at the "Question (enter to quit): " prompt; press
    Enter on an empty line to exit.
"""

import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from shared.utils.paths import DATA_DIR


def build_tfidf(repo: str = "STM32CubeH7"):
    """Load a repo's enriched issue docs and fit a TF-IDF vectorizer over title + body.

    Only docs with `is_valid` truthy (or missing, defaulting to valid) are
    indexed, matching what would be considered for delivery/chunking.

    Args:
        repo: Repo name (e.g. "STM32CubeH7"), used to locate the docs JSON.

    Returns:
        Tuple of (ids, meta, vectorizer, x_matrix):
            ids: list of issue `id` values, aligned with matrix rows.
            meta: list of the original doc dicts, aligned with matrix rows.
            vectorizer: fitted `TfidfVectorizer`.
            x_matrix: sparse TF-IDF matrix, one row per doc.
    """
    path = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"
    docs = json.loads(path.read_text(encoding="utf-8"))

    texts = []
    ids = []
    meta = []

    for d in docs:
        if not d.get("is_valid", True):
            continue
        ids.append(d["id"])
        meta.append(d)
        title = d.get("issue_title") or ""
        body = d.get("clean_text") or ""
        texts.append(title + "\n" + body)

    vectorizer = TfidfVectorizer(max_features=8000)
    x_matrix = vectorizer.fit_transform(texts)
    return ids, meta, vectorizer, x_matrix


def search(query: str, ids, meta, vectorizer, x_matrix, top_k: int = 5):
    """Rank indexed issue docs by cosine similarity to a free-text query.

    Args:
        query: Free-text question/search string.
        ids: List of issue ids aligned with `x_matrix` rows (unused here, kept
            for parity with `build_tfidf`'s return signature).
        meta: List of doc dicts aligned with `x_matrix` rows.
        vectorizer: Fitted `TfidfVectorizer` used to embed the query into the same space.
        x_matrix: TF-IDF matrix of indexed docs.
        top_k: Number of top matches to return.

    Returns:
        List of (similarity_score, doc_dict) tuples, sorted by descending score.
    """
    q_vec = vectorizer.transform([query])
    sims = cosine_similarity(q_vec, x_matrix)[0]
    # argsort ascending, then reverse to get highest-similarity indices first.
    idxs = sims.argsort()[::-1][:top_k]
    return [(sims[i], meta[i]) for i in idxs]


def main() -> None:
    """Run an interactive REPL for TF-IDF search over STM32CubeH7 issue docs.

    Side effects:
        Reads from stdin in a loop and prints ranked results to stdout until
        the user submits an empty line.
    """
    repo = "STM32CubeH7"
    ids, meta, vectorizer, x_matrix = build_tfidf(repo)

    while True:
        q = input("\nQuestion (enter to quit): ").strip()
        if not q:
            break
        res = search(q, ids, meta, vectorizer, x_matrix, top_k=10)
        for score, d in res:
            print(f"\n[score={score:.3f}] {d['issue_number']} - {d['issue_title']}")
            print(
                "  "
                f"layer={d.get('layer')}, severity={d.get('severity')}, "
                f"board={d.get('board')}, component={d.get('component')}"
            )
            print(f"  url={d.get('github_url')}")


if __name__ == "__main__":
    main()
