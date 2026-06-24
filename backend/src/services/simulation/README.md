# services/simulation — 仿真案例管理与参数采样

## 文件地图
| 文件 | 职责 |
|------|------|
| `doe_sampler.py` | DOE 参数采样：全因子 / LHS / Sobol / 自适应 |
| `parametric_search.py` | 多条件参数化案例检索与评分排序 |
| `case_importer.py` | 批量导入仿真案例（CSV / XLSX） |
| `spec_linker.py` | 将仿真案例关联到规范文档节点 |
| `rule_extractor.py` | 从仿真输入提取隐含设计规则 |
| `simulation_enricher.py` | 补充仿真案例缺失的元数据（材料/工况） |
| `cluster_submitter.py` | 提交仿真任务到 HPC 集群（SLURM 适配） |

## 核心流程
```
GET /simulation/doe?type=lhs&n=20
  → doe_sampler.generate("latin_hypercube", params, n_samples=20)
  → [{param: value}, ...]

POST /simulation/search
  → parametric_search.search(db, criteria)
      ├── _build_filters → DB 查询
      ├── _apply_range_filter → 温度/压力范围过滤
      └── _rank → 关键词+置信度评分排序
```

## 注意事项
- `doe_sampler` 纯 Python，无外部依赖；生产环境建议改用 `SALib`（精度更高）
- `cluster_submitter` 需要 SLURM 环境，本地开发时调用会静默失败
- 参数化搜索的 `temperature_range` / `pressure_range` 为 Python 级后过滤

## 测试
```bash
pytest tests/test_doe_sampler.py tests/test_parametric_search.py -v
```
