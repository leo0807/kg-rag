FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（pdfplumber + LibreOffice .doc 转换）
RUN apt-get update && apt-get install -y \
    gcc \
    libreoffice \
    libreoffice-writer \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fonts-noto-cjk \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
# 只要 requirements.txt 没变，这一层就不会重新构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制源码和运维脚本
COPY src/ ./src/
COPY scripts/ ./scripts/

# 创建运行时目录
RUN mkdir -p uploads uploads/snapshots

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
