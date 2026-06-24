# services/ops — 运维支撑（审计/运行时/协作感知）

## 文件地图
| 文件 | 职责 |
|------|------|
| `audit_service.py` | 记录操作审计事件到 `audit_events` 表 |
| `harness_service.py` | 检索质量评估框架（Golden Set 对比、RAGAS 集成） |
| `runtime_service.py` | 系统运行时信息暴露（版本、依赖健康、配置摘要） |
| `presence_service.py` | 用户在线状态管理（WebSocket 心跳） |

## 核心流程
```
任意写操作完成后:
  → audit_service.log(user, action, resource, success)
       └── INSERT INTO audit_events(...)

GET /ops/runtime-info
  → runtime_service.get_info() → {version, db_status, ...}
```

## 注意事项
- 审计日志为追加写，禁止软删除；合规归档周期建议 90 天
- `harness_service` 依赖 Golden Set 数据集，测试前需初始化 `tests/fixtures/`
- `presence_service` 心跳间隔 30s，断开超过 60s 视为离线

## 测试
```bash
pytest tests/test_harness_service.py tests/test_runtime_service.py -v
```
