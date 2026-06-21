# services/security — 安全模块

## 文件地图

| 文件 | 职责 |
|------|------|
| `upload_validator.py` | 上传文件校验：MIME 白名单 + 大小限制 + magic number |
| `encryption.py` | AES-256-GCM 字段级加密（`FieldEncryption`） |
| `key_manager.py` | 密钥轮换管理 |
| `compliance_checker.py` | 合规检查（数据脱敏、导出限制） |

## upload_validator

```python
from src.services.security.upload_validator import validate_upload, PDF_ONLY

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await validate_upload(file, PDF_ONLY)  # raises HTTPException on error
    # content is bytes, ready to write to disk
```

校验顺序：① MIME 白名单 → ② 非空且不超大 → ③ magic number 匹配

## FieldEncryption

```python
from src.services.security.encryption import get_field_encryption

fe = get_field_encryption()
ciphertext = fe.encrypt("sensitive value")
plaintext  = fe.decrypt(ciphertext)
```

密钥来源（优先级）：
1. 构造函数显式传入 `key=...`（32 字节）
2. 环境变量 `FIELD_ENCRYPTION_KEY`（Base64 编码，32 字节）
3. 未配置 → no-op 直通（`enabled == False`）

**已知 Bug（需人工）**：`_load_key()` 先尝试 Base64 解码；若 Base64 成功但 `len != 32` 则直接 `return None`，不会回退到 hex 解码路径。hex 格式密钥实际无法通过 `FIELD_ENCRYPTION_KEY` 正常加载。

## 测试

```bash
pytest tests/test_upload_validator.py tests/test_encryption.py -v
```
