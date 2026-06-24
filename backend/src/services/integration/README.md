# services/integration — 业务系统集成（ERP/MES/PLM）

## 文件地图
| 文件 | 职责 |
|------|------|
| `base.py` | 抽象基类 `IntegrationProvider`，定义 `fetch` / `push` 接口 |
| `erp_provider.py` | SAP/Oracle ERP 数据拉取适配 |
| `mes_provider.py` | MES 生产数据推送与拉取 |
| `plm_provider.py` | PLM 产品生命周期数据同步 |
| `webhook_dispatcher.py` | 向外部系统推送事件 Webhook |
| `messaging.py` | 消息队列适配（RabbitMQ / Kafka） |

## 核心流程
```
外部系统 Webhook → POST /integration/webhook/{source}
  → webhook_dispatcher.dispatch(source, payload)
      └── 路由到对应 provider.handle(payload)

内部数据推送:
  → provider.push(data) → HTTP / MQ → 外部系统
```

## 注意事项
- 各 provider 凭证通过 `settings.INTEGRATION_{ERP|MES|PLM}_*` 配置
- Webhook 请求会验证 HMAC 签名（`X-Signature` 头），密钥在 settings 中
- `messaging.py` 默认使用内存队列，生产环境需配置 `MESSAGE_BROKER_URL`

## 测试
```bash
pytest tests/ -k integration -v
```
