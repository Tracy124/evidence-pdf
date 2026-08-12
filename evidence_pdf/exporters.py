import csv
import json
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pypdf import PdfReader, PdfWriter

from .models import Evidence


COLUMNS = [
    ("index", "序号"), ("company", "企业名称"), ("indicator", "指标"),
    ("value_candidate", "数值候选（待复核）"), ("source_filename", "来源文件名"),
    ("page_number", "页码"), ("language", "语种"), ("year", "年份"),
    ("document_type", "原文件类型"), ("matched_terms", "命中词"),
    ("score", "匹配分"), ("excerpt", "证据片段"),
    ("evidence_filename", "证据文件名"),
]


def extract_single_page(pdf_bytes: bytes, page_number: int) -> bytes:
    reader = PdfReader(BytesIO(pdf_bytes))
    if page_number < 1 or page_number > len(reader.pages):
        raise ValueError(f"页码超出范围：{page_number}")
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def build_excel(results: list[Evidence]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "提取结果"
    ws.append([label for _, label in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for result in results:
        record = result.to_record()
        ws.append([record[key] for key, _ in COLUMNS])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    widths = [8, 18, 30, 22, 28, 8, 10, 10, 16, 24, 10, 70, 42]
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def build_word(results: list[Evidence]) -> bytes:
    doc = Document()
    styles = doc.styles
    styles["Normal"].font.name = "Arial"
    styles["Normal"].font.size = Pt(10)
    doc.add_heading("PDF 证据提取结果", level=0)
    doc.add_paragraph("说明：数值为自动识别候选，正式使用前请结合证据页人工复核。")
    for result in results:
        doc.add_heading(f"{result.index:03d}  {result.company} - 第 {result.page_number} 页", level=1)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        items = [
            ("指标", result.indicator), ("数值候选", result.value_candidate),
            ("来源文件", result.source_filename), ("证据文件", result.evidence_filename),
            ("命中词", result.matched_terms), ("匹配分", str(result.score)),
            ("证据片段", result.excerpt),
        ]
        for label, value in items:
            cells = table.add_row().cells
            cells[0].text, cells[1].text = label, value
    output = BytesIO()
    doc.save(output)
    return output.getvalue()


def build_csv(results: list[Evidence]) -> bytes:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([label for _, label in COLUMNS])
    for result in results:
        record = result.to_record()
        writer.writerow([record[key] for key, _ in COLUMNS])
    return output.getvalue().encode("utf-8-sig")


def build_export_bundle(results: list[Evidence], source_pdfs: dict[str, bytes]) -> dict[str, bytes]:
    files = {
        "提取结果.xlsx": build_excel(results),
        "证据清单.docx": build_word(results),
        "提取结果.csv": build_csv(results),
    }
    for result in results:
        files[f"证据页/{result.evidence_filename}"] = extract_single_page(
            source_pdfs[result.source_filename], result.page_number
        )
    manifest = {
        "result_count": len(results),
        "notice": "自动提取结果仅供辅助定位，请人工复核证据原页。",
        "files": [result.to_record() for result in results],
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    files["证据提取结果包.zip"] = zip_buffer.getvalue()
    return files
