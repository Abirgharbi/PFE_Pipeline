import argparse
import json
import re
from collections import Counter, defaultdict
from typing import Any

from shared.utils.paths import DATA_DIR, get_config_path


_LICENSE_RE = re.compile(
    r"(copyright|all rights reserved|licensed under|spdx|permission is hereby)",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MD_BADGE_RE = re.compile(r"!\[[^\]]*\]\(https?://img\.shields\.io[^)]*\)", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_CMSIS_BIT_MACRO_RE = re.compile(r"^\s*#define\s+\w+_(Pos|Msk|\d+)\b")
_STAR_BANNER_RE = re.compile(r"^[\s/*#_=\-]{12,}$")


def get_default_repos() -> list[str]:
    cfg = json.loads(get_config_path().read_text(encoding="utf-8-sig"))
    repos = cfg.get("repos", [])
    if repos:
        return repos
    return []


def classify_noise_line(line: str) -> str | None:
    s = line.strip()
    if not s:
        return "empty"

    if _CMSIS_BIT_MACRO_RE.match(s):
        return "cmsis_bit_macro"
    if _LICENSE_RE.search(s):
        return "license_or_legal"
    if _MD_BADGE_RE.search(s) or _MD_IMAGE_RE.search(s):
        return "markdown_image_or_badge"

    if _HTML_TAG_RE.search(s):
        plain = _HTML_TAG_RE.sub("", s).strip()
        # Consider the line as structural HTML noise when tags dominate the content.
        if len(plain) <= max(8, len(s) // 4):
            return "html_structure"

    if _STAR_BANNER_RE.match(s):
        return "ascii_banner"

    return None


def compute_density_stats(docs: list[dict[str, Any]]) -> dict[str, Any]:
    total_chars = 0
    signal_chars = 0
    total_lines = 0
    signal_lines = 0
    noise_reasons: Counter[str] = Counter()

    per_type_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total_chars": 0, "signal_chars": 0, "total_lines": 0, "signal_lines": 0}
    )

    for doc in docs:
        text = str(doc.get("clean_text", "") or "")
        file_type = str(doc.get("file_type", "other") or "other")

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            line_chars = len(line)
            total_chars += line_chars
            total_lines += 1

            per_type_totals[file_type]["total_chars"] += line_chars
            per_type_totals[file_type]["total_lines"] += 1

            reason = classify_noise_line(line)
            if reason is None:
                signal_chars += line_chars
                signal_lines += 1
                per_type_totals[file_type]["signal_chars"] += line_chars
                per_type_totals[file_type]["signal_lines"] += 1
            else:
                noise_reasons[reason] += 1

    density_chars = (signal_chars / total_chars) if total_chars else 0.0
    density_lines = (signal_lines / total_lines) if total_lines else 0.0

    per_type_density = {}
    for file_type, vals in sorted(per_type_totals.items()):
        tc = vals["total_chars"]
        tl = vals["total_lines"]
        sc = vals["signal_chars"]
        sl = vals["signal_lines"]
        per_type_density[file_type] = {
            "total_chars": tc,
            "signal_chars": sc,
            "density_chars": (sc / tc) if tc else 0.0,
            "total_lines": tl,
            "signal_lines": sl,
            "density_lines": (sl / tl) if tl else 0.0,
        }

    return {
        "docs": len(docs),
        "total_chars": total_chars,
        "signal_chars": signal_chars,
        "density_chars": density_chars,
        "total_lines": total_lines,
        "signal_lines": signal_lines,
        "density_lines": density_lines,
        "noise_reasons": dict(noise_reasons.most_common()),
        "per_file_type": per_type_density,
    }


def load_docs(repo: str, version: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"docs_files_{repo.lower()}_{version}.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def compute_repo_gain(repo: str) -> dict[str, Any]:
    docs_v2 = load_docs(repo, "v2")
    docs_v3 = load_docs(repo, "v3")

    v2 = compute_density_stats(docs_v2)
    v3 = compute_density_stats(docs_v3)

    d2 = v2["density_chars"]
    d3 = v3["density_chars"]
    gain_chars_pct = ((d3 - d2) / d2 * 100.0) if d2 > 0 else 0.0

    l2 = v2["density_lines"]
    l3 = v3["density_lines"]
    gain_lines_pct = ((l3 - l2) / l2 * 100.0) if l2 > 0 else 0.0

    return {
        "repo": repo,
        "formula": "Density = signal_chars / total_chars ; Gain(%) = (DensityV3 - DensityV2) / DensityV2 * 100",
        "v2": v2,
        "v3": v3,
        "gain_percent_chars": gain_chars_pct,
        "gain_percent_lines": gain_lines_pct,
    }


def save_result(result: dict[str, Any]) -> str:
    repo = str(result["repo"]).lower()
    out_path = DATA_DIR / f"summary_cleaning_density_{repo}_v2_vs_v3.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute reproducible V2->V3 signal density gain for docs_files artifacts."
    )
    parser.add_argument(
        "--repo",
        action="append",
        help="Repo name (can be repeated), e.g., cmsis_device_f3 or STM32CubeH7",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repos = args.repo or get_default_repos()
    if not repos:
        raise ValueError("No repos found. Provide --repo explicitly.")

    for repo in repos:
        try:
            result = compute_repo_gain(repo)
            out_file = save_result(result)
            print(f"[OK] {repo}")
            print(
                f"     Density chars V2={result['v2']['density_chars']:.4f} "
                f"-> V3={result['v3']['density_chars']:.4f} "
                f"(gain={result['gain_percent_chars']:.2f}%)"
            )
            print(
                f"     Density lines V2={result['v2']['density_lines']:.4f} "
                f"-> V3={result['v3']['density_lines']:.4f} "
                f"(gain={result['gain_percent_lines']:.2f}%)"
            )
            print(f"     Saved: {out_file}")
        except FileNotFoundError as exc:
            print(f"[WARN] {repo}: {exc}")


if __name__ == "__main__":
    main()
