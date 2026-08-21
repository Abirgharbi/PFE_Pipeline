"""Validate coherence of Alfred image descriptions against their source context.

This script checks whether Alfred (internal LLM Vision API) generated image
descriptions and OCR text are actually grounded in / consistent with the
surrounding text they were derived from, for two sources:

1. Issue images: `image_analyses` entries inside ST-ready enriched issue
   JSON files (`st_ready_issues_with_images_*.json`), where the "context" is
   the issue body/clean_text.
2. PDF figures: entries in a PDF figure descriptions map, where the
   "context" is the surrounding page text captured in PDF task files.

For each image/figure it computes a lexical grounding score (token overlap
with the context), an optional semantic similarity score, and an optional
contradiction probability (does the description contradict the context),
then combines them into a single `coherence_score` and a reliability class
(EXCELLENT/BON/ACCEPTABLE/INSUFFISANT). Rows below a configurable threshold
are flagged as low-coherence with machine-readable reason codes.

Semantic similarity and contradiction detection each support three modes:
- "off": skipped entirely (score recorded as None/0).
- "lite": dependency-free heuristic proxies (token Jaccard + char-trigram
  cosine for semantics; polarity-opposite heuristic for contradiction) so
  the script runs without `sentence-transformers`/`transformers` installed.
- "auto"/"required": use real ML models (`sentence-transformers` for
  semantic similarity, an NLI `transformers` pipeline for contradiction),
  falling back to unavailable (auto) or raising (required) if the
  dependency/model cannot be loaded.

Role in the evaluation stage: this is the automated coherence-QA gate for
Alfred-enriched content, catching cases where an image description was
hallucinated, generic, or contradicts the ticket/document it was attached
to — separate from `eval_image_descriptions.py`, which focuses on
success/failure rates and short/low-quality descriptions rather than
context coherence.

Inputs:
    - Issue JSON files matching `--issue-glob` (default
      `datasets/07_delivery/st_ready/by_series/**/issues_json/st_ready_issues_with_images_*.json`),
      each containing records with an `image_analyses` list.
    - PDF figure descriptions map at `--pdf-descriptions` (default
      `data/pdf_image_descriptions.json`), a dict of `image_id -> description`.
    - PDF task files matching `--pdf-task-glob` (default
      `data/pdf_image_tasks_*.jsonl`), JSONL files with `image_id` and
      `page_context_text` per line.

Outputs:
    - CSV report at `--output-csv` (default
      `docs/evaluation/alfred_coherence_report.csv`) with one row per
      evaluated image/figure.
    - Summary JSON at `--output-summary-json` (default
      `docs/evaluation/alfred_coherence_summary.json`) with aggregate counts,
      low-coherence rate, and per-source breakdowns plus the scoring config used.
    - Console: scan/availability info and a short summary table.

CLI usage:
    python pipeline/evaluation/validate_alfred_coherence.py \
        [--issue-glob GLOB] [--pdf-descriptions PATH] [--pdf-task-glob GLOB] \
        [--threshold 0.12] [--semantic-mode {off,lite,auto,required}] \
        [--nli-mode {off,lite,auto,required}] [--semantic-model NAME] \
        [--nli-model NAME] [--alpha-lexical 0.4] [--beta-semantic 0.6] \
        [--gamma-contradiction 0.8] [--semantic-alert-threshold 0.55] \
        [--contradiction-alert-threshold 0.5] [--excellent-threshold 0.95] \
        [--good-threshold 0.85] [--acceptable-threshold 0.70] [--limit N] \
        [--output-csv PATH] [--output-summary-json PATH]
"""

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from shared.utils.paths import PROJECT_ROOT


# Common English/French stopwords excluded from lexical token overlap so
# grounding scores reflect meaningful shared terms, not filler words.
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "than",
    "have", "has", "had", "was", "were", "are", "is", "be", "been", "being", "will", "would",
    "can", "could", "should", "may", "might", "not", "you", "your", "they", "their", "them",
    "our", "nous", "vous", "avec", "sans", "dans", "pour", "sur", "par", "les", "des", "une",
    "est", "sont", "été", "être", "cela", "ceci", "comme", "plus", "moins", "very", "also",
    "image", "description", "text", "figure", "technical", "issue", "github", "url", "none",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-/]{2,}")
NEGATION_HINTS = {
    "not", "no", "never", "without", "cannot", "can't", "failed", "fail", "fails",
    "error", "errors", "missing", "none", "disabled", "disable", "wrong",
    "pas", "sans", "jamais", "erreur", "echec", "manquant",
}
POSITIVE_HINTS = {
    "works", "working", "ok", "fixed", "resolved", "success", "enabled", "available",
    "correct", "valid", "supported", "stable", "fonctionne", "corrige", "actif",
}


@dataclass
class CoherenceRow:
    """One evaluated row of the coherence CSV report (one image or PDF figure)."""

    source: str
    series: str
    repo: str
    record_id: str
    image_or_figure_id: str
    url_or_path: str
    status: str
    context_field: str
    desc_len: int
    ocr_len: int
    lexical_score: float
    semantic_score: float
    contradiction_prob: float
    desc_context_overlap: float
    ocr_context_overlap: float
    coherence_score: float
    reliability_class: str
    flag_low_coherence: int
    reason_codes: str
    notes: str


@dataclass
class ScoringConfig:
    """Weights and thresholds controlling final coherence scoring and classification."""

    alpha_lexical: float
    beta_semantic: float
    gamma_contradiction: float
    threshold_low: float
    contradiction_alert_threshold: float
    semantic_alert_threshold: float
    excellent_threshold: float
    good_threshold: float
    acceptable_threshold: float


class SemanticScorer:
    """Computes semantic similarity between a description and its source context.

    Backed by a `sentence-transformers` model in "auto"/"required" mode, a
    dependency-free heuristic in "lite" mode, or disabled in "off" mode.
    """

    def __init__(self, model_name: str, mode: str):
        """Configure the scorer and attempt to load its backing model (if any).

        Args:
            model_name: HuggingFace `sentence-transformers` model id, used
                only when `mode` is "auto" or "required".
            mode: One of "off", "lite", "auto", "required".
        """
        self.model_name = model_name
        self.mode = mode
        self.available = False
        self._model = None
        self.error_message = ""
        self._load()

    def _load(self) -> None:
        """Load the sentence-transformers model, unless mode is "off"/"lite".

        Side effects:
            Sets `self.available`/`self.error_message`. Re-raises the load
            exception only when `mode == "required"`, so "auto" mode can
            silently fall back to unavailable (score() then returns None).
        """
        if self.mode == "off":
            self.error_message = "semantic_disabled"
            return
        if self.mode == "lite":
            self.available = True
            self.error_message = "semantic_lite_builtin"
            return
        try:
            from sentence_transformers import SentenceTransformer, util

            self._model = SentenceTransformer(self.model_name)
            self._cos = util.cos_sim
            self.available = True
        except Exception as exc:  # pragma: no cover - runtime dependency
            self.error_message = f"semantic_unavailable:{exc.__class__.__name__}"
            if self.mode == "required":
                raise

    def score(self, a: str, b: str) -> Optional[float]:
        """Return a [0, 1] semantic similarity score between two texts, or None if unavailable.

        Args:
            a: First text (e.g. Alfred description).
            b: Second text (e.g. source context).

        Returns:
            Similarity in [0, 1], or None if the model failed to load
            ("auto" mode) or scoring is disabled ("off" mode).
        """
        if self.mode == "lite":
            return semantic_lite_score(a, b)
        if not self.available:
            return None
        if not a.strip() or not b.strip():
            return 0.0
        emb = self._model.encode([a, b], convert_to_tensor=True)
        raw = float(self._cos(emb[0], emb[1]).item())
        # Convert cosine from [-1, 1] to [0, 1] for easier thresholding.
        return max(0.0, min(1.0, (raw + 1.0) / 2.0))


class NLIContradictionScorer:
    """Computes the probability that a description contradicts its source context.

    Backed by a Natural Language Inference (NLI) `transformers` pipeline in
    "auto"/"required" mode, a dependency-free polarity heuristic in "lite"
    mode, or disabled in "off" mode.
    """

    def __init__(self, model_name: str, mode: str):
        """Configure the scorer and attempt to load its backing NLI pipeline (if any).

        Args:
            model_name: HuggingFace NLI model id, used only when `mode` is
                "auto" or "required".
            mode: One of "off", "lite", "auto", "required".
        """
        self.model_name = model_name
        self.mode = mode
        self.available = False
        self._clf = None
        self.error_message = ""
        self._load()

    def _load(self) -> None:
        """Load the transformers text-classification (NLI) pipeline, unless mode is "off"/"lite".

        Side effects:
            Sets `self.available`/`self.error_message`. Re-raises the load
            exception only when `mode == "required"`.
        """
        if self.mode == "off":
            self.error_message = "nli_disabled"
            return
        if self.mode == "lite":
            self.available = True
            self.error_message = "nli_lite_builtin"
            return
        try:
            from transformers import pipeline

            self._clf = pipeline(
                "text-classification",
                model=self.model_name,
                top_k=None,
                truncation=True,
            )
            self.available = True
        except Exception as exc:  # pragma: no cover - runtime dependency
            self.error_message = f"nli_unavailable:{exc.__class__.__name__}"
            if self.mode == "required":
                raise

    def contradiction_probability(self, premise: str, hypothesis: str) -> Optional[float]:
        """Return the probability in [0, 1] that `hypothesis` contradicts `premise`.

        Args:
            premise: The trusted source text (e.g. issue body / page context).
            hypothesis: The generated text to check (e.g. Alfred description).

        Returns:
            Contradiction probability in [0, 1], or None if the NLI pipeline
            is unavailable ("auto" mode) or scoring is disabled ("off" mode).
        """
        if self.mode == "lite":
            return contradiction_lite_probability(premise, hypothesis)
        if not self.available:
            return None
        if not premise.strip() or not hypothesis.strip():
            return 0.0

        out = self._clf(f"premise: {premise} hypothesis: {hypothesis}")
        # top_k=None returns scores for all labels; some pipelines nest the
        # list one level deeper for a single input, hence this unwrap.
        preds = out[0] if out and isinstance(out[0], list) else out
        if not isinstance(preds, list):
            return None

        contradiction = 0.0
        for p in preds:
            label = str(p.get("label", "")).lower()
            score = float(p.get("score", 0.0))
            if "contrad" in label:
                contradiction = max(contradiction, score)
        return max(0.0, min(1.0, contradiction))


def tokenize(text: str) -> list[str]:
    """Lowercase-tokenize text into meaningful words, dropping stopwords and pure numbers.

    Args:
        text: Input text.

    Returns:
        List of lowercase alphanumeric tokens (min length 3), excluding
        `STOPWORDS` and digit-only tokens, used as the basis for lexical
        overlap and polarity heuristics.
    """
    if not text:
        return []
    out: list[str] = []
    for token in TOKEN_RE.findall(text.lower()):
        if token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        out.append(token)
    return out


def overlap_ratio(content: str, context: str) -> float:
    """Fraction of `content` tokens that also appear in `context` (lexical grounding proxy).

    Args:
        content: Generated text to check (e.g. Alfred description or OCR text).
        context: Trusted source text the content should be grounded in.

    Returns:
        Ratio in [0, 1] of shared tokens over `content`'s token set size; 0.0
        if `content` has no meaningful tokens.
    """
    content_tokens = set(tokenize(content))
    context_tokens = set(tokenize(context))
    if not content_tokens:
        return 0.0
    overlap = content_tokens.intersection(context_tokens)
    return len(overlap) / max(len(content_tokens), 1)


def _char_ngrams(text: str, n: int = 3) -> dict[str, int]:
    """Build a character n-gram frequency map, used as a fuzzy-match signal for `semantic_lite_score`.

    Args:
        text: Input text.
        n: N-gram size (default trigrams).

    Returns:
        Dict mapping each n-gram to its occurrence count; empty if `text` is
        shorter than `n` characters after whitespace normalization.
    """
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    if len(normalized) < n:
        return {}
    grams: dict[str, int] = {}
    for i in range(0, len(normalized) - n + 1):
        g = normalized[i:i + n]
        grams[g] = grams.get(g, 0) + 1
    return grams


def _cosine_counts(a: dict[str, int], b: dict[str, int]) -> float:
    """Cosine similarity between two sparse count vectors (e.g. character n-gram frequencies).

    Args:
        a: First frequency map.
        b: Second frequency map.

    Returns:
        Cosine similarity in [0, 1] (both inputs are non-negative counts);
        0.0 if either map is empty.
    """
    if not a or not b:
        return 0.0
    dot = 0.0
    for k, va in a.items():
        vb = b.get(k)
        if vb:
            dot += va * vb
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_lite_score(a: str, b: str) -> float:
    """Dependency-free semantic proxy: token Jaccard + char-trigram cosine."""
    ta = set(tokenize(a))
    tb = set(tokenize(b))
    if not ta and not tb:
        return 0.0
    inter = len(ta.intersection(tb))
    union = len(ta.union(tb)) if ta or tb else 1
    token_jaccard = inter / union

    g1 = _char_ngrams(a, n=3)
    g2 = _char_ngrams(b, n=3)
    char_cos = _cosine_counts(g1, g2)

    # Blend word-level (jaccard) and character-level (trigram cosine)
    # similarity so near-duplicate phrasing still scores well even when
    # exact word overlap is low (e.g. singular/plural, minor rewording).
    return clamp01(0.7 * token_jaccard + 0.3 * char_cos)


def _polarity_signal(text: str) -> tuple[int, float]:
    """Estimate whether a text leans positive/negative and how strongly.

    Args:
        text: Input text.

    Returns:
        Tuple of (sign, magnitude): sign is 1 (positive-leaning),
        -1 (negative-leaning), or 0 (neutral/no signal); magnitude in [0, 1]
        scales with how much the positive/negative hint counts diverge
        relative to total token count.
    """
    toks = tokenize(text)
    if not toks:
        return (0, 0.0)
    pos = sum(1 for t in toks if t in POSITIVE_HINTS)
    neg = sum(1 for t in toks if t in NEGATION_HINTS)
    diff = pos - neg
    mag = min(1.0, (abs(diff) / max(len(toks), 1)) * 5.0)
    sign = 1 if diff > 0 else (-1 if diff < 0 else 0)
    return sign, mag


def contradiction_lite_probability(premise: str, hypothesis: str) -> float:
    """Dependency-free contradiction proxy based on opposite polarity over shared anchors."""
    p_toks = set(tokenize(premise))
    h_toks = set(tokenize(hypothesis))
    if not h_toks:
        return 0.0
    overlap = len(p_toks.intersection(h_toks)) / max(len(h_toks), 1)

    ps, pm = _polarity_signal(premise)
    hs, hm = _polarity_signal(hypothesis)
    # Contradiction is only plausible when both texts discuss the same topic
    # (token overlap) but disagree in sentiment/polarity (e.g. premise says
    # "works", hypothesis says "fails").
    opposite = (ps != 0 and hs != 0 and ps != hs)

    if opposite and overlap >= 0.2:
        return clamp01(0.6 * overlap + 0.4 * ((pm + hm) / 2.0))
    if overlap < 0.1:
        return 0.0
    return clamp01(0.15 * overlap)


def clamp01(x: float) -> float:
    """Clamp a float into the [0, 1] range."""
    return max(0.0, min(1.0, x))


def classify_score(score: float, cfg: ScoringConfig) -> str:
    """Map a numeric coherence score to a reliability class using `cfg`'s thresholds.

    Args:
        score: Final coherence score in [0, 1].
        cfg: Scoring configuration providing excellent/good/acceptable thresholds.

    Returns:
        One of "EXCELLENT", "BON", "ACCEPTABLE", "INSUFFISANT" (French labels
        kept for consistency with existing reports/dashboards).
    """
    if score >= cfg.excellent_threshold:
        return "EXCELLENT"
    if score >= cfg.good_threshold:
        return "BON"
    if score >= cfg.acceptable_threshold:
        return "ACCEPTABLE"
    return "INSUFFISANT"


def compute_final_score(
    lexical_score: float,
    semantic_score: Optional[float],
    contradiction_prob: Optional[float],
    cfg: ScoringConfig,
) -> float:
    """Combine lexical grounding, semantic similarity, and contradiction penalty into one score.

    Args:
        lexical_score: Token-overlap grounding score in [0, 1].
        semantic_score: Semantic similarity in [0, 1], or None if not computed.
        contradiction_prob: Contradiction probability in [0, 1], or None if not computed.
        cfg: Scoring configuration providing the alpha/beta/gamma weights.

    Returns:
        Final coherence score in [0, 1]: a weighted average of lexical and
        semantic scores (re-normalized if semantic is missing), then
        multiplied down by a contradiction penalty.
    """
    lex_w = max(0.0, cfg.alpha_lexical)
    sem_w = max(0.0, cfg.beta_semantic) if semantic_score is not None else 0.0
    support = lex_w + sem_w

    if support <= 0:
        base = lexical_score
    else:
        sem = semantic_score if semantic_score is not None else 0.0
        # Re-normalize weights by whatever signals are actually available,
        # so missing semantic scoring doesn't silently zero out the base score.
        base = (lex_w * lexical_score + sem_w * sem) / support

    contradiction = contradiction_prob if contradiction_prob is not None else 0.0
    # Contradiction acts as a multiplicative penalty rather than a subtractive
    # one, so a high-grounding description that still contradicts context is
    # pulled down proportionally rather than just losing a fixed amount.
    penalty = clamp01(cfg.gamma_contradiction * contradiction)
    return clamp01(base * (1.0 - penalty))


def clean_context(text: str) -> str:
    """Strip Alfred-appended/inline enrichment markers from a context field before comparison.

    Without this, comparing a description to "context" that already contains
    Alfred's own output (appended by `enrich_json_images_with_alfred.py`)
    would trivially inflate the coherence score by comparing text to itself.

    Args:
        text: Raw context text (e.g. issue body), possibly Alfred-enriched.

    Returns:
        Context text with the "Image-derived context:" appended section and
        inline `[IMAGE DESCRIPTION]`/`[IMAGE TEXT]` tags removed, whitespace
        collapsed.
    """
    if not text:
        return ""
    cleaned = text
    # Remove appended section added by enrich_json_images_with_alfred.
    marker = "\n\nImage-derived context:"
    idx = cleaned.find(marker)
    if idx >= 0:
        cleaned = cleaned[:idx]

    # Remove inline Alfred tags if present.
    cleaned = re.sub(r"\[IMAGE DESCRIPTION\]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[IMAGE TEXT\]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def pick_context_field(record: dict[str, Any]) -> tuple[str, str]:
    """Pick the first non-empty candidate field to use as an issue/record's grounding context.

    Args:
        record: Issue/PR record dict.

    Returns:
        Tuple of (field_name, cleaned_text). Returns ("", "") if none of the
        candidate fields are present/non-empty.
    """
    # Prefer raw fields first to avoid leakage from enriched text.
    for key in ("body", "clean_text", "text", "description", "resolver_card_text", "st_ready_text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return key, clean_context(value)
    return "", ""


def parse_issue_records(path: Path) -> list[dict[str, Any]]:
    """Load an issue JSON file's records, tolerating both list-root and dict-root shapes.

    Args:
        path: Path to an ST-ready enriched issue JSON file.

    Returns:
        List of record dicts. Handles both a top-level JSON array and a
        dict with one of several known list-valued keys (different delivery
        exports use different root shapes); returns an empty list otherwise.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("issues", "pull_requests", "prs", "items", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


def detect_series_from_path(path: Path) -> str:
    """Infer the STM32 series name (e.g. "H7") from a `by_series/<series>/...` file path.

    Args:
        path: File path, expected to contain a `by_series` segment.

    Returns:
        The path segment following `by_series`, or "unknown" if not found.
    """
    parts = [p.lower() for p in path.parts]
    if "by_series" in parts:
        i = parts.index("by_series")
        if i + 1 < len(parts):
            return path.parts[i + 1]
    return "unknown"


def evaluate_issue_image_coherence(
    issue_files: list[Path],
    cfg: ScoringConfig,
    semantic_scorer: SemanticScorer,
    nli_scorer: NLIContradictionScorer,
    limit: int,
) -> list[CoherenceRow]:
    """Score every Alfred image analysis found across a set of issue JSON files.

    Args:
        issue_files: Enriched issue JSON files to scan (matches from `--issue-glob`).
        cfg: Scoring configuration (weights/thresholds).
        semantic_scorer: Semantic similarity scorer.
        nli_scorer: Contradiction probability scorer.
        limit: Max total rows to produce (0 = unlimited); used to cap runtime
            on large corpora or when models are slow to run.

    Returns:
        List of `CoherenceRow` entries, one per `image_analyses` entry found,
        including a zero-score flagged row for analyses whose `status` is
        not "ok" (e.g. UNAVAILABLE/error).
    """
    rows: list[CoherenceRow] = []

    for issue_file in issue_files:
        series = detect_series_from_path(issue_file)
        records = parse_issue_records(issue_file)

        for rec in records:
            context_field, context = pick_context_field(rec)
            analyses = rec.get("image_analyses")
            if not isinstance(analyses, list):
                continue

            repo = str(rec.get("repo") or "")
            rec_id = str(rec.get("id") or rec.get("issue_number") or "")

            for analysis in analyses:
                if not isinstance(analysis, dict):
                    continue

                status = str(analysis.get("status") or "")
                image_url = str(analysis.get("image_url") or "")
                desc = str(analysis.get("description") or "").strip()
                ocr = str(analysis.get("ocr_text") or "").strip()
                err = str(analysis.get("error") or "").strip()

                if status != "ok":
                    # Analyses that failed/are unavailable get an automatic
                    # zero coherence score — there is no description to
                    # ground, so they cannot be trusted regardless of context.
                    score = 0.0
                    reliability = classify_score(score, cfg)
                    row = CoherenceRow(
                        source="issue_image",
                        series=series,
                        repo=repo,
                        record_id=rec_id,
                        image_or_figure_id="",
                        url_or_path=image_url,
                        status=status or "error",
                        context_field=context_field,
                        desc_len=len(desc),
                        ocr_len=len(ocr),
                        lexical_score=0.0,
                        semantic_score=0.0,
                        contradiction_prob=0.0,
                        desc_context_overlap=0.0,
                        ocr_context_overlap=0.0,
                        coherence_score=score,
                        reliability_class=reliability,
                        flag_low_coherence=1,
                        reason_codes="ANALYSIS_NOT_OK",
                        notes=f"analysis_error={err}" if err else "analysis_status_not_ok",
                    )
                    rows.append(row)
                    if limit > 0 and len(rows) >= limit:
                        return rows
                    continue

                desc_overlap = overlap_ratio(desc, context)
                ocr_overlap = overlap_ratio(ocr, context) if ocr else 0.0
                # Weight the description more than OCR text since OCR often
                # captures noisy/partial text (UI labels, error codes) that
                # overlaps context less reliably than a full description.
                lexical_score = 0.7 * desc_overlap + 0.3 * ocr_overlap if (desc and ocr) else desc_overlap
                semantic_score = semantic_scorer.score(desc, context)
                contradiction_prob = nli_scorer.contradiction_probability(context, desc)
                score = compute_final_score(lexical_score, semantic_score, contradiction_prob, cfg)
                reliability = classify_score(score, cfg)

                notes = ""
                reasons: list[str] = []
                if not context:
                    notes = "missing_context"
                    reasons.append("NO_CONTEXT_FOUND")
                elif len(desc) < 20:
                    notes = "very_short_description"
                    reasons.append("VERY_SHORT_DESCRIPTION")

                if lexical_score < cfg.threshold_low:
                    reasons.append("LOW_LEXICAL_GROUNDING")

                if semantic_score is not None and semantic_score < cfg.semantic_alert_threshold:
                    reasons.append("LOW_SEMANTIC_SIMILARITY")

                if contradiction_prob is not None and contradiction_prob >= cfg.contradiction_alert_threshold:
                    reasons.append("HIGH_CONTRADICTION")

                if semantic_score is None:
                    reasons.append("SEMANTIC_SKIPPED")
                if contradiction_prob is None:
                    reasons.append("NLI_SKIPPED")

                row = CoherenceRow(
                    source="issue_image",
                    series=series,
                    repo=repo,
                    record_id=rec_id,
                    image_or_figure_id="",
                    url_or_path=image_url,
                    status=status,
                    context_field=context_field,
                    desc_len=len(desc),
                    ocr_len=len(ocr),
                    lexical_score=round(lexical_score, 4),
                    semantic_score=round(semantic_score or 0.0, 4),
                    contradiction_prob=round(contradiction_prob or 0.0, 4),
                    desc_context_overlap=round(desc_overlap, 4),
                    ocr_context_overlap=round(ocr_overlap, 4),
                    coherence_score=round(score, 4),
                    reliability_class=reliability,
                    flag_low_coherence=1 if score < cfg.threshold_low else 0,
                    reason_codes="|".join(sorted(set(reasons))),
                    notes=notes,
                )
                rows.append(row)

                if limit > 0 and len(rows) >= limit:
                    return rows

    return rows


def load_pdf_tasks_map(task_files: list[Path]) -> dict[str, dict[str, Any]]:
    """Load and index PDF figure extraction tasks by `image_id` for context lookup.

    Args:
        task_files: JSONL files matching `--pdf-task-glob`, each line a task
            dict with an `image_id` and `page_context_text`.

    Returns:
        Dict mapping `image_id` (as string) to its task dict. Malformed JSON
        lines and entries without an `image_id` are silently skipped.
    """
    out: dict[str, dict[str, Any]] = {}
    for path in task_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            fig_id = str(item.get("image_id") or "")
            if not fig_id:
                continue
            out[fig_id] = item
    return out


def evaluate_pdf_figure_coherence(
    descriptions_file: Path,
    task_files: list[Path],
    cfg: ScoringConfig,
    semantic_scorer: SemanticScorer,
    nli_scorer: NLIContradictionScorer,
    limit: int,
) -> list[CoherenceRow]:
    """Score every PDF figure description against its source page context.

    Args:
        descriptions_file: JSON file mapping `image_id -> description` text.
        task_files: JSONL task files providing `page_context_text` per `image_id`
            (joined via `load_pdf_tasks_map`).
        cfg: Scoring configuration (weights/thresholds).
        semantic_scorer: Semantic similarity scorer.
        nli_scorer: Contradiction probability scorer.
        limit: Max rows to produce (0 = unlimited); typically the remaining
            budget after issue-image rows have already consumed part of a
            shared `--limit`.

    Returns:
        List of `CoherenceRow` entries, one per figure description. Returns
        an empty list if the descriptions file is missing or not a dict.
        Descriptions containing "UNAVAILABLE" or starting with "[" (Alfred
        placeholder markers) get an automatic zero score.
    """
    rows: list[CoherenceRow] = []

    if not descriptions_file.exists():
        return rows

    descriptions = json.loads(descriptions_file.read_text(encoding="utf-8"))
    if not isinstance(descriptions, dict):
        return rows

    tasks_map = load_pdf_tasks_map(task_files)

    for fig_id, desc_raw in descriptions.items():
        desc = str(desc_raw or "").strip()
        task = tasks_map.get(str(fig_id), {})

        repo = str(task.get("repo") or "")
        page_context = str(task.get("page_context_text") or "")
        image_path = str(task.get("image_path") or "")

        # Placeholder/unavailable descriptions carry no grounded information,
        # so short-circuit with a zero score rather than scoring them normally.
        is_placeholder = "UNAVAILABLE" in desc.upper() or desc.startswith("[")
        if is_placeholder:
            score = 0.0
            reliability = classify_score(score, cfg)
            row = CoherenceRow(
                source="pdf_figure",
                series="unknown",
                repo=repo,
                record_id="",
                image_or_figure_id=str(fig_id),
                url_or_path=image_path,
                status="placeholder",
                context_field="page_context_text",
                desc_len=len(desc),
                ocr_len=0,
                lexical_score=0.0,
                semantic_score=0.0,
                contradiction_prob=0.0,
                desc_context_overlap=0.0,
                ocr_context_overlap=0.0,
                coherence_score=0.0,
                reliability_class=reliability,
                flag_low_coherence=1,
                reason_codes="DESCRIPTION_UNAVAILABLE",
                notes="description_unavailable",
            )
            rows.append(row)
            if limit > 0 and len(rows) >= limit:
                return rows
            continue

        desc_overlap = overlap_ratio(desc, page_context)
        lexical_score = desc_overlap
        semantic_score = semantic_scorer.score(desc, page_context)
        contradiction_prob = nli_scorer.contradiction_probability(page_context, desc)
        score = compute_final_score(lexical_score, semantic_score, contradiction_prob, cfg)
        reliability = classify_score(score, cfg)

        notes = ""
        reasons: list[str] = []
        if not task:
            notes = "missing_task_context"
            reasons.append("MISSING_TASK_CONTEXT")
        elif len(desc) < 20:
            notes = "very_short_description"
            reasons.append("VERY_SHORT_DESCRIPTION")

        if lexical_score < cfg.threshold_low:
            reasons.append("LOW_LEXICAL_GROUNDING")
        if semantic_score is not None and semantic_score < cfg.semantic_alert_threshold:
            reasons.append("LOW_SEMANTIC_SIMILARITY")
        if contradiction_prob is not None and contradiction_prob >= cfg.contradiction_alert_threshold:
            reasons.append("HIGH_CONTRADICTION")
        if semantic_score is None:
            reasons.append("SEMANTIC_SKIPPED")
        if contradiction_prob is None:
            reasons.append("NLI_SKIPPED")

        row = CoherenceRow(
            source="pdf_figure",
            series="unknown",
            repo=repo,
            record_id="",
            image_or_figure_id=str(fig_id),
            url_or_path=image_path,
            status="ok",
            context_field="page_context_text",
            desc_len=len(desc),
            ocr_len=0,
            lexical_score=round(lexical_score, 4),
            semantic_score=round(semantic_score or 0.0, 4),
            contradiction_prob=round(contradiction_prob or 0.0, 4),
            desc_context_overlap=round(desc_overlap, 4),
            ocr_context_overlap=0.0,
            coherence_score=round(score, 4),
            reliability_class=reliability,
            flag_low_coherence=1 if score < cfg.threshold_low else 0,
            reason_codes="|".join(sorted(set(reasons))),
            notes=notes,
        )
        rows.append(row)

        if limit > 0 and len(rows) >= limit:
            return rows

    return rows


def write_csv(path: Path, rows: list[CoherenceRow]) -> None:
    """Write coherence rows to a CSV report, creating parent directories as needed.

    Args:
        path: Output CSV path.
        rows: Rows to write (order preserved).

    Side effects:
        Creates `path.parent` if missing and overwrites `path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source",
                "series",
                "repo",
                "record_id",
                "image_or_figure_id",
                "url_or_path",
                "status",
                "context_field",
                "desc_len",
                "ocr_len",
                "lexical_score",
                "semantic_score",
                "contradiction_prob",
                "desc_context_overlap",
                "ocr_context_overlap",
                "coherence_score",
                "reliability_class",
                "flag_low_coherence",
                "reason_codes",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def summarize(rows: list[CoherenceRow]) -> dict[str, Any]:
    """Aggregate coherence rows into overall and per-source summary statistics.

    Args:
        rows: All evaluated `CoherenceRow` entries (issue images + PDF figures).

    Returns:
        Dict with `total_checked`, `low_coherence` count/rate, and a
        `by_source` breakdown (per "issue_image"/"pdf_figure" source) of
        count, low-coherence rate, average score, and reliability class
        distribution. Used both for the console summary and the JSON report.
    """
    total = len(rows)
    low = sum(r.flag_low_coherence for r in rows)
    by_source: dict[str, dict[str, Any]] = {}

    for src in {r.source for r in rows}:
        subset = [r for r in rows if r.source == src]
        n = len(subset)
        low_n = sum(r.flag_low_coherence for r in subset)
        avg = round(sum(r.coherence_score for r in subset) / n, 4) if n else 0.0
        classes = {
            "EXCELLENT": sum(1 for r in subset if r.reliability_class == "EXCELLENT"),
            "BON": sum(1 for r in subset if r.reliability_class == "BON"),
            "ACCEPTABLE": sum(1 for r in subset if r.reliability_class == "ACCEPTABLE"),
            "INSUFFISANT": sum(1 for r in subset if r.reliability_class == "INSUFFISANT"),
        }
        by_source[src] = {
            "count": n,
            "low_coherence": low_n,
            "low_coherence_rate": round((low_n / n), 4) if n else 0.0,
            "avg_coherence_score": avg,
            "class_distribution": classes,
        }

    return {
        "total_checked": total,
        "low_coherence": low,
        "low_coherence_rate": round((low / total), 4) if total else 0.0,
        "by_source": by_source,
    }


def main() -> None:
    """Parse CLI args, evaluate issue-image and PDF-figure coherence, and write reports.

    Side effects:
        Writes the CSV report to `--output-csv` and the summary JSON to
        `--output-summary-json`; prints a console summary. Raises
        `ValueError` if threshold arguments are out of range or inconsistently
        ordered.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate Alfred output coherence against source context for issue images and PDF figures."
        )
    )
    parser.add_argument(
        "--issue-glob",
        default="datasets/07_delivery/st_ready/by_series/**/issues_json/st_ready_issues_with_images_*.json",
        help="Glob for enriched issue JSON files",
    )
    parser.add_argument(
        "--pdf-descriptions",
        default="data/pdf_image_descriptions.json",
        help="Path to PDF figure descriptions map",
    )
    parser.add_argument(
        "--pdf-task-glob",
        default="data/pdf_image_tasks_*.jsonl",
        help="Glob for PDF task files containing page_context_text",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.12,
        help="Low coherence threshold below which rows are flagged",
    )
    parser.add_argument(
        "--semantic-mode",
        choices=["off", "lite", "auto", "required"],
        default="lite",
        help="Semantic scorer mode: off, lite (no deps), auto (fallback if unavailable), or required",
    )
    parser.add_argument(
        "--nli-mode",
        choices=["off", "lite", "auto", "required"],
        default="lite",
        help="NLI contradiction mode: off, lite (no deps), auto (fallback if unavailable), or required",
    )
    parser.add_argument(
        "--semantic-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-transformers model for semantic similarity",
    )
    parser.add_argument(
        "--nli-model",
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        help="NLI model for contradiction probability",
    )
    parser.add_argument(
        "--alpha-lexical",
        type=float,
        default=0.4,
        help="Weight of lexical grounding in final score",
    )
    parser.add_argument(
        "--beta-semantic",
        type=float,
        default=0.6,
        help="Weight of semantic similarity in final score",
    )
    parser.add_argument(
        "--gamma-contradiction",
        type=float,
        default=0.8,
        help="Contradiction penalty strength (final score multiplied by 1-gamma*p_contradiction)",
    )
    parser.add_argument(
        "--semantic-alert-threshold",
        type=float,
        default=0.55,
        help="Reason code threshold for low semantic similarity",
    )
    parser.add_argument(
        "--contradiction-alert-threshold",
        type=float,
        default=0.5,
        help="Reason code threshold for high contradiction probability",
    )
    parser.add_argument(
        "--excellent-threshold",
        type=float,
        default=0.95,
        help="Minimum final score for class EXCELLENT",
    )
    parser.add_argument(
        "--good-threshold",
        type=float,
        default=0.85,
        help="Minimum final score for class BON",
    )
    parser.add_argument(
        "--acceptable-threshold",
        type=float,
        default=0.70,
        help="Minimum final score for class ACCEPTABLE",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of rows to evaluate",
    )
    parser.add_argument(
        "--output-csv",
        default="docs/evaluation/alfred_coherence_report.csv",
        help="Output CSV path",
    )
    parser.add_argument(
        "--output-summary-json",
        default="docs/evaluation/alfred_coherence_summary.json",
        help="Output summary JSON path",
    )
    args = parser.parse_args()

    if not (0.0 <= args.threshold <= 1.0):
        raise ValueError("--threshold must be in [0, 1]")
    if not (0.0 <= args.excellent_threshold <= 1.0):
        raise ValueError("--excellent-threshold must be in [0, 1]")
    if not (0.0 <= args.good_threshold <= 1.0):
        raise ValueError("--good-threshold must be in [0, 1]")
    if not (0.0 <= args.acceptable_threshold <= 1.0):
        raise ValueError("--acceptable-threshold must be in [0, 1]")
    if not (args.excellent_threshold >= args.good_threshold >= args.acceptable_threshold):
        raise ValueError("Threshold ordering must satisfy excellent >= good >= acceptable")

    cfg = ScoringConfig(
        alpha_lexical=args.alpha_lexical,
        beta_semantic=args.beta_semantic,
        gamma_contradiction=args.gamma_contradiction,
        threshold_low=args.threshold,
        contradiction_alert_threshold=args.contradiction_alert_threshold,
        semantic_alert_threshold=args.semantic_alert_threshold,
        excellent_threshold=args.excellent_threshold,
        good_threshold=args.good_threshold,
        acceptable_threshold=args.acceptable_threshold,
    )

    semantic_scorer = SemanticScorer(args.semantic_model, args.semantic_mode)
    nli_scorer = NLIContradictionScorer(args.nli_model, args.nli_mode)

    issue_files = sorted((PROJECT_ROOT / ".").glob(args.issue_glob))
    pdf_desc_path = PROJECT_ROOT / args.pdf_descriptions
    pdf_task_files = sorted((PROJECT_ROOT / ".").glob(args.pdf_task_glob))

    rows_issue = evaluate_issue_image_coherence(
        issue_files=issue_files,
        cfg=cfg,
        semantic_scorer=semantic_scorer,
        nli_scorer=nli_scorer,
        limit=args.limit,
    )

    remaining = 0
    if args.limit > 0:
        remaining = max(args.limit - len(rows_issue), 0)

    rows_pdf = evaluate_pdf_figure_coherence(
        descriptions_file=pdf_desc_path,
        task_files=pdf_task_files,
        cfg=cfg,
        semantic_scorer=semantic_scorer,
        nli_scorer=nli_scorer,
        limit=remaining if args.limit > 0 else 0,
    )

    rows = rows_issue + rows_pdf

    output_csv = PROJECT_ROOT / args.output_csv
    write_csv(output_csv, rows)

    summary = summarize(rows)
    summary["scoring_config"] = {
        "alpha_lexical": cfg.alpha_lexical,
        "beta_semantic": cfg.beta_semantic,
        "gamma_contradiction": cfg.gamma_contradiction,
        "threshold_low": cfg.threshold_low,
        "excellent_threshold": cfg.excellent_threshold,
        "good_threshold": cfg.good_threshold,
        "acceptable_threshold": cfg.acceptable_threshold,
        "semantic_mode": args.semantic_mode,
        "nli_mode": args.nli_mode,
        "semantic_model": args.semantic_model,
        "nli_model": args.nli_model,
        "semantic_available": semantic_scorer.available,
        "nli_available": nli_scorer.available,
        "semantic_info": semantic_scorer.error_message,
        "nli_info": nli_scorer.error_message,
    }
    output_summary = PROJECT_ROOT / args.output_summary_json
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Alfred Coherence Validation ===")
    print(f"Issue files scanned: {len(issue_files)}")
    print(f"PDF task files scanned: {len(pdf_task_files)}")
    print(f"Semantic scorer available: {semantic_scorer.available} ({semantic_scorer.error_message})")
    print(f"NLI scorer available: {nli_scorer.available} ({nli_scorer.error_message})")
    print(f"Rows evaluated: {summary['total_checked']}")
    print(f"Low coherence: {summary['low_coherence']} ({summary['low_coherence_rate']*100:.1f}%)")
    for src, data in summary["by_source"].items():
        print(
            f"- {src}: count={data['count']}, low={data['low_coherence']} "
            f"({data['low_coherence_rate']*100:.1f}%), avg_score={data['avg_coherence_score']}"
        )
    print(f"CSV report: {output_csv}")
    print(f"Summary: {output_summary}")


if __name__ == "__main__":
    main()
