import streamlit as st

from evidence_pdf.extractor import extract_evidence
from evidence_pdf.exporters import build_export_bundle
from evidence_pdf.parser import PDFParseError, read_pages
from evidence_pdf.utils import infer_meta, split_terms


st.set_page_config(page_title="EvidencePDF", page_icon="🔎", layout="wide")
st.title("EvidencePDF · 法律/财务文档证据提取")
st.caption("批量定位目标字段，保留原始证据页，并生成 Excel / Word / ZIP 结果包。所有处理均在当前运行环境完成。")

with st.sidebar:
    st.header("提取设置")
    raw_terms = st.text_area(
        "目标字段 / 同义词",
        "研发投入, 研发费用, R&D expenditure, research and development expenses",
        help="用逗号、分号或换行分隔。更具体的词通常能减少误报。",
    )
    max_pages = st.slider("每份文件最多保留证据页", 1, 10, 3)
    min_score = st.slider("最低匹配分", 1.0, 10.0, 2.0, 0.25)
    st.divider()
    st.subheader("默认元数据（可选）")
    company = st.text_input("企业名称")
    year = st.text_input("年份")
    document_type = st.text_input("文件类型", placeholder="年度报告")

uploads = st.file_uploader("上传企业文档 PDF", type=["pdf"], accept_multiple_files=True)

if st.button("开始提取", type="primary", disabled=not uploads, use_container_width=True):
    terms = split_terms(raw_terms)
    if not terms:
        st.error("请至少输入一个目标字段。")
        st.stop()

    all_results, source_pdfs, warnings = [], {}, []
    next_index = 1
    progress = st.progress(0, text="正在解析…")
    for pos, upload in enumerate(uploads, start=1):
        pdf_bytes = upload.getvalue()
        source_pdfs[upload.name] = pdf_bytes
        try:
            pages = read_pages(pdf_bytes)
            if pages and sum(bool(page.text.strip()) for page in pages) / len(pages) < 0.2:
                warnings.append(f"{upload.name}：大部分页面没有可提取文本，可能是扫描件，需要 OCR。")
            meta = infer_meta(upload.name, company, year, document_type)
            results = extract_evidence(
                pages, terms, meta, max_pages=max_pages,
                min_score=min_score, start_index=next_index,
            )
            if not results:
                warnings.append(f"{upload.name}：未找到达到阈值的页面。")
            all_results.extend(results)
            next_index += len(results)
        except PDFParseError as exc:
            warnings.append(f"{upload.name}：{exc}")
        progress.progress(pos / len(uploads), text=f"已处理 {pos}/{len(uploads)}")

    progress.empty()
    for warning in warnings:
        st.warning(warning)
    if not all_results:
        st.info("没有可导出的结果。请检查 PDF 是否含文本层，或补充同义词、降低匹配阈值。")
        st.stop()

    files = build_export_bundle(all_results, source_pdfs)
    st.session_state["evidence_results"] = all_results
    st.session_state["evidence_files"] = files
    st.success(f"完成：从 {len(uploads)} 份文档中找到 {len(all_results)} 个证据页候选。")

if "evidence_results" in st.session_state:
    results = st.session_state["evidence_results"]
    files = st.session_state["evidence_files"]
    st.subheader("候选结果")
    st.dataframe(
        [{
            "序号": r.index, "企业": r.company, "指标": r.indicator,
            "数值候选": r.value_candidate, "来源": r.source_filename,
            "页码": r.page_number, "匹配分": r.score, "命中词": r.matched_terms,
        } for r in results],
        hide_index=True, use_container_width=True,
    )
    for result in results:
        with st.expander(f"{result.index:03d} · {result.company} · 第 {result.page_number} 页"):
            st.write(result.excerpt)
            st.caption(f"证据文件：{result.evidence_filename}")
    c1, c2, c3 = st.columns(3)
    c1.download_button("下载完整 ZIP", files["证据提取结果包.zip"], "证据提取结果包.zip", "application/zip", use_container_width=True)
    c2.download_button("下载 Excel", files["提取结果.xlsx"], "提取结果.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    c3.download_button("下载 Word", files["证据清单.docx"], "证据清单.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)

st.divider()
st.caption("提示：该工具提供证据定位与整理，不替代专业判断。数值候选和来源页应由使用者复核。")
