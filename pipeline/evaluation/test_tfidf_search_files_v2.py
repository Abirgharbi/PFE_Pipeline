"""Interactive TF-IDF retrieval simulation over enriched "files" documents (V2).

Despite the module's `test_` prefix, this is an interactive manual-testing
tool (not a pytest test): it builds a TF-IDF index over the `clean_text` of
valid files docs (README, release notes, project files, docs) for one repo
and lets a human type free-text questions in a REPL loop to inspect which
files would be retrieved, approximating what a RAG retriever would surface
before delivery/chunking.

Role in the evaluation stage: cheap, dependency-light (scikit-learn only)
sanity check of retrieval quality — no LLM or embeddings service required —
useful for spotting missing/duplicate/noisy `clean_text` content that would
hurt real semantic retrieval too.

Inputs:
    - `data/docs_files_<repo>_v2.json` (repo hardcoded to "STM32CubeH7" in
      `main()`; pass a different value to `build_tfidf_files()` when calling
      programmatically).

Outputs:
    - Console-only: for each typed question, prints top-K matches with
      cosine-similarity score, file_type/path, board/component/example_name,
      and a text excerpt. No files are written.

CLI usage:
    python pipeline/evaluation/test_tfidf_search_files_v2.py
    Then type a question at the "Question (enter to quit): " prompt; press
    Enter on an empty line to exit.
"""

import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from shared.utils.paths import DATA_DIR


def build_tfidf_files(repo: str = "STM32CubeH7"):
    """Load a repo's enriched files docs and fit a TF-IDF vectorizer over them.

    Only docs with `is_valid` truthy (or missing, defaulting to valid) are
    indexed, matching what would be considered for delivery/chunking.

    Args:
        repo: Repo name (e.g. "STM32CubeH7"), used to locate the docs JSON.

    Returns:
        Tuple of (meta, vectorizer, x_matrix):
            meta: list of the original doc dicts, aligned with matrix rows.
            vectorizer: fitted `TfidfVectorizer`.
            x_matrix: sparse TF-IDF matrix, one row per doc.

    Raises:
        RuntimeError: if no valid documents were found for the repo.
    """
    path = DATA_DIR / f"docs_files_{repo.lower()}_v2.json"
    docs = json.loads(path.read_text(encoding="utf-8"))

    texts = []
    meta = []

    for d in docs:
        if not d.get("is_valid", True):
            continue

        # Prepend path + file_type as a lightweight header so structural
        # metadata also contributes to term matching, not just body text.
        header = f"{d.get('path', '')}\n[{d.get('file_type', '')}]"
        body = d.get("clean_text") or ""
        texts.append(header + "\n" + body)
        meta.append(d)

    if not texts:
        raise RuntimeError(f"No valid files text for {repo}")

    vectorizer = TfidfVectorizer(max_features=8000)
    x_matrix = vectorizer.fit_transform(texts)
    return meta, vectorizer, x_matrix


def search_files(query: str, meta, vectorizer, x_matrix, top_k: int = 5):
    """Rank indexed files docs by cosine similarity to a free-text query.

    Args:
        query: Free-text question/search string.
        meta: List of doc dicts aligned with `x_matrix` rows (from `build_tfidf_files`).
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
    """Run an interactive REPL for TF-IDF search over STM32CubeH7 files docs.

    Side effects:
        Reads from stdin in a loop and prints ranked results to stdout until
        the user submits an empty line.
    """
    repo = "STM32CubeH7"
    meta, vectorizer, x_matrix = build_tfidf_files(repo)

    while True:
        q = input("\nQuestion (enter to quit): ").strip()
        if not q:
            break

        res = search_files(q, meta, vectorizer, x_matrix, top_k=5)
        for score, d in res:
            print(f"\n[score={score:.3f}] {d.get('file_type')} - {d.get('path')}")
            print(
                "  "
                f"board={d.get('board')}, component={d.get('component')}, "
                f"example_name={d.get('example_name')}"
            )
            print("  excerpt:")
            clean_text = d.get("clean_text") or ""
            print("   ", clean_text[:300].replace("\n", " ") + "...")
            print("-" * 80)


if __name__ == "__main__":
    main()
