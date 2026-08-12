from io import BytesIO

from pypdf import PdfReader

from .models import PageText


class PDFParseError(ValueError):
    pass


def read_pages(pdf_bytes: bytes) -> list[PageText]:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PDFParseError("PDF 已加密，无法读取") from exc
        return [
            PageText(page_number=i, text=(page.extract_text() or "").strip())
            for i, page in enumerate(reader.pages, start=1)
        ]
    except PDFParseError:
        raise
    except Exception as exc:
        raise PDFParseError(f"PDF 解析失败：{exc}") from exc
