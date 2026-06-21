# Scripts 目录说明

## 部署与运维

| 脚本 | 说明 |
|------|------|
| `dev.sh` | 本地开发环境启动（Docker Compose） |
| `prod.sh` | 生产环境启动 |
| `deploy.sh` | 完整部署脚本（pull + build + up） |
| `stop.sh` | 停止所有服务 |
| `restart.sh` | 重启服务 |
| `upgrade.sh` | 在线升级（pull 最新镜像 + rolling restart） |
| `offline-upgrade.sh` | 离线升级（从本地包导入镜像） |
| `logs.sh` | 查看服务日志 |

## 备份与恢复

| 脚本 | 说明 |
|------|------|
| `backup.sh` | 手动备份（PostgreSQL + Neo4j + Milvus） |
| `restore.sh` | 从备份恢复 |
| `cron-backup.sh` | 定时备份入口（供 cron 调用） |
| `dr-drill.sh` | 灾难恢复演练脚本 |

## 安全与证书

| 脚本 | 说明 |
|------|------|
| `generate-certs.sh` | 生成 TLS 证书（自签 or Let's Encrypt） |
| `rotate-keys.sh` | 轮换 JWT/API 密钥 |
| `security-hardening.sh` | 系统安全加固（防火墙、SSH 等） |

## 初始化与数据迁移

| 脚本 | 说明 |
|------|------|
| `init_graph_schema.py` | 初始化 Neo4j schema 约束与索引 |
| `schema-sync.py` | 检查 DB 表结构与模型的差异 |
| `migrate-to-multitenant.py` | 单租户数据迁移至多租户结构 |
| `migrate_uploads_to_minio.py` | 将上传文件迁移至 MinIO |

## 检查与验证

| 脚本 | 说明 |
|------|------|
| `check-env.py` | 检查 .env 配置项完整性 |
| `verify_connections.py` | 验证各服务连接（DB/Redis/Neo4j/Milvus） |
| `isolation-audit.py` | 租户隔离安全审计 |
| `tenant-isolation-test.py` | 租户隔离功能测试 |

## 评估与 ML

| 脚本 | 说明 |
|------|------|
| `ragas_eval.py` | RAGAS 指标评估（Faithfulness/Relevancy） |
| `eval_reranker.py` | 重排序模型评估 |
| `scheduled-eval.py` | 定时评估任务（供 cron 调用） |
| `finetune_reranker.py` | 重排序模型微调 |
| `prepare_reranker_data.py` | 准备重排序训练数据 |

## 数据处理

| 脚本 | 说明 |
|------|------|
| `backfill_formulas.py` | 回填公式字段 |
| `backfill_section_level.py` | 回填章节层级 |
| `run_association_mining.py` | 运行关联挖掘 |
| `run_link_prediction.py` | 运行链路预测 |
| `reparse_zero_section_docs.py` | 重新解析零章节文档 |
| `generate_soft_copyright_package.py` | 生成软著申请包 |

## 离线包

`offline-package/` 目录包含离线部署所需的工具与脚本，适用于无外网环境。
