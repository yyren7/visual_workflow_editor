FROM python:3.10-slim

WORKDIR /app

# 安装调试工具
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    procps \
    net-tools \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 将requirements.txt复制到工作目录
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将整个项目目录复制到容器中
COPY . /app/

# 列出文件以便调试
RUN ls -la /app/backend

ENV PYTHONPATH=/app

# 确保pytest在路径中
RUN pip list

EXPOSE 8000

# 使用正确的路径运行backend目录下的run_backend.py
CMD ["python", "backend/run_backend.py"] 