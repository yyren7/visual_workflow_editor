FROM python:3.10-slim

WORKDIR /app

# 安装调试工具 (放在前面以利用缓存)
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    procps \
    net-tools \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 将requirements.txt复制到后端目录内
COPY ./backend/requirements.txt /app/backend/requirements.txt

# 切换到后端目录安装依赖
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# 切换回根工作目录
WORKDIR /app

# 只复制后端和数据库代码
COPY ./backend /app/backend
COPY ./database /app/database

# 列出文件以便调试 (可选)
RUN ls -la /app/backend
RUN ls -la /app/database

# 设置 PYTHONPATH 确保能找到 backend 和 database 包
ENV PYTHONPATH=/app

# 确保pytest在路径中 (可选, pip list 已经证明安装成功)
# RUN pip list

EXPOSE 8000

# 使用正确的路径运行backend目录下的run_backend.py
CMD ["python", "backend/run_backend.py"] 