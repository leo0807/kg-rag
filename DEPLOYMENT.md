# KG-RAG 部署指南

## 环境要求

| 组件 | 最低版本 | 备注 |
|------|----------|------|
| Docker | 24+ | |
| Docker Compose | v2 (`docker compose`) | |
| CPU | 4 核 | 推荐 8 核 |
| 内存 | 8 GB | 推荐 16 GB（含本地 Embedding 模型） |
| 磁盘 | 50 GB | SSD 推荐；含向量数据和文档存储 |

---

## 快速部署（开发环境）

```bash
# 1. 克隆仓库
git clone <repo-url> && cd kg-rag

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填写：LLM_API_KEY、JWT_SECRET（生产环境必须修改）

# 3. 校验配置
python3 scripts/check-env.py

# 4. 一键部署
./scripts/deploy.sh dev --init
```

部署完成后访问：
- 前端：http://localhost:3000
- API 文档：http://localhost:8000/docs
- MinIO 控制台：http://localhost:9001
- Neo4j Browser：http://localhost:7474

---

## 生产环境部署

```bash
# 修改 .env 中的所有默认密码和密钥
./scripts/deploy.sh prod --init
```

**必须修改的配置：**
- `JWT_SECRET` — 用 `openssl rand -base64 48` 生成
- `NEO4J_PASSWORD` — 修改 docker-compose.yml 和 .env 保持一致
- `POSTGRES_PASSWORD` — 同上

---

## 常用运维操作

```bash
# 查看所有服务状态
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# 查看后端日志（实时）
./scripts/logs.sh backend prod

# 重启后端
./scripts/restart.sh backend prod

# 停止所有服务
./scripts/stop.sh prod

# 升级版本（git pull + rebuild + 滚动重启）
./scripts/upgrade.sh prod
```

---

## 备份与恢复

```bash
# 手动全量备份
./scripts/backup.sh

# 备份列表在 ./backups/ 目录下
ls backups/

# 从指定备份恢复
./scripts/restore.sh backups/20240101_020000

# 配置自动每日备份（凌晨2点）
# 将以下行添加到 crontab -e：
0 2 * * * CRON_MODE=1 /path/to/kg-rag/scripts/cron-backup.sh >> /var/log/kg-rag-backup.log 2>&1
```

备份内容包括：PostgreSQL、Neo4j、MinIO 文件存储、etcd（Milvus 元数据）、配置文件。

---

## 环境变量说明

核心配置项（详见 `.env.example`）：

| 变量 | 说明 | 必填 |
|------|------|------|
| `JWT_SECRET` | JWT 签名密钥，生产环境须强密码 | ✓ |
| `DATABASE_URL` | PostgreSQL 连接串（asyncpg 驱动） | ✓ |
| `NEO4J_URI` | Neo4j bolt 连接地址 | ✓ |
| `LLM_API_KEY` | LLM API 密钥 | ✓（API模式） |
| `LOG_FORMAT` | `text`（开发）或 `json`（生产/容器） | — |
| `DINGTALK_WEBHOOK` | 告警推送 Webhook | — |
| `BACKUP_RETENTION_DAYS` | 备份保留天数（默认7） | — |

运行 `python3 scripts/check-env.py` 可自动校验配置完整性和安全性。

---

## 日志查询

**管理界面：** `/admin/logs`（需管理员登录）

**命令行：**
```bash
# 查看最近500行错误日志
./scripts/logs.sh backend prod --tail=500

# 过滤 ERROR 级别
grep -i "error" logs/errors.log | tail -50
```

**API：**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/admin/logs?level=ERROR&lines=100"
```

---

## CI/CD

- **PR/push → CI 自动运行**：代码格式检查（ruff/eslint）、类型检查、Docker 镜像构建
- **打 tag → 自动发布**：构建并推送镜像到 GitHub Container Registry

```bash
# 发布新版本
git tag v1.2.3
git push --tags
```

---

## 常见问题

**Q: 后端启动后一直显示 DEGRADED？**

A: 查看 `http://localhost:8000/api/health` 中哪个服务为 `down`，通常是 Milvus 启动慢（需等待 30-60 秒）。

**Q: 前端报 "Cannot connect to API"？**

A: 检查 `.env` 中 `FRONTEND_URL` 和 Next.js 的 `NEXT_PUBLIC_API_URL` 是否与后端端口一致。

**Q: Neo4j 内存不足？**

A: 调整 `docker-compose.dev.yml` 中的 `NEO4J_dbms_memory_heap_max__size`。生产环境建议 4-8 GB。

**Q: 备份脚本报错 "容器未运行"？**

A: 备份脚本需要服务正在运行。先确认 `docker ps` 中各容器处于 `Up` 状态。

**Q: 如何重置开发数据库？**

A: 运行 `./scripts/clean.sh`（危险操作，会删除所有数据），然后 `./scripts/deploy.sh dev --init`。
