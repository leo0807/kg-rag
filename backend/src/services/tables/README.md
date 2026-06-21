# services/tables — 表格提取与规范化模块

## 职责

从 PDF 中提取表格数据，规范化为约束条目（参数-值-单位三元组），写入知识图谱。

## 文件地图

| 文件 | 职责 |
|------|------|
| `table_extractor.py` | Facade：re-export `strategies.py` 的公开符号 |
| `strategies.py` | 实际提取逻辑：camelot（矢量PDF）+ PaddleOCR structure（扫描件） |
| `normalization.py` | 行列转约束：`rows_to_constraints()`；`parse_value()` 解析数值/范围/单位 |
| `canonicalization.py` | 表格内容规范化（去重、合并相似行） |

## 可用性检测

```python
from src.services.tables.strategies import is_available, CAM_ELOT_AVAILABLE
```

- `CAM_ELOT_AVAILABLE`：启动时探测 camelot 是否可 import（矢量 PDF 提取）
- `is_struct_available()`：探测 PaddleOCR structure 是否可用（扫描件表格）
- `is_available()`：二者取 OR

**注意**：`table_extractor.py` 是 facade，无自己的变量。测试 mock 必须 patch `src.services.tables.strategies.CAM_ELOT_AVAILABLE`，而非 `table_extractor._CAMELOT_AVAILABLE`（不存在）。

## 约束提取示例

输入表格行：
```
["参数", "要求值", "单位"]
["力矩", "10~20",  "N·m"]
```

输出 `constraints`:
```python
{
  "constraint_id": "con_<md5>",
  "type": "torque",
  "value": "",
  "value_min": "10",
  "value_max": "20",
  "unit": "N·m",
  "description": "力矩: 10~20 N·m",
  "doc_id": "CPS1000",
  "source": "table",
}
```

## 测试

```bash
pytest tests/test_table_extractor.py tests/test_table_normalization.py tests/test_table_canonicalization.py -v
```
