FROM python:3.9-alpine

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
COPY requirements.txt .

# 安装Flask和SQLite支持
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY server.py .
COPY public/ ./public/
COPY data/ ./data/

# 暴露端口
EXPOSE 5000

# 启动应用
CMD ["python3", "server.py"]