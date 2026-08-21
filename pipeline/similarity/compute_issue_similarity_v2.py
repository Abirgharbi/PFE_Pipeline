"""CLI script: compute related-issue links via TF-IDF cosine similarity.

Role in the pipeline: similarity stage, run after `issues_to_docs_v2.py`
(enrichment) and before `docs_to_chunks_issues_v2.py` (chunking). Links
related issues together so a chunk about one issue can reference similar
issues, improving retrieval context in the RAG chatbot.

For each repo in the active config, reads `data/docs_issues_<repo>_v2.json`,
vectorizes the title+body text of all valid (`is_valid=True`) issues with
TF-IDF, computes pairwise cosine similarity, and attaches up to `top_k`
related issue ids (above `min_sim`) to each doc as `related_issue_ids`. The
result (all original docs, valid or not, each with `related_issue_ids` set)
is written to `data/docs_issues_<repo>_v2_sim.json`.

Config: resolved via `shared.utils.paths.get_config_path()`. Uses the
`repos` list.

Run with:
    python -m pipeline.similarity.compute_issue_similarity_v2
"""

import json
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from shared.utils.paths import DATA_DIR, get_config_path


def load_config() -> dict:
    """Load and return the active pipeline config as a dict."""
    cfg_path = get_config_path()
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def compute_related_issues_for_repo(repo: str, top_k: int = 3, min_sim: float = 0.4) -> None:
    """Compute and persist `related_issue_ids` for one repo's issue docs.

    Only issues with `is_valid` True (or missing, defaulting to True) are
    included in the TF-IDF vocabulary and similarity comparison, so
    filtered-out issues neither pollute nor receive related-issue links.

    Args:
        repo: Repository name used to locate `docs_issues_<repo>_v2.json`.
        top_k: Maximum number of related issues to keep per issue.
        min_sim: Minimum cosine similarity score required to keep a match;
            candidates are sorted by descending similarity and iteration
            stops as soon as a candidate falls below this threshold.

    Side Effects:
        Writes `docs_issues_<repo>_v2_sim.json` containing all original docs
        with `related_issue_ids` added/overwritten. Prints progress/warnings
        to stdout. No-op (with a warning) if the input file is missing or no
        valid issue text is found.
    """
    docs_file = DATA_DIR / f"docs_issues_{repo.lower()}_v2.json"
    if not docs_file.exists():
        print(f"[WARN] docs_issues_v2 not found for {repo}: {docs_file}")
        return

    docs: List[dict] = json.loads(docs_file.read_text(encoding="utf-8"))

    texts = []
    ids = []

    for d in docs:
        if not d.get("is_valid", True):
            continue
        ids.append(d["id"])
        title = d.get("issue_title") or ""
        body = d.get("clean_text") or ""
        texts.append(title + "\n" + body)

    if not texts:
        print(f"[WARN] No valid text for {repo}")
        return

    print(f"[SIM] TF-IDF over {len(texts)} valid issues for {repo}...")
    # TF-IDF + cosine similarity: a lightweight, deterministic way to find
    # near-duplicate/related issues without requiring embeddings/ML models.
    vectorizer = TfidfVectorizer(max_features=5000)
    x_matrix = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(x_matrix)

    id_to_related: dict[str, list[str]] = {doc_id: [] for doc_id in ids}

    for i, doc_id in enumerate(ids):
        sims = sim_matrix[i]
        # Sort candidate indices by descending similarity to this issue.
        indices = sims.argsort()[::-1]
        related: list[str] = []
        for j in indices:
            if j == i:
                continue
            # Similarities are sorted descending, so once we drop below
            # min_sim no further candidate can qualify -- stop early.
            if sims[j] < min_sim:
                break
            related.append(ids[j])
            if len(related) >= top_k:
                break
        id_to_related[doc_id] = related

    for d in docs:
        d["related_issue_ids"] = id_to_related.get(d["id"], [])

    out_file = DATA_DIR / f"docs_issues_{repo.lower()}_v2_sim.json"
    out_file.write_text(
        json.dumps(docs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[SIM] related_issue_ids added -> {out_file}")


def main() -> None:
    """Compute related-issue links for every repo in the active config."""
    cfg = load_config()
    repos = cfg["repos"]
    for repo in repos:
        compute_related_issues_for_repo(repo, top_k=3, min_sim=0.4)

    print("Done V2 similarity.")


if __name__ == "__main__":
    main()
