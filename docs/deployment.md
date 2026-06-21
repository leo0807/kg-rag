# 部署文档

## 1. 系统要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| CPU | 4 核 | 8 核+ |
| 内存 | 16 GB | 32 GB+ |
| 磁盘 | 100 GB SSD | 500 GB SSD |
| OS | Ubuntu 22.04 / macOS 13+ | Ubuntu 22.04 LTS |
| Docker | 24.0+ | 最新稳定版 |
| Docker Compose | 2.20+ | 最新稳定版 |

> **注**：本地 Embedding 模型（bge-m3）需要额外 ~4 GB 内存；GPU 可选但显著加速推理。

---

## 2. 快速部署（开发环境）

```bash
# 1. 克隆仓库
git clone <repo-url> kg-rag && cd kg-rag

# 2. 复制并配置环境变量
cp .env.example .env
# 编辑 .env，至少填写 LLM_PROVIDER + 对应 API Key

# 3. 启动所有服务
bash scripts/dev.sh

# 4. 验证连接
python3 scripts/verify_connections.py

# 5. 初始化图数据库 Schema
python3 scripts/init_graph_schema.py
```

服务启动后访问：
- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- Grafana 监控：http://localhost:3001

---

## 3. 生产环境部署

### 3.1 环境准备

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER

# 安装 Docker Compose 插件
sudo apt-get install docker-compose-plugin

# 克隆仓库
git clone <repo-url> /opt/kg-rag && cd /opt/kg-rag
```

### 3.2 配置环境变量

```bash
cp .env.example .env
```

**必须修改的配置项**：

```ini
# 安全密钥（生产必须更改）
JWT_SECRET=<随机 64 字符以上的强密钥>
STORAGE_ACCESS_KEY=<MinIO 访问密钥>
STORAGE_SECRET_KEY=<MinIO 秘钥>

# LLM 服务
LLM_PROVIDER=qwen
DASHSCOPE_API_KEY=sk-xxxx

# 数据库密码
NEO4J_PASSWORD=<强密码>
DATABASE_URL=postgresql+asyncpg://aviation:<密码>@postgres:5432/aviation
```

### 3.3 启动生产服务

```bash
bash scripts/prod.sh
```

`prod.sh` 使用 `docker-compose.prod.yml`，包含：
- 资源限制（CPU/内存）
- 健康检查
- 自动重启策略
- 日志轮转配置

### 3.4 启用监控（可选）

```bash
# 启动 Prometheus + Grafana
docker compose -f docker-compose.monitoring.yml up -d

# Grafana 默认账号：admin / admin（首次登录后请修改）
```

---

## 4. 高可用部署

使用 `docker-compose.ha.yml`：

```bash
docker compose -f docker-compose.ha.yml up -d
```

HA 模式特性：
- 后端多副本（默认 2）
- Nginx 负载均衡
- PostgreSQL 主从复制
- Redis Sentinel

---

## 5. 离线部署（内网/气隙环境）

```bash
# 在有网络的机器上打包
cd scripts/offline-package
# 按 offline-package/README.md 操作

# 传输至目标机器后
bash scripts/offline-upgrade.sh
```

---

## 6. 数据初始化

### 6.1 Schema 同步

```bash
python3 scripts/schema-sync.py
```

输出示例：
```
Checking PostgreSQL schema...
✓ No missing columns found
Checking default tenant...
✓ Default tenant exists
```

### 6.2 多租户迁移（从单租户版本升级）

```bash
# 备份现有数据
bash scripts/backup.sh

# 执行迁移
python3 scripts/migrate-to-multitenant.py

# 验证
python3 scripts/tenant-isolation-test.py
```

---

## 7. SSL/TLS 配置

```bash
# 生成自签证书（测试用）
bash scripts/generate-certs.sh self-signed

# Let's Encrypt（需要域名）
bash scripts/generate-certs.sh letsencrypt --domain example.com
```

证书文件存放于 `nginx/certs/`，Nginx 配置参考 `nginx/nginx.conf`。

---

## 8. 升级

### 8.1 在线升级

```bash
bash scripts/upgrade.sh
```

### 8.2 离线升级

```bash
bash scripts/offline-upgrade.sh /path/to/offline-package.tar.gz
```

---

## 9. 部署后验证清单

```bash
# 1. 服务健康
curl http://localhost:8000/health

# 2. 数据库连接
python3 scripts/verify_connections.py

# 3. 租户隔离
python3 scripts/tenant-isolation-test.py

# 4. 安全检查
bash scripts/isolation-audit.py
```

---

## 10. 环境变量参考

完整参数列表见 `.env.example`。关键分组：

| 分组 | 变量前缀 | 说明 |
|------|----------|------|
| LLM | `LLM_*` | 语言模型配置 |
| Embedding | `EMBEDDING_*` | 向量化模型配置 |
| Reranker | `RERANKER_*` | 重排序模型配置 |
| 数据库 | `DATABASE_URL`, `NEO4J_*`, `MILVUS_*` | 存储层 |
| 安全 | `JWT_SECRET`, `FIELD_ENCRYPTION_KEY` | 密钥配置 |
| 告警 | `DINGTALK_WEBHOOK`, `WECOM_WEBHOOK` | 推送通知 |
| 部署模式 | `DEPLOYMENT_MODE` | cloud/hybrid/intranet/airgapped |
