"""Validate pipeline JSON outputs against their JSON Schema contracts.

This is the schema-validation gate of the evaluation stage: it checks that
the enriched docs and chunked outputs produced by the enrichment/chunking
stages structurally conform to the JSON Schemas declared under
`shared/schemas/`, before those files are used in TF-IDF tests, delivery
exports, or KB upload. Catching a schema mismatch here (missing/renamed
field, wrong type) is cheaper than discovering it downstream in delivery or
the KB.

Inputs:
    - Schemas: `shared/schemas/docs_issues_v2.schema.json`,
      `shared/schemas/docs_files_v2.schema.json`,
      `shared/schemas/chunks_issues_v2.schema.json`,
      `shared/schemas/chunks_files_v2.schema.json`.
    - Data: `data/docs_issues_<repo>_v2.json`,
      `data/docs_files_<repo>_v2.json` (or `_v3.json` if present),
      `data/chunks_issues_<repo>_v2.json`, `data/chunks_files_<repo>_v2.json`
      for the default repo (first `STM32Cube*` entry in
      `shared/config/config_all_series.json`).

Outputs:
    - Console-only: "OK: ..." line per successfully validated file, a
      "[WARN] ... not found" line for missing data files (skipped, not
      failed), and a final validated-file count. Raises
      `jsonschema.ValidationError` (uncaught) if any present data file does
      not match its schema.

CLI usage:
    python -m pipeline.evaluation.validate_schemas
    (no CLI args; validates the default repo's 4 doc/chunk file pairs)
"""

import json
from pathlib import Path

from jsonschema import validate

from shared.utils.paths import get_config_path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

def get_default_repo() -> str:
    """Return the first STM32Cube* repo from the shared config, or the first repo overall.

    Used to pick a default repo to validate when the caller does not specify one.
    """
    cfg = json.loads(get_config_path().read_text(encoding="utf-8-sig"))
    repos = cfg.get("repos", [])
    return next((repo for repo in repos if str(repo).lower().startswith("stm32cube")), repos[0])


def build_schema_data_pairs(repo: str) -> list[tuple[str, str]]:
    """Build the list of (schema_path, data_path) pairs to validate for a repo.

    Args:
        repo: Repo name (e.g. "STM32CubeH7").

    Returns:
        List of (schema_relative_path, data_relative_path) tuples for the
        issues docs, files docs, issues chunks, and files chunks JSON files.
        The files docs entry uses the v3 schema/suffix if `docs_files_<slug>_v3.json`
        exists, else falls back to v2, matching the enrichment stage's own
        v2/v3 versioning.
    """
    slug = repo.lower()
    docs_files_v3 = PROJECT_ROOT / "data" / f"docs_files_{slug}_v3.json"
    docs_files_suffix = "v3" if docs_files_v3.exists() else "v2"
    return [
        (
            "shared/schemas/docs_issues_v2.schema.json",
            f"data/docs_issues_{slug}_v2.json",
        ),
        (
            "shared/schemas/docs_files_v2.schema.json",
            f"data/docs_files_{slug}_{docs_files_suffix}.json",
        ),
        (
            "shared/schemas/chunks_issues_v2.schema.json",
            f"data/chunks_issues_{slug}_v2.json",
        ),
        (
            "shared/schemas/chunks_files_v2.schema.json",
            f"data/chunks_files_{slug}_v2.json",
        ),
    ]


def validate_file(schema_rel: str, data_rel: str) -> bool:
    """Validate one data JSON file against one JSON Schema file.

    Args:
        schema_rel: Schema path relative to the project root.
        data_rel: Data file path relative to the project root.

    Returns:
        True if validation ran and succeeded, False if the data file was
        missing (skipped, not treated as a failure).

    Raises:
        FileNotFoundError: if the schema file itself is missing (schemas are
            expected to always be present, unlike per-repo data files).
        jsonschema.ValidationError: if the data does not conform to the schema.
    """
    schema_path = PROJECT_ROOT / schema_rel
    data_path = PROJECT_ROOT / data_rel

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    if not data_path.exists():
        print(f"[WARN] Schema validation skipped; data file not found: {data_path}")
        return False

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))

    validate(instance=data, schema=schema)
    print(f"OK: {data_rel} matches {schema_rel}")
    return True


def main() -> None:
    """Validate the default repo's docs/chunks files against their schemas and print a summary."""
    repo = get_default_repo()
    print(f"Running schema validation for {repo}...")
    validated = 0
    for schema_rel, data_rel in build_schema_data_pairs(repo):
        if validate_file(schema_rel, data_rel):
            validated += 1
    print(f"Schema validation completed: {validated} file(s) validated.")


if __name__ == "__main__":
    main()
