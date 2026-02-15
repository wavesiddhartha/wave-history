from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 46
TOP_MARGIN = 760
LINE_HEIGHT = 14
MAX_CHARS_PER_LINE = 94
MAX_LINES_PER_PAGE = 48


def _safe_line(text: str) -> str:
    # Keep PDF text stream latin-1 safe while preserving readability.
    return text.encode("latin-1", "replace").decode("latin-1")


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _to_lines(report: dict[str, Any]) -> list[str]:
    details = report.get("details") if isinstance(report.get("details"), dict) else {}
    date_text = str(report.get("date") or datetime.now().date().isoformat())
    model = str(report.get("model") or "Unknown model")
    source_events = int(report.get("source_events") or 0)
    generated_raw = str(report.get("generated_at") or datetime.now().isoformat())
    try:
        generated_at = datetime.fromisoformat(generated_raw).strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        generated_at = generated_raw

    lines: list[str] = [
        "Wave Internet Intelligence Report",
        f"Date: {date_text}",
        f"Generated At: {generated_at}",
        f"Model: {model}",
        f"Source Events: {source_events}",
        "",
        "Executive Summary",
    ]

    summary = str(report.get("summary") or "No summary available.").strip()
    lines.extend(textwrap.wrap(summary, width=MAX_CHARS_PER_LINE) or ["No summary available."])
    lines.extend(["", "Examination Result"])
    exam_grade = str(details.get("examination_grade") or "-").strip()
    exam_score = details.get("overall_score")
    exam_score_text = "-"
    if isinstance(exam_score, (int, float)):
        exam_score_text = str(int(round(exam_score)))
    lines.append(f"Grade: {exam_grade}")
    lines.append(f"Overall Score: {exam_score_text}/100")
    exam_summary = str(details.get("examination_summary") or "").strip()
    lines.extend(textwrap.wrap(exam_summary, width=MAX_CHARS_PER_LINE) or ["No examination summary available."])
    lines.extend(["", "Detailed Narrative"])

    narrative = str(details.get("narrative") or "").strip()
    lines.extend(textwrap.wrap(narrative, width=MAX_CHARS_PER_LINE) or ["No narrative available."])
    lines.extend(["", "Deep Research Paper"])
    deep_paper = str(details.get("deep_research_paper") or "").strip()
    lines.extend(textwrap.wrap(deep_paper, width=MAX_CHARS_PER_LINE) or ["No deep research paper available."])

    section_map = [
        ("Scorecard", _as_list(details.get("scorecard"))),
        ("Detailed Findings", _as_list(details.get("detailed_findings"))),
        ("Important Highlights", _as_list(details.get("important_highlights"))),
        ("Key Facts", _as_list(details.get("key_facts"))),
        ("Highlights", _as_list(report.get("highlights"))),
        ("Behavior Patterns", _as_list(details.get("behavior_patterns"))),
        ("Time Insights", _as_list(details.get("time_insights"))),
        ("Category Insights", _as_list(details.get("category_insights"))),
        ("Intent Signals", _as_list(details.get("intent_signals"))),
        ("Focus Gaps", _as_list(details.get("focus_gaps"))),
        ("7-Day Action Plan", _as_list(details.get("action_plan_7d"))),
        ("Methodology Notes", _as_list(details.get("methodology_notes"))),
        ("Risk Flags", _as_list(report.get("risk_flags"))),
        ("Recommendations", _as_list(details.get("recommendations"))),
    ]

    for title, items in section_map:
        lines.extend(["", title])
        if not items:
            lines.append("- None")
            continue
        for item in items:
            wrapped = textwrap.wrap(item, width=MAX_CHARS_PER_LINE - 2) or [item]
            lines.append(f"- {wrapped[0]}")
            for continuation in wrapped[1:]:
                lines.append(f"  {continuation}")

    return [_safe_line(line) for line in lines]


def _chunk_lines(lines: list[str], chunk_size: int) -> list[list[str]]:
    if not lines:
        return [[]]
    chunks: list[list[str]] = []
    for idx in range(0, len(lines), chunk_size):
        chunks.append(lines[idx : idx + chunk_size])
    return chunks


def _build_pdf(lines: list[str]) -> bytes:
    pages = _chunk_lines(lines, MAX_LINES_PER_PAGE)
    objects: list[str] = []

    def add_object(body: str) -> int:
        objects.append(body)
        return len(objects)

    catalog_id = add_object("<< /Type /Catalog /Pages 0 0 R >>")
    pages_id = add_object("<< /Type /Pages /Kids [] /Count 0 >>")
    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_object_ids: list[int] = []

    for page_number, page_lines in enumerate(pages, start=1):
        content_commands = ["BT", f"/F1 11 Tf", f"{LEFT_MARGIN} {TOP_MARGIN} Td", f"{LINE_HEIGHT} TL"]
        for line in page_lines:
            escaped = _escape_pdf_text(line)
            content_commands.append(f"({escaped}) Tj")
            content_commands.append("T*")
        content_commands.extend(["T*", f"(Page {page_number}/{len(pages)}) Tj", "ET"])
        content_stream = "\n".join(content_commands)
        content_bytes = content_stream.encode("latin-1", "replace")
        content_id = add_object(
            f"<< /Length {len(content_bytes)} >>\nstream\n{content_stream}\nendstream"
        )
        page_id = add_object(
            "<< /Type /Page "
            f"/Parent {pages_id} 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_object_ids.append(page_id)

    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_object_ids)
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>"
    )

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(body.encode("latin-1", "replace"))
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    pdf.extend(trailer.encode("ascii"))
    return bytes(pdf)


def build_report_pdf(report: dict[str, Any]) -> bytes:
    lines = _to_lines(report)
    return _build_pdf(lines)
