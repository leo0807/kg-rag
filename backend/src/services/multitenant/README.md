# services/multitenant — 多租户支持（计费/配额/过滤）

## 文件地图
| 文件 | 职责 |
|------|------|
| `tenant_filter.py` | 请求级别租户隔离（在 DB 查询自动追加 tenant_id 过滤） |
| `quota_checker.py` | 检查租户用量配额（API 调用次数、存储、文档数） |
| `billing.py` | 用量计费记录与账单聚合 |

## 核心流程
```
每次 API 请求:
  1. tenant_filter → 从 JWT 提取 tenant_id，注入到 DB session
  2. quota_checker.check(tenant_id, action) → 若超限返回 429
  3. 请求完成 → billing.record_usage(tenant_id, tokens_used)
```

## 注意事项
- `tenant_filter` 通过 SQLAlchemy event 自动追加 WHERE 子句，对业务代码透明
- 配额上限存储在 `tenant_quotas` 表，可通过管理接口动态调整
- 超限时返回 `{"error": "quota_exceeded", "limit": N, "used": M}`

## 测试
```bash
pytest tests/test_tenant_filter.py tests/test_quota_checker.py -v
```
