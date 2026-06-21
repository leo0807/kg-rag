# 灾难恢复计划（DRP）

## 1. 概述

本文档定义了 CPS 知识库系统在发生重大故障时的恢复目标和操作流程。

| 指标 | 目标值 |
|------|--------|
| **RTO**（恢复时间目标） | 4 小时 |
| **RPO**（恢复点目标） | 24 小时（日备份）/ 1 小时（增量备份） |

---

## 2. 故障分类

### 2.1 一级故障（服务中断，无数据丢失）

- 单个服务崩溃（后端、Worker）
- 容器 OOM
- 网络抖动

**响应时限**：15 分钟内恢复  
**处理方式**：见 [运维手册](./runbook.md#2-常见故障处理)

### 2.2 二级故障（服务降级，可能数据损坏）

- 数据库主节点故障
- Redis 数据丢失
- Milvus 集合损坏

**响应时限**：2 小时内恢复  
**处理方式**：见本文档第 4 节

### 2.3 三级故障（灾难性故障，数据丢失）

- 服务器硬件损毁
- 机房级别故障
- 数据库误删除

**响应时限**：4 小时内恢复  
**处理方式**：见本文档第 5 节

---

## 3. 备份策略

### 3.1 自动备份

| 数据 | 备份工具 | 频率 | 保留期 |
|------|----------|------|--------|
| PostgreSQL | `pg_dump` | 每天 02:00 | 30 天 |
| Neo4j | `neo4j-admin dump` | 每天 03:00 | 30 天 |
| MinIO 文件 | `mc mirror` | 每小时增量 | 90 天 |
| Milvus | 快照 | 每天 04:00 | 7 天 |

定时备份配置（cron）：
```bash
# /etc/cron.d/kg-rag-backup
0 2 * * * root /opt/kg-rag/scripts/cron-backup.sh >> /var/log/kg-rag-backup.log 2>&1
```

### 3.2 备份存储位置

```
/data/backups/
├── YYYY-MM-DD/
│   ├── postgres.dump        # PostgreSQL 全量
│   ├── neo4j.dump           # Neo4j 全量
│   ├── milvus-snapshot/     # Milvus 快照
│   └── backup.manifest.json # 备份清单（含 SHA256）
```

### 3.3 备份验证

每周日 05:00 自动运行恢复测试（使用独立测试环境）：

```bash
bash scripts/dr-drill.sh --dry-run
```

---

## 4. 二级故障恢复流程

### 4.1 PostgreSQL 主节点故障（HA 模式）

```bash
# 1. 确认主节点故障
docker compose -f docker-compose.ha.yml ps postgres-primary

# 2. 手动提升从节点（HA 模式应自动切换，此为手动兜底）
docker exec postgres-replica pg_ctl promote -D /var/lib/postgresql/data

# 3. 更新 DATABASE_URL 指向新主节点
# 编辑 .env 或通过 config reload

# 4. 验证服务恢复
curl http://localhost:8000/health
```

### 4.2 Redis 数据丢失

```bash
# 1. 停止服务（避免写入损坏数据）
docker compose stop backend worker

# 2. 清空 Redis（缓存可重建，Session 需从 DB 重建）
docker exec redis redis-cli FLUSHALL

# 3. 重启服务（缓存会自动重建）
docker compose start backend worker

# 注：活跃会话丢失，用户需重新登录
```

### 4.3 Milvus 集合损坏

```bash
# 1. 恢复最近快照
python3 scripts/restore_milvus_snapshot.py --date YYYY-MM-DD

# 2. 如无快照，从文档重建向量（耗时，按文档量估算）
python3 scripts/reparse_all_docs.py --rebuild-vectors
```

---

## 5. 三级故障（完整恢复）

### 5.1 准备工作

```bash
# 在新服务器上安装 Docker
curl -fsSL https://get.docker.com | bash

# 克隆代码
git clone <repo-url> /opt/kg-rag && cd /opt/kg-rag

# 复制配置（从安全存储获取）
cp /secure/backup/.env /opt/kg-rag/.env
```

### 5.2 数据恢复

```bash
# 将备份文件传输至新服务器
rsync -avz backup-server:/data/backups/latest/ /data/backups/restore/

# 执行恢复（自动停服 → 恢复数据 → 启服）
bash scripts/restore.sh /data/backups/restore/
```

### 5.3 服务启动与验证

```bash
# 启动生产服务
bash scripts/prod.sh

# 验证所有连接
python3 scripts/verify_connections.py

# 运行租户隔离测试
python3 scripts/tenant-isolation-test.py

# 检查健康端点
curl http://localhost:8000/health | python3 -m json.tool
```

---

## 6. 通知流程

| 故障级别 | 通知对象 | 通知方式 | 时限 |
|----------|----------|----------|------|
| 一级 | 运维值班 | 企业微信/钉钉告警 | 自动 |
| 二级 | 运维 + 技术负责人 | 电话 + 工单 | 15 分钟内 |
| 三级 | 全团队 + 业务方 | 电话 + 紧急会议 | 30 分钟内 |

告警 Webhook 配置见 `.env`：
- `DINGTALK_WEBHOOK` — 钉钉机器人
- `WECOM_WEBHOOK` — 企业微信机器人

---

## 7. 演练计划

| 类型 | 频率 | 负责人 |
|------|------|--------|
| 备份恢复测试 | 每周（自动） | CI/CD 系统 |
| 手动恢复演练 | 每季度 | 运维团队 |
| 全链路故障演练 | 每半年 | 技术负责人 |

演练脚本：
```bash
bash scripts/dr-drill.sh
```
