# services/parsing — 文档解析模块

## 职责

从 PDF / DOCX 中提取结构化内容（元数据、章节、目录、表格），供 RAG 检索链路使用。

## 文件地图

| 文件 | 职责 |
|------|------|
| `parser.py` | 公共入口：`parse_document()` 整合所有子模块 |
| `parser_meta.py` | 提取封面元数据（文档编号、版本、发布日期）；`clean_content()` 过滤页码/页眉 |
| `parser_sections.py` | 按章节号切分正文：`extract_sections(pdf_path, doc_id)` |
| `parser_heading.py` | 章节标题识别正则与过滤逻辑 |
| `parser_toc.py` | 目录锚点提取与目录噪声过滤 |
| `parser_tables.py` | pdfplumber 表格提取，输出 `list[list[str]]` |
| `parser_patterns.py` | 共享正则常量（章节号、日期、页码等） |
| `parser_office.py` | DOCX/Office 格式解析适配 |
| `ocr_engine.py` | PaddleOCR 封装；`is_struct_available()` 探测环境 |
| `ocr_parser.py` | OCR 路径的全文提取 |
| `docx_parser.py` | python-docx 段落/表格抽取 |
| `validator.py` | 上传前 PDF 格式校验 |

## 调用流程

```
parse_document(path, doc_id)
  ├── parser_meta.extract_meta()          # 封面信息
  ├── parser_sections.extract_sections()  # 章节切分
  │     ├── parser_toc  (目录锚点)
  │     └── parser_heading (标题识别)
  └── parser_tables (表格提取，按需)
```

## 关键设计决策

- **目录噪声过滤**：CPS 规范文档目录页与正文重复，`_filter_headings_with_toc_anchors` 用 TOC 锚点集合筛除错误章节。
- **双语标题合并**：中英文标题换行跨行（`_merge_wrapped_heading`），以未闭合括号为信号。
- **pdfplumber 优先**：有结构 PDF 直接用 pdfplumber；纯扫描件走 `ocr_engine`。
- **monkeypatch 注意**：测试中 patch `pdfplumber.open` 必须指向 `parser_sections.pdfplumber.open`，不是 `parser.pdfplumber.open`。

## 测试

```bash
pytest tests/test_parser.py -v
```
