"""Service module: multimodal PDF extraction (text + rendered figures) for STM32Cube documentation PDFs.

Role in the pipeline
---------------------
Used by `pipeline/ingestion/file_collect_service.py` (via `extract_pdf_multimodal`)
when ingesting PDF files under a repo's `Documentation(s)/` folder. Beyond
plain text extraction, this module renders each PDF page to a PNG, detects
candidate figure/diagram regions with OpenCV, crops them, and prepares
vision-model description "tasks" (later consumed by an external image
description pipeline, e.g. Alfred). Existing descriptions are re-injected as
`[FIGURE_DESCRIPTIONS]` blocks into the page text so figures remain
searchable/retrievable in the RAG knowledge base.

Inputs
------
- A PDF file path plus repo/path metadata for URL and asset-folder naming.
- `data/pdf_image_descriptions.json`: optional map of `figure_id -> description`
  text produced by a prior vision-model enrichment pass.

Outputs
-------
- Rendered page PNGs under `data/pdf_pages/<repo>/<slugified_path>/`.
- Cropped figure PNGs under `data/pdf_figures/<repo>/<slugified_path>/`.
- `data/pdf_image_tasks_<repo>.jsonl`: one JSON line per figure still missing
  a description, ready to be consumed by a vision-description worker.
- Return value of `extract_pdf_multimodal`: page text enriched with figure
  description blocks, plus figure records/counts and the task file path.

This module has no CLI entry point; it is imported, not run directly.
"""

import json
import re
from pathlib import Path
from typing import Any

import cv2
import fitz

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None



def slugify(path_text: str) -> str:
    """Turn a relative file path into a filesystem-safe folder-name fragment.

    Args:
        path_text: A relative path such as "Documentation/UM1234.pdf".

    Returns:
        The path with any character outside `[a-zA-Z0-9._/-]` replaced by "_",
        with leading/trailing slashes stripped.
    """
    return re.sub(r"[^a-zA-Z0-9._/-]+", "_", path_text).strip("/")


def make_figure_id(repo_name: str, rel_path: str, page_number: int, figure_index: int) -> str:
    """Build a stable, unique identifier for a detected figure.

    Args:
        repo_name: Repository name.
        rel_path: PDF path relative to the repo root.
        page_number: 1-based page number.
        figure_index: 1-based figure index within the page.

    Returns:
        A string of the form "<repo>:<rel_path>:p<page>:f<index>", used both
        as a lookup key in the descriptions map and as a task identifier.
    """
    return f"{repo_name}:{rel_path}:p{page_number}:f{figure_index}"


# PDF text extraction


def extract_pdf_text_by_page(pdf_path: Path) -> list[str]:
    """Extract plain text from a PDF, one entry per page, using `pypdf`.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of page texts (index 0 = page 1), or an empty list if `pypdf`
        is unavailable or extraction fails.
    """
    if PdfReader is None:
        print(f"[WARN] pypdf unavailable for {pdf_path}")
        return []

    try:
        reader = PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            pages.append((page.extract_text() or "").strip())
        return pages
    except Exception as exc:
        print(f"[WARN] Cannot extract PDF text by page from {pdf_path}: {exc}")
        return []


def extract_pdf_text_blocks(pdf_path: Path, zoom: float = 2.0) -> dict[int, list[dict[str, Any]]]:
    """Extract text blocks with bounding boxes, scaled to match the rendered page images.

    This is used to tell apart real figures from blocks of body text when
    detecting candidate figure regions (see `text_overlap_ratio`).

    Args:
        pdf_path: Path to the PDF file.
        zoom: Rendering zoom factor; must match the zoom used in
            `render_pdf_pages` so bounding boxes line up with the PNG pixels.

    Returns:
        A dict mapping 1-based page number to a list of
        `{"bbox": [x0, y0, x1, y1], "text": str}` entries.
    """
    page_blocks: dict[int, list[dict[str, Any]]] = {}

    try:
        doc = fitz.open(str(pdf_path))
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            blocks = page.get_text("blocks")  # tuples
            items: list[dict[str, Any]] = []

            for blk in blocks:
                x0, y0, x1, y1, text, *_ = blk
                txt = (text or "").strip()
                if not txt:
                    continue

                items.append(
                    {
                        "bbox": [
                            int(x0 * zoom),
                            int(y0 * zoom),
                            int(x1 * zoom),
                            int(y1 * zoom),
                        ],
                        "text": txt,
                    }
                )

            page_blocks[page_idx + 1] = items

    except Exception as exc:
        print(f"[WARN] Cannot extract text blocks from {pdf_path}: {exc}")

    return page_blocks


# =========================
# PDF rendering
# =========================

def render_pdf_pages(pdf_path: Path, out_dir: Path, zoom: float = 2.0) -> list[dict[str, Any]]:
    """Render every page of a PDF to a PNG image using PyMuPDF (fitz).

    Args:
        pdf_path: Path to the PDF file.
        out_dir: Directory to write `page_NNN.png` files to (created if needed).
        zoom: Rendering zoom factor (higher = higher resolution, matches the
            scale used by `extract_pdf_text_blocks` for bbox alignment).

    Returns:
        A list of dicts with `page_number`, `image_path`, `width`, `height`
        for each rendered page.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered_pages: list[dict[str, Any]] = []

    doc = fitz.open(str(pdf_path))
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        page_number = page_idx + 1
        page_file = out_dir / f"page_{page_number:03d}.png"
        pix.save(str(page_file))

        rendered_pages.append(
            {
                "page_number": page_number,
                "image_path": str(page_file),
                "width": pix.width,
                "height": pix.height,
            }
        )

    return rendered_pages


# =========================
# Geometry helpers
# =========================

def rect_area_xywh(r: tuple[int, int, int, int]) -> int:
    """Compute the area of a rectangle given as (x, y, w, h)."""
    return max(r[2], 0) * max(r[3], 0)


def rect_to_xyxy(r: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert an (x, y, w, h) rectangle to (x0, y0, x1, y1) corner form."""
    x, y, w, h = r
    return x, y, x + w, y + h


def xyxy_to_xywh(r: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert an (x0, y0, x1, y1) rectangle back to (x, y, w, h) form."""
    x0, y0, x1, y1 = r
    return x0, y0, x1 - x0, y1 - y0


def intersection_area_xywh(a: tuple[int, int, int, int], b_xyxy: tuple[int, int, int, int]) -> int:
    """Compute the overlap area between an (x, y, w, h) rect and an (x0, y0, x1, y1) rect.

    Args:
        a: Rectangle in (x, y, w, h) form.
        b_xyxy: Rectangle in (x0, y0, x1, y1) form.

    Returns:
        The intersection area, or 0 if the rectangles do not overlap.
    """
    ax0, ay0, ax1, ay1 = rect_to_xyxy(a)
    bx0, by0, bx1, by1 = b_xyxy

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    if ix1 <= ix0 or iy1 <= iy0:
        return 0
    return (ix1 - ix0) * (iy1 - iy0)


def close_or_overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int], gap: int = 30) -> bool:
    """Check whether two rectangles overlap or are within `gap` pixels of each other.

    Used to decide whether two nearby figure-candidate regions likely belong
    to the same diagram and should be merged.

    Args:
        a: First rectangle (x, y, w, h).
        b: Second rectangle (x, y, w, h).
        gap: Maximum pixel gap that still counts as "close".

    Returns:
        True if the rectangles overlap or are close enough to merge.
    """
    ax0, ay0, ax1, ay1 = rect_to_xyxy(a)
    bx0, by0, bx1, by1 = rect_to_xyxy(b)

    # overlap or near overlap
    return not (
        ax1 < bx0 - gap or
        bx1 < ax0 - gap or
        ay1 < by0 - gap or
        by1 < ay0 - gap
    )


def union_xywh(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Compute the bounding rectangle that encloses both input rectangles."""
    ax0, ay0, ax1, ay1 = rect_to_xyxy(a)
    bx0, by0, bx1, by1 = rect_to_xyxy(b)

    x0 = min(ax0, bx0)
    y0 = min(ay0, by0)
    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)

    return xyxy_to_xywh((x0, y0, x1, y1))


# =========================
# Figure detection (improved)
# =========================

def merge_close_regions(
    regions: list[tuple[int, int, int, int]],
    gap: int = 30,
) -> list[tuple[int, int, int, int]]:
    """Merge overlapping or nearby candidate regions into single bounding boxes.

    A raw contour-detection pass tends to split one diagram into several
    disjoint blobs (e.g. separate boxes and arrows); this greedily unions any
    regions that are close/overlapping until no more merges are possible.

    Args:
        regions: List of candidate rectangles in (x, y, w, h) form.
        gap: Maximum pixel gap to still consider two regions mergeable.

    Returns:
        The merged list of rectangles, sorted top-to-bottom, left-to-right.
    """
    if not regions:
        return []

    pending = regions[:]
    merged: list[tuple[int, int, int, int]] = []

    while pending:
        current = pending.pop(0)
        changed = True

        while changed:
            changed = False
            remaining = []
            for r in pending:
                if close_or_overlap(current, r, gap=gap):
                    current = union_xywh(current, r)
                    changed = True
                else:
                    remaining.append(r)
            pending = remaining

        merged.append(current)

    merged.sort(key=lambda r: (r[1], r[0]))
    return merged


def text_overlap_ratio(
    region: tuple[int, int, int, int],
    text_blocks: list[dict[str, Any]],
) -> float:
    """Compute the fraction of a candidate region's area covered by text blocks.

    Used to filter out regions that are actually paragraphs of body text
    (mis-detected as figures) rather than real diagrams.

    Args:
        region: Candidate rectangle in (x, y, w, h) form.
        text_blocks: Text blocks (with bbox) from `extract_pdf_text_blocks`
            for the same page.

    Returns:
        A ratio in [0, 1]; 0 if the region has no area.
    """
    area = rect_area_xywh(region)
    if area <= 0:
        return 0.0

    overlap_sum = 0
    for blk in text_blocks:
        bbox = blk.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        overlap_sum += intersection_area_xywh(region, tuple(bbox))

    return min(overlap_sum / area, 1.0)


def looks_like_caption(text: str) -> bool:
    """Heuristically detect whether a text snippet looks like a figure caption.

    Args:
        text: Candidate caption text.

    Returns:
        True if the (lowercased) text contains a common figure/diagram keyword.
    """
    t = (text or "").strip().lower()
    caption_keywords = [
        "figure",
        "fig.",
        "diagram",
        "overview",
        "architecture",
        "workflow",
        "block diagram",
        "illustration",
    ]
    return any(k in t for k in caption_keywords)


def detect_candidate_figure_regions(
    page_image_path: Path,
    text_blocks: list[dict[str, Any]] | None = None,
) -> list[tuple[int, int, int, int]]:
    """Detect likely figure/diagram bounding boxes on a rendered PDF page image.

    Approach: threshold the grayscale page to isolate non-white ink, apply a
    morphological close to group nearby strokes/shapes into blobs, then filter
    contours by size/aspect-ratio and merge nearby ones (see
    `merge_close_regions`). Finally, regions that are mostly covered by real
    text blocks (see `text_overlap_ratio`) are dropped since they are more
    likely paragraphs or text-heavy screenshots than genuine diagrams.

    Args:
        page_image_path: Path to the rendered page PNG.
        text_blocks: Text blocks (with bbox) for this page, from
            `extract_pdf_text_blocks`, used for the text-overlap filter.

    Returns:
        A list of candidate figure rectangles in (x, y, w, h) form, sorted
        top-to-bottom, left-to-right.
    """
    img = cv2.imread(str(page_image_path))
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h_img, w_img = gray.shape

    # Inversion threshold : texte/traits deviennent blancs
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Morphologie pour grouper les éléments visuels
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
    merged = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = 0.03 * (w_img * h_img)   # un peu plus strict qu'avant
    max_area = 0.92 * (w_img * h_img)

    regions: list[tuple[int, int, int, int]] = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        if area < min_area or area > max_area:
            continue

        if w < 180 or h < 140:
            continue

        ratio = w / max(h, 1)
        if ratio > 15 or ratio < 0.12:
            continue

        regions.append((x, y, w, h))

    # fusion plus aggressive
    regions = merge_close_regions(regions, gap=40)

    # filtre anti-texte
    filtered: list[tuple[int, int, int, int]] = []
    blocks = text_blocks or []

    for r in regions:
        overlap = text_overlap_ratio(r, blocks)

        # Si la région est couverte à >65% par des blocs texte,
        # elle ressemble trop à un paragraphe / screenshot de texte
        if overlap > 0.65:
            continue

        filtered.append(r)

    # si on a une légende "Figure..." à proximité, on peut garder la région associée
    # (pour le moment, le filtrage overlap suffit déjà bien)
    filtered.sort(key=lambda r: (r[1], r[0]))
    return filtered


# =========================
# Cropping
# =========================

def crop_figures_from_page(
    page_image_path: Path,
    regions: list[tuple[int, int, int, int]],
    out_dir: Path,
    repo_name: str,
    rel_path: str,
    page_number: int,
) -> list[dict[str, Any]]:
    """Crop each detected figure region out of a rendered page image and save it as PNG.

    Args:
        page_image_path: Path to the rendered page PNG.
        regions: Candidate figure rectangles in (x, y, w, h) form.
        out_dir: Directory to write cropped figure PNGs to (created if needed).
        repo_name: Repository name (used to build the figure id).
        rel_path: PDF path relative to the repo root (used to build the figure id).
        page_number: 1-based page number these regions belong to.

    Returns:
        A list of figure record dicts (`figure_id`, `page_number`,
        `figure_index`, `bbox`, `path`).
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(page_image_path))
    if img is None:
        return []

    records: list[dict[str, Any]] = []

    for idx, (x, y, w, h) in enumerate(regions, start=1):
        crop = img[y:y + h, x:x + w]
        figure_id = make_figure_id(repo_name, rel_path, page_number, idx)
        file_name = f"page_{page_number:03d}_fig_{idx:03d}.png"
        file_path = out_dir / file_name

        cv2.imwrite(str(file_path), crop)

        records.append(
            {
                "figure_id": figure_id,
                "page_number": page_number,
                "figure_index": idx,
                "bbox": [int(x), int(y), int(w), int(h)],
                "path": str(file_path),
            }
        )

    return records


# =========================
# Tasks
# =========================

def build_pdf_figure_tasks(
    repo_name: str,
    rel_path: str,
    source_pdf_url: str,
    page_texts: list[str],
    figure_records: list[dict[str, Any]],
    descriptions_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Build vision-model description tasks for figures that lack a description yet.

    Each task bundles enough context (surrounding page text, crop path, a
    fixed prompt) for an external image-description worker (e.g. Alfred) to
    produce a technical description later re-injected via
    `inject_figure_descriptions_into_pages`.

    Args:
        repo_name: Repository name.
        rel_path: PDF path relative to the repo root.
        source_pdf_url: GitHub URL of the source PDF (for traceability).
        page_texts: Extracted page texts (index 0 = page 1), used for context.
        figure_records: Detected/cropped figure records.
        descriptions_map: Existing `figure_id -> description` map; figures
            already described are skipped.

    Returns:
        A list of task dicts, one per figure still needing a description.
    """
    tasks: list[dict[str, Any]] = []

    for rec in figure_records:
        figure_id = str(rec["figure_id"])
        if descriptions_map.get(figure_id):
            continue

        page_number = int(rec["page_number"])
        page_text = page_texts[page_number - 1] if 0 < page_number <= len(page_texts) else ""

        tasks.append(
            {
                "image_id": figure_id,  # compatibilité agent
                "repo": repo_name,
                "pdf_path": rel_path,
                "source_pdf_url": source_pdf_url,
                "page_number": page_number,
                "image_index": rec["figure_index"],
                "image_path": rec["path"],
                "bbox": rec["bbox"],
                "page_context_text": page_text[:3000],
                "prompt": (
                    "Describe this technical figure or diagram from the STM32Cube PDF. "
                    "Explain the visible blocks, labels, arrows, modules, interfaces, "
                    "and its role relative to the surrounding section. "
                    "If the crop is mostly plain text and not a real figure, say explicitly that it is not a useful diagram."
                ),
            }
        )

    return tasks


def write_pdf_figure_tasks(task_file: Path, tasks: list[dict[str, Any]]) -> None:
    """Write figure description tasks as JSON Lines (one task per line).

    Args:
        task_file: Destination `.jsonl` path.
        tasks: Task dicts from `build_pdf_figure_tasks`.
    """
    lines = [json.dumps(t, ensure_ascii=False) for t in tasks]
    task_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_descriptions_map(desc_file: Path) -> dict[str, str]:
    """Load a previously produced `figure_id -> description` map from disk.

    Args:
        desc_file: Path to `data/pdf_image_descriptions.json`.

    Returns:
        The description map, or an empty dict if the file is missing,
        unparseable, or not a JSON object.
    """
    if not desc_file.exists():
        return {}

    try:
        data = json.loads(desc_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] Cannot load descriptions file {desc_file}: {exc}")
        return {}

    if not isinstance(data, dict):
        return {}

    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


# =========================
# Reinjection
# =========================

def inject_figure_descriptions_into_pages(
    page_texts: list[str],
    figure_records: list[dict[str, Any]],
    descriptions_map: dict[str, str],
) -> list[str]:
    """Re-inject figure descriptions into page text as `[FIGURE_DESCRIPTIONS]` blocks.

    This makes figure content retrievable by the RAG chunker/search even
    though the diagrams themselves are images: each page's text gets an
    appended block listing every figure detected on that page along with its
    (possibly still-pending) description.

    Args:
        page_texts: Extracted page texts (index 0 = page 1).
        figure_records: Detected/cropped figure records.
        descriptions_map: `figure_id -> description` map; missing entries are
            replaced with a placeholder note.

    Returns:
        A new list of page texts, each with its figure descriptions appended.
    """
    page_to_figs: dict[int, list[dict[str, Any]]] = {}
    for rec in figure_records:
        page_to_figs.setdefault(int(rec["page_number"]), []).append(rec)

    enriched_pages: list[str] = []

    for idx, page_text in enumerate(page_texts, start=1):
        figs = page_to_figs.get(idx, [])
        figs.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))

        blocks = [page_text.strip()] if page_text.strip() else []

        if figs:
            blocks.append("")
            blocks.append("[FIGURE_DESCRIPTIONS]")
            for rec in figs:
                figure_id = str(rec["figure_id"])
                desc = descriptions_map.get(figure_id, "").strip()
                if not desc:
                    desc = (
                        f"Figure detected on page {idx}, but no technical description "
                        f"is available yet for {figure_id}."
                    )
                blocks.append(f"- {figure_id}: {desc}")
            blocks.append("[/FIGURE_DESCRIPTIONS]")

        enriched_pages.append("\n".join(blocks).strip())

    return enriched_pages


# =========================
# Main multimodal pipeline
# =========================

def extract_pdf_multimodal(
    pdf_path: Path,
    repo_name: str,
    rel_path: str,
    source_pdf_url: str,
    data_dir: Path,
) -> dict[str, Any]:
    """Run the full multimodal PDF extraction pipeline for one PDF file.

    Pipeline steps:
    1. Extract text per page and text blocks (with bounding boxes).
    2. Render each page to a PNG image.
    3. Detect candidate figure regions on each page (OpenCV) and crop them.
    4. Build description tasks for figures without an existing description.
    5. Load any existing descriptions and re-inject them into the page text.

    Args:
        pdf_path: Path to the PDF file.
        repo_name: Repository name (used for asset folder naming and figure ids).
        rel_path: PDF path relative to the repo root.
        source_pdf_url: GitHub URL of the source PDF (for traceability in tasks).
        data_dir: Base data directory (`DATA_DIR`) under which rendered pages,
            cropped figures, and task/description files are stored.

    Returns:
        A dict with `content` (enriched text), `figure_records`,
        `figures_count`, `task_file`, `rendered_pages_count`, and
        `content_extractor` label.
    """
    zoom = 2.0

    page_texts = extract_pdf_text_by_page(pdf_path)
    page_text_blocks = extract_pdf_text_blocks(pdf_path, zoom=zoom)

    render_dir = data_dir / "pdf_pages" / repo_name.lower() / slugify(rel_path).replace("/", "_")
    rendered_pages = render_pdf_pages(pdf_path, render_dir, zoom=zoom)

    figure_dir = data_dir / "pdf_figures" / repo_name.lower() / slugify(rel_path).replace("/", "_")
    all_figure_records: list[dict[str, Any]] = []

    for page_info in rendered_pages:
        page_number = int(page_info["page_number"])
        page_image_path = Path(page_info["image_path"])

        text_blocks = page_text_blocks.get(page_number, [])
        regions = detect_candidate_figure_regions(
            page_image_path=page_image_path,
            text_blocks=text_blocks,
        )

        figure_records = crop_figures_from_page(
            page_image_path=page_image_path,
            regions=regions,
            out_dir=figure_dir,
            repo_name=repo_name,
            rel_path=rel_path,
            page_number=page_number,
        )
        all_figure_records.extend(figure_records)

    desc_file = data_dir / "pdf_image_descriptions.json"
    descriptions_map = load_descriptions_map(desc_file)

    tasks = build_pdf_figure_tasks(
        repo_name=repo_name,
        rel_path=rel_path,
        source_pdf_url=source_pdf_url,
        page_texts=page_texts,
        figure_records=all_figure_records,
        descriptions_map=descriptions_map,
    )

    task_file = data_dir / f"pdf_image_tasks_{repo_name.lower()}.jsonl"
    write_pdf_figure_tasks(task_file, tasks)

    enriched_pages = inject_figure_descriptions_into_pages(
        page_texts=page_texts,
        figure_records=all_figure_records,
        descriptions_map=descriptions_map,
    )

    content = "\n\n".join([p for p in enriched_pages if p.strip()]).strip()

    return {
        "content": content,
        "figure_records": all_figure_records,
        "figures_count": len(all_figure_records),
        "task_file": str(task_file),
        "rendered_pages_count": len(rendered_pages),
        "content_extractor": "pypdf+render+opencv+text-filter",
    }