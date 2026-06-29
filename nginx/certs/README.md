# nginx/certs — SSL 证书目录

将以下两个文件放在此目录：

| 文件名       | 说明                        |
|--------------|-----------------------------|
| `server.crt` | 证书文件（含完整证书链）    |
| `server.key` | 私钥文件（权限设为 600）    |

## 方案一：申请免费证书（Let's Encrypt）

```bash
# 安装 certbot
sudo apt install certbot

# DNS 验证申请通配符证书（覆盖主域 + 所有子域）
sudo certbot certonly --manual --preferred-challenges dns \
  -d cps.comac.cc -d "*.cps.comac.cc"

# 证书默认路径
# /etc/letsencrypt/live/cps.comac.cc/fullchain.pem  → server.crt
# /etc/letsencrypt/live/cps.comac.cc/privkey.pem    → server.key

# 复制到本目录（或在 docker-compose.prod.yml 中挂载 /etc/letsencrypt）
sudo cp /etc/letsencrypt/live/cps.comac.cc/fullchain.pem ./server.crt
sudo cp /etc/letsencrypt/live/cps.comac.cc/privkey.pem   ./server.key
sudo chmod 600 ./server.key
```

## 方案二：使用已有证书

直接将证书文件改名为 `server.crt` 和 `server.key` 放入此目录即可。

## 自签名证书（本地测试用）

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ./server.key \
  -out    ./server.crt \
  -subj "/CN=cps.comac.cc"
chmod 600 ./server.key
```

> 此目录已加入 `.gitignore`，证书文件不会被提交。
