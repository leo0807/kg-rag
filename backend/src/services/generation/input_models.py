"""
规范生成系统输入数据模型。
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class SectionOverride(BaseModel):
    """允许用户为某个章节提供自定义指令"""
    section_number: str
    custom_instruction: str = ""
    skip: bool = False


class GenerationInput(BaseModel):
    """创建生成任务时提交的完整输入"""

    # 基本信息
    spec_name:        str = Field(..., description="拟生成的规范名称，如 CPSXXXX 密封规范")
    spec_type:        str = Field(..., description="规范类型，如 密封/复合材料/紧固件")
    template_id:      str = Field(..., description="使用的模板 ID")

    # 输入源
    reference_docs:   list[str] = Field(default_factory=list, description="参考的现有 CPS 文档 ID 列表")
    test_data:        dict[str, Any] | None = Field(None, description="结构化试验数据")
    user_requirements:str = Field("", description="用户用自然语言描述的需求")
    target_application:str = Field("", description="目标应用场景描述")

    # 约束条件
    must_reference:   list[str] = Field(default_factory=list, description="必须引用的标准编号")
    must_include_sections: list[str] = Field(default_factory=list, description="必须包含的章节标题")

    # 高级选项
    section_overrides: list[SectionOverride] = Field(default_factory=list, description="章节级自定义指令")
    language:         str = Field("zh", description="输出语言，默认中文")
    style_reference:  str = Field("", description="风格参考的现有规范 ID")


class TestDataRow(BaseModel):
    """试验数据行，从 Excel/CSV 解析而来"""
    parameter:  str
    value:      str | float
    unit:       str = ""
    condition:  str = ""
    note:       str = ""


class ParsedTestData(BaseModel):
    """解析后的试验数据集"""
    source_file: str = ""
    rows:        list[TestDataRow] = []
    summary:     dict[str, Any] = {}


def parse_excel_test_data(file_bytes: bytes, filename: str) -> ParsedTestData:
    """
    解析上传的 Excel/CSV 文件为结构化试验数据。
    要求第一行为表头：参数名 | 数值 | 单位 | 测试条件 | 备注
    """
    import io
    rows: list[TestDataRow] = []

    try:
        if filename.endswith(".csv"):
            import csv
            reader = csv.DictReader(io.StringIO(file_bytes.decode("utf-8", errors="replace")))
            for row in reader:
                vals = list(row.values())
                if len(vals) < 2:
                    continue
                rows.append(TestDataRow(
                    parameter=str(vals[0]).strip(),
                    value=str(vals[1]).strip(),
                    unit=str(vals[2]).strip() if len(vals) > 2 else "",
                    condition=str(vals[3]).strip() if len(vals) > 3 else "",
                    note=str(vals[4]).strip() if len(vals) > 4 else "",
                ))
        else:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
                ws = wb.active
                header_skipped = False
                for row in ws.iter_rows(values_only=True):
                    if not header_skipped:
                        header_skipped = True
                        continue
                    if not row or not row[0]:
                        continue
                    rows.append(TestDataRow(
                        parameter=str(row[0] or "").strip(),
                        value=str(row[1] or "").strip() if len(row) > 1 else "",
                        unit=str(row[2] or "").strip() if len(row) > 2 else "",
                        condition=str(row[3] or "").strip() if len(row) > 3 else "",
                        note=str(row[4] or "").strip() if len(row) > 4 else "",
                    ))
            except ImportError:
                pass  # openpyxl not available
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("parse_excel_test_data failed: %s", e)

    summary = {
        "total_rows": len(rows),
        "parameters": list({r.parameter for r in rows if r.parameter}),
    }
    return ParsedTestData(source_file=filename, rows=rows, summary=summary)
