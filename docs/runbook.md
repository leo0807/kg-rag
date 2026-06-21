# 运维手册（Runbook）

## 1. 日常巡检

### 1.1 服务健康检查

```bash
# 检查所有容器状态
docker compose ps

# 检查后端健康端点
curl -s http://localhost:8000/health | python3 -m json.tool

# 检查 Prometheus 指标
curl -s http://localhost:8000/metrics | grep "http_requests_total" | head -5
```

### 1.2 数据库连接验证

```bash
cd scripts
python3 verify_connections.py
```

正常输出示例：
```
✓ PostgreSQL: connected (latency: 2ms)
✓ Neo4j: connected (nodes: 142,318)
✓ Milvus: connected (collections: 3)
✓ Redis: connected (keys: 847)
✓ Elasticsearch: connected (indices: 2)
```

---

## 2. 常见故障处理

### 2.1 后端服务无响应

**症状**：`curl http://localhost:8000/health` 超时或返回 5xx

**排查步骤**：
```bash
# 查看最近 100 行日志
docker compose logs --tail=100 backend

# 检查内存使用
docker stats --no-stream backend

# 重启后端（零停机）
docker compose restart backend
```

**常见原因**：
- 内存 OOM（embedding 模型加载）→ 增加容器内存限制
- Neo4j 连接池耗尽 → 检查 `NEO4J_MAX_CONNECTION_POOL_SIZE`
- 启动时 DB 未就绪 → 等待 30s 后重试

### 2.2 查询响应慢（> 10s）

**排查步骤**：
```bash
# 查看 Grafana 延迟面板 (http://localhost:3001)
# dashboard: kg-rag → P95 Latency by Handler

# 查看慢查询日志
docker compose logs backend | grep "slow\|timeout\|WARNING" | tail -20
```

**常见原因**：
- Milvus 向量检索超时 → 检查 GPU/CPU 负载
- LLM API 超时 → 检查 `LLM_TIMEOUT` 配置
- Redis 缓存未命中率高 → 检查 `QUERY_CACHE_TTL`

### 2.3 文档解析失败

**症状**：ingestion 任务状态一直为 `processing`

**排查步骤**：
```bash
# 查看 Celery worker 日志
docker compose logs worker --tail=50

# 检查任务队列积压
docker exec -it redis redis-cli llen celery

# 重启 worker
docker compose restart worker
```

### 2.4 Neo4j 磁盘告警

```bash
# 检查 Neo4j 数据目录大小
docker exec neo4j du -sh /data

# 触发 Neo4j 检查点（释放日志空间）
docker exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "CALL dbms.checkpoint()"
```

### 2.5 Redis 内存告警

```bash
# 检查 Redis 内存使用
docker exec redis redis-cli info memory | grep "used_memory_human"

# 清理过期 key（谨慎，会短暂阻塞）
docker exec redis redis-cli --scan --pattern "cache:*" | \
  xargs docker exec redis redis-cli del
```

---

## 3. 备份与恢复

### 3.1 手动触发备份

```bash
cd scripts
bash backup.sh
# 备份文件存储于 /data/backups/YYYY-MM-DD/
```

### 3.2 从备份恢复

```bash
# 停止服务
bash scripts/stop.sh

# 恢复（指定备份目录）
bash scripts/restore.sh /data/backups/2026-06-01

# 重启服务
bash scripts/prod.sh
```

### 3.3 验证备份完整性

```bash
# 列出最近备份
ls -lh /data/backups/ | tail -5

# 检查 PostgreSQL dump 完整性
pg_restore --list /data/backups/latest/postgres.dump | tail -5
```

---

## 4. 扩容操作

### 4.1 水平扩展后端

```bash
# 扩展到 3 个副本（需 load balancer 支持）
docker compose scale backend=3
```

### 4.2 扩展 Celery Worker

```bash
docker compose scale worker=4
```

---

## 5. 日志管理

### 5.1 查看实时日志

```bash
# 所有服务
docker compose logs -f

# 单个服务
docker compose logs -f backend

# 过滤错误
docker compose logs backend 2>&1 | grep -E "ERROR|CRITICAL"
```

### 5.2 日志轮转

日志自动轮转配置在 `docker-compose.yml` 的 `logging` 字段：
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
```

---

## 6. 告警响应矩阵

| 告警 | 严重级别 | 响应时限 | 处理步骤 |
|------|----------|----------|----------|
| 服务 5xx 率 > 5% | P1 🔴 | 5 分钟 | 查日志 → 重启 → 升级 |
| P99 延迟 > 30s | P2 🟡 | 15 分钟 | 查慢查询 → 检查外部服务 |
| 磁盘使用率 > 80% | P2 🟡 | 1 小时 | 清理日志/旧备份 |
| 备份失败 | P2 🟡 | 1 小时 | 手动触发 → 检查存储 |
| 内存使用率 > 90% | P1 🔴 | 10 分钟 | 重启服务 → 排查泄漏 |

---

## 7. 紧急联系

- Grafana 监控：http://localhost:3001 (admin / 见 .env GF_SECURITY_ADMIN_PASSWORD)
- Prometheus：http://localhost:9090
- 后端 API 文档：http://localhost:8000/docs
- 后端健康检查：http://localhost:8000/health
