# API 参考文档

完整的交互式文档由 FastAPI 自动生成：
- **Swagger UI**：`http://localhost:8000/docs`
- **ReDoc**：`http://localhost:8000/redoc`
- **OpenAPI JSON**：`http://localhost:8000/openapi.json`

---

## 认证机制

所有需要鉴权的接口都使用 **Bearer Token**（JWT）：

```http
Authorization: Bearer <token>
```

### 获取 Token

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "your_password"
}
```

响应：
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

## 模块索引

### 认证 `/api/auth`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/auth/register` | 用户注册 | 公开 |
| POST | `/api/auth/login` | 用户登录 | 公开 |
| POST | `/api/auth/logout` | 注销 | 登录用户 |
| POST | `/api/auth/change-password` | 修改密码 | 登录用户 |
| GET | `/api/auth/me` | 当前用户信息 | 登录用户 |

### 文档库 `/api/documents`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/documents` | 文档列表（分页） | 登录用户 |
| GET | `/api/documents/{doc_id}` | 文档详情 | 登录用户 |
| GET | `/api/documents/{doc_id}/sections` | 章节列表 | 登录用户 |
| POST | `/api/documents/upload` | 上传文档 | 管理员 |
| DELETE | `/api/documents/{doc_id}` | 删除文档 | 管理员 |

### 智能查询 `/api/query`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/query` | GraphRAG 问答 | 登录用户 |
| POST | `/api/query/stream` | 流式问答（SSE） | 登录用户 |
| GET | `/api/query/{session_id}/history` | 会话历史 | 登录用户 |

查询请求体：
```json
{
  "question": "航空铆接工艺的质量要求是什么？",
  "strategy": "graph_vector",
  "top_k": 5,
  "session_id": "optional-session-id"
}
```

`strategy` 可选值：
- `graph_vector` — 图谱 + 向量混合（推荐）
- `vector_only` — 仅向量检索
- `graph_only` — 仅图谱检索
- `hybrid` — 全量混合

### 知识图谱 `/api/graph`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/graph/nodes` | 节点列表 | 登录用户 |
| GET | `/api/graph/nodes/{node_id}` | 节点详情 | 登录用户 |
| GET | `/api/graph/relations` | 关系列表 | 登录用户 |
| POST | `/api/graph/query` | Cypher 查询 | 管理员 |
| GET | `/api/graph/stats` | 图谱统计 | 登录用户 |

### 管理员 `/api/admin`

所有 `/api/admin/*` 接口需要管理员权限。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/dashboard` | 系统概览 |
| GET | `/api/admin/users` | 用户列表 |
| POST | `/api/admin/users` | 创建用户 |
| PATCH | `/api/admin/users/{id}` | 修改用户 |
| DELETE | `/api/admin/users/{id}` | 删除用户 |
| GET | `/api/admin/quota` | 租户配额概览 |
| GET | `/api/admin/billing/bills` | 账单列表 |
| GET | `/api/admin/billing/plans` | 套餐列表 |
| POST | `/api/admin/billing/bills/{id}/pay` | 标记账单已付 |
| GET | `/api/admin/metrics` | 系统指标 |
| GET | `/api/admin/logs` | 操作日志 |
| GET | `/api/admin/audit` | 审计日志 |

---

## 错误码

| HTTP 状态码 | 含义 | 常见原因 |
|-------------|------|----------|
| 400 | Bad Request | 请求参数格式错误 |
| 401 | Unauthorized | Token 缺失、过期或无效 |
| 403 | Forbidden | 权限不足（需要管理员） |
| 404 | Not Found | 资源不存在 |
| 422 | Unprocessable Entity | Pydantic 参数校验失败 |
| 429 | Too Many Requests | 配额超限（查询次数/Token） |
| 503 | Service Unavailable | 外部服务（LLM/Neo4j）不可用 |

错误响应格式：
```json
{
  "detail": "错误描述（中文）"
}
```

---

## 分页参数

支持分页的接口统一使用以下参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码（从 1 开始） |
| `page_size` | int | 20 | 每页条数（最大 100） |

分页响应格式：
```json
{
  "total": 142,
  "page": 1,
  "page_size": 20,
  "items": [...]
}
```

---

## 多租户说明

平台管理员（`is_platform_admin=true`）访问时，通过 `X-Tenant-ID` 请求头指定租户：

```http
GET /api/admin/quota
Authorization: Bearer <platform-admin-token>
X-Tenant-ID: tenant-uuid-here
```

普通用户的租户 ID 从 JWT payload 中自动提取，无需手动传入。

---

## OpenAPI 客户端生成

```bash
# 导出 OpenAPI spec（需要服务运行中）
curl http://localhost:8000/openapi.json > docs/openapi.json

# 使用 openapi-generator 生成 TypeScript 客户端
npx @openapitools/openapi-generator-cli generate \
  -i docs/openapi.json \
  -g typescript-fetch \
  -o frontend/src/generated/api
```
