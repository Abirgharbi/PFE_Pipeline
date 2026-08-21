"""
Convert the flat CSV test suite (Question;Answer;Tags) into a formatted, human-friendly
Excel workbook for manual QA grading of the knowledge base.

This is the v1 (legacy) test suite builder: it does not read any pipeline JSON
dataset directly, it only reformats an already-generated CSV file.

Input:
    datasets/07_delivery/st_ready/all_series_test_suite_50q.csv
    (semicolon-delimited, quoted fields: Question;Answer;Tags)

Output:
    datasets/07_delivery/st_ready/all_series_test_suite_50q.xlsx
    Sheet "Test Suite 50Q All Series" with columns:
      A = Question (width 60), B = Answer (width 80), C = Tags (width 15)
    Header row is bold/white-on-blue, all cells wrap text and have thin borders,
    and the header row is frozen for easier scrolling.

Usage:
    python pipeline_Automation/test_suites/build_all_series_test_suite_xlsx.py
"""

import csv
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    raise SystemExit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "all_series_test_suite_50q.csv"
XLSX_PATH = PROJECT_ROOT / "datasets" / "07_delivery" / "st_ready" / "all_series_test_suite_50q.xlsx"


def main():
    """Read the source CSV and write a styled .xlsx workbook next to it.

    Reads ``CSV_PATH`` row by row, copies every cell into the worksheet at the
    same row/column position, applies header/body styling, and saves to
    ``XLSX_PATH``.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Suite 50Q All Series"

    # Styles
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    wrap_align = Alignment(wrap_text=True, vertical="top")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Column widths
    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 80
    ws.column_dimensions["C"].width = 15

    # Read CSV
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        for row_idx, row in enumerate(reader, start=1):
            for col_idx, value in enumerate(row, start=1):
                # Strip stray double quotes: the source CSV quotes long text fields
                # containing the ';' delimiter, and csv.reader leaves literal quote
                # characters in the value when they are not the field delimiter quote.
                cell = ws.cell(row=row_idx, column=col_idx, value=value.strip('"'))
                cell.alignment = wrap_align
                cell.border = thin_border

                # Row 1 is the header: style it distinctly so graders can
                # visually separate it from data rows.
                if row_idx == 1:
                    cell.font = header_font_white
                    cell.fill = header_fill
                else:
                    cell.font = Font(size=10)

    # Keep the header row visible while scrolling through many questions.
    ws.freeze_panes = "A2"

    wb.save(XLSX_PATH)
    print(f"Created: {XLSX_PATH}")
    print(f"Total rows: {ws.max_row - 1} questions")


if __name__ == "__main__":
    main()
