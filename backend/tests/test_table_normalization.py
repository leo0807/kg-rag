"""Unit tests for table normalization helpers."""
from src.services.tables.normalization import (
    TableHTMLParser,
    parse_html_table,
    rows_to_markdown,
    infer_constraint_type,
    parse_value,
    rows_to_constraints,
)


class TestHtmlParser:
    def test_parses_simple_table(self):
        html = "<table><tr><th>参数</th><th>值</th></tr><tr><td>温度</td><td>120</td></tr></table>"
        rows = parse_html_table(html)
        assert rows == [["参数", "值"], ["温度", "120"]]

    def test_empty_table_returns_empty(self):
        assert parse_html_table("<table></table>") == []

    def test_strips_cell_whitespace(self):
        html = "<table><tr><td>  力矩  </td><td>  50  </td></tr></table>"
        rows = parse_html_table(html)
        assert rows[0] == ["力矩", "50"]


class TestRowsToMarkdown:
    def test_basic_table(self):
        rows = [["参数", "值", "单位"], ["温度", "120", "℃"]]
        md = rows_to_markdown(rows)
        assert "参数" in md
        assert "120" in md
        assert "---" in md  # separator row

    def test_empty_rows_returns_empty(self):
        assert rows_to_markdown([]) == ""

    def test_single_row_no_separator(self):
        rows = [["参数", "值"]]
        md = rows_to_markdown(rows)
        assert "参数" in md


class TestInferConstraintType:
    def test_torque(self):
        assert infer_constraint_type("力矩要求") == "torque"

    def test_temperature(self):
        assert infer_constraint_type("温度限制 ℃") == "temperature"

    def test_tolerance(self):
        assert infer_constraint_type("公差范围") == "tolerance"

    def test_surface_roughness(self):
        assert infer_constraint_type("表面粗糙度 Ra") == "surface"

    def test_pressure(self):
        assert infer_constraint_type("压力 MPa") == "pressure"

    def test_unknown_returns_specification(self):
        assert infer_constraint_type("其他参数") == "specification"


class TestParseValue:
    def test_range_value(self):
        value, v_min, v_max, unit = parse_value("10~20 N·m")
        assert v_min == "10"
        assert v_max == "20"
        assert value == ""

    def test_single_value_with_unit(self):
        value, v_min, v_max, unit = parse_value("120 ℃")
        assert value == "120"
        assert v_min == ""
        assert v_max == ""
        assert unit == "℃"

    def test_bare_number(self):
        value, v_min, v_max, unit = parse_value("50")
        assert value == "50"
        assert unit == ""

    def test_empty_string(self):
        value, v_min, v_max, unit = parse_value("")
        assert value == ""
        assert unit == ""

    def test_em_dash_range(self):
        value, v_min, v_max, unit = parse_value("5—15 MPa")
        assert v_min == "5"
        assert v_max == "15"

    def test_negative_range(self):
        value, v_min, v_max, unit = parse_value("-10~10℃")
        assert v_min == "-10"
        assert v_max == "10"


class TestRowsToConstraints:
    def _make_rows(self):
        return [
            ["参数", "要求值", "单位"],
            ["力矩", "10~20", "N·m"],
            ["温度", "120", "℃"],
        ]

    def test_extracts_two_constraints(self):
        constraints = rows_to_constraints(self._make_rows(), "sec_1", "CPS1000", "tbl_1")
        assert len(constraints) == 2

    def test_constraint_has_required_fields(self):
        constraints = rows_to_constraints(self._make_rows(), "sec_1", "CPS1000", "tbl_1")
        c = constraints[0]
        assert c["doc_id"] == "CPS1000"
        assert c["chunk_id"] == "sec_1"
        assert c["source"] == "table"
        assert c["constraint_id"].startswith("con_")

    def test_range_constraint_has_min_max(self):
        constraints = rows_to_constraints(self._make_rows(), "sec_1", "CPS1000", "tbl_1")
        torque = next(c for c in constraints if "力矩" in c["description"])
        assert torque["value_min"] == "10"
        assert torque["value_max"] == "20"

    def test_too_few_rows_returns_empty(self):
        rows = [["参数", "值"]]  # only header, no data
        assert rows_to_constraints(rows, "sec_1", "CPS1000", "tbl_1") == []

    def test_skips_rows_with_empty_param(self):
        rows = [["参数", "值"], ["", "50"], ["温度", "120"]]
        constraints = rows_to_constraints(rows, "sec_1", "CPS1000", "tbl_1")
        assert len(constraints) == 1
