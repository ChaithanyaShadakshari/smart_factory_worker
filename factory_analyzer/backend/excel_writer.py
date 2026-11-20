"""
excel_writer.py – Export AI analyzer results to Excel.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


def _apply_header_style(cell) -> None:
    cell.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    cell.fill = PatternFill(start_color="1A1A2E", end_color="1A1A2E", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _get_status_fill(status: str) -> PatternFill | None:
    if status == "RED":
        return PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")
    if status == "AMBER":
        return PatternFill(start_color="FFF3CC", end_color="FFF3CC", fill_type="solid")
    if status == "GREEN":
        return PatternFill(start_color="CCFFCC", end_color="CCFFCC", fill_type="solid")
    return None


def generate_excel_report(data: list[dict]) -> Path:
    """
    Generate the scorecard.xlsx output given the agent's payload.

    Returns the Path to the generated Excel file.
    """
    wb = Workbook()

    # ── Sheet 1: Efficiency Report ───────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Efficiency Report"

    headers = ["Worker ID", "Division", "Shift", "Score", "Rank", "Status", "Notes"]
    ws1.append(headers)

    # Style headers and row height
    ws1.row_dimensions[1].height = 22
    for col_idx in range(1, len(headers) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        _apply_header_style(cell)

    # Column widths
    ws1.column_dimensions["A"].width = 12
    ws1.column_dimensions["B"].width = 14
    ws1.column_dimensions["C"].width = 12
    ws1.column_dimensions["D"].width = 10
    ws1.column_dimensions["E"].width = 8
    ws1.column_dimensions["F"].width = 10
    ws1.column_dimensions["G"].width = 55

    # Freeze row 1
    ws1.freeze_panes = "A2"

    # Write data
    for row_idx, worker in enumerate(data, start=2):
        score = worker.get("score", 0.0)
        status = worker.get("status", "")

        row_data = [
            worker.get("worker_id", ""),
            worker.get("division", ""),
            worker.get("shift", ""),
            score,
            worker.get("rank", ""),
            status,
            worker.get("narrative", ""),
        ]
        ws1.append(row_data)

        # Apply basic row styling
        fill = _get_status_fill(status)
        for col_idx in range(1, len(row_data) + 1):
            cell = ws1.cell(row=row_idx, column=col_idx)
            cell.font = Font(name="Calibri", size=11)
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=col_idx == 7)

            if col_idx == 4:  # Score (D)
                cell.number_format = "0.0"
                cell.alignment = Alignment(horizontal="right", vertical="center")
                if fill:
                    cell.fill = fill
            if col_idx == 6:  # Status (F)
                if fill:
                    cell.fill = fill

    # ── Sheet 2: Summary ──────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Summary")

    ws2.append(["Session Summary"])
    title_cell = ws2.cell(row=1, column=1)
    title_cell.font = Font(name="Calibri", size=14, bold=True)
    ws2.append([])

    summary_headers = ["Total Workers", "Avg Score", "RED count", "AMBER count", "GREEN count"]
    ws2.append(summary_headers)
    for col_idx in range(1, len(summary_headers) + 1):
        _apply_header_style(ws2.cell(row=3, column=col_idx))

    if data:
        avg_score = sum(w.get("score", 0) for w in data) / len(data)
    else:
        avg_score = 0.0

    red_cnt   = sum(1 for w in data if w.get("status") == "RED")
    amber_cnt = sum(1 for w in data if w.get("status") == "AMBER")
    green_cnt = sum(1 for w in data if w.get("status") == "GREEN")

    ws2.append([len(data), round(avg_score, 1), red_cnt, amber_cnt, green_cnt])

    # Widths
    for col_letter in ["A", "B", "C", "D", "E"]:
        ws2.column_dimensions[col_letter].width = 15

    # ── Save ──────────────────────────────────────────────────────────────────
    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "scorecard.xlsx"
    wb.save(out_path)
    return out_path
