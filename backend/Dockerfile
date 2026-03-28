FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖（pdfplumber 需要）
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
# 只要 requirements.txt 没变，这一层就不会重新构建
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制源码
COPY src/ ./src/

# 创建上传目录
RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]