"""
J7.3: PDF and Excel report generation from report data.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """
    Generates reports in PDF (via reportlab or fallback HTML) and Excel/CSV formats.
    """

    OUTPUT_DIR = os.getenv("REPORT_OUTPUT_DIR", "/tmp/kg_rag_reports")

    def __init__(self) -> None:
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    async def generate(
        self,
        report_name: str,
        data_sections: List[Dict[str, Any]],
        fmt: str = "pdf",
    ) -> str:
        slug = report_name.replace(" ", "_").replace("/", "-")
        ts   = int(time.time())
        if fmt == "csv":
            return self._generate_csv(slug, ts, data_sections)
        if fmt == "json":
            return self._generate_json(slug, ts, data_sections)
        # Default: try PDF, fall back to HTML
        try:
            return self._generate_pdf(slug, ts, report_name, data_sections)
        except ImportError:
            logger.info("reportlab 未安装，生成 HTML 报告")
            return self._generate_html(slug, ts, report_name, data_sections)

    def _generate_pdf(
        self,
        slug: str, ts: int,
        title: str,
        sections: List[Dict[str, Any]],
    ) -> str:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib import colors
        from reportlab.lib.units import cm

        path = os.path.join(self.OUTPUT_DIR, f"{slug}_{ts}.pdf")
        doc  = SimpleDocTemplate(path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                                 topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=12)
        head_style  = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=16, spaceAfter=8)

        story = [Paragraph(title, title_style), Spacer(1, 0.5*cm)]

        for sec in sections:
            rows = sec.get("rows", [])
            if not rows:
                continue
            cols = list(rows[0].keys()) if rows else []
            story.append(Paragraph(sec.get("source", "数据"), head_style))

            table_data = [cols] + [[str(r.get(c, "")) for c in cols] for r in rows[:50]]
            t = Table(table_data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTSIZE",    (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#1F2937"), colors.HexColor("#111827")]),
                ("TEXTCOLOR",   (0, 1), (-1, -1), colors.HexColor("#D1D5DB")),
                ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#374151")),
                ("PADDING",     (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.3*cm))

        doc.build(story)
        return path

    def _generate_html(
        self,
        slug: str, ts: int,
        title: str,
        sections: List[Dict[str, Any]],
    ) -> str:
        path = os.path.join(self.OUTPUT_DIR, f"{slug}_{ts}.html")
        out  = [f"<html><head><meta charset='utf-8'><title>{title}</title>",
                "<style>body{background:#111;color:#eee;font-family:sans-serif;padding:2rem}",
                "table{border-collapse:collapse;width:100%;margin-bottom:2rem}",
                "th{background:#1e3a5f;padding:8px;text-align:left}",
                "td{padding:6px;border-bottom:1px solid #374151;font-size:13px}</style></head><body>",
                f"<h1>{title}</h1>"]
        for sec in sections:
            rows = sec.get("rows", [])
            if not rows:
                continue
            cols = list(rows[0].keys())
            out.append(f"<h2>{sec.get('source', '数据')}</h2><table>")
            out.append("<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>")
            for row in rows[:100]:
                out.append("<tr>" + "".join(f"<td>{row.get(c,'')}</td>" for c in cols) + "</tr>")
            out.append("</table>")
        out.append("</body></html>")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        return path

    def _generate_csv(
        self, slug: str, ts: int, sections: List[Dict[str, Any]]
    ) -> str:
        path = os.path.join(self.OUTPUT_DIR, f"{slug}_{ts}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            for sec in sections:
                rows = sec.get("rows", [])
                if not rows:
                    continue
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        return path

    def _generate_json(
        self, slug: str, ts: int, sections: List[Dict[str, Any]]
    ) -> str:
        path = os.path.join(self.OUTPUT_DIR, f"{slug}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sections, f, ensure_ascii=False, indent=2, default=str)
        return path


pdf_generator = PDFReportGenerator()
