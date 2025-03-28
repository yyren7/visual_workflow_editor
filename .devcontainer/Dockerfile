FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# 安装后端 Dockerfile 中指定的调试工具
RUN apt-get update && apt-get install -y \
    curl \
    iputils-ping \
    procps \
    net-tools \
    vim \
    sqlite3 \
    python3-pip \
    python3-venv \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 16（与前端 Dockerfile 保持一致）
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@8.19.4 \
    && node --version \
    && npm --version

# 安装 Python 3.10（与后端一致）
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update \
    && apt-get install -y python3.10 python3.10-venv python3.10-dev \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && update-alternatives --set python3 /usr/bin/python3.10 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3 \
    && rm -rf /var/lib/apt/lists/*

# 设置 Python 环境变量（与后端一致）
ENV PYTHONPATH=/workspace

# 创建非root用户（如果基础镜像没有提供）
ARG USERNAME=vscode
RUN if ! id -u $USERNAME > /dev/null 2>&1; then \
    groupadd --gid 1000 $USERNAME \
    && useradd --uid 1000 --gid 1000 -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/* ; \
    fi

# 切换到 vscode 用户
USER vscode

# 设置用户环境（只配置 .npm-global 目录和别名，不涉及 /workspace）
RUN mkdir -p /home/vscode/.npm-global \
    && npm config set prefix "/home/vscode/.npm-global" \
    && echo 'export PATH=/home/vscode/.npm-global/bin:$PATH' >> /home/vscode/.bashrc \
    && echo 'alias py="python3"' >> /home/vscode/.bashrc \
    && echo 'alias start-backend="cd /workspace && python3 backend/run_backend.py"' >> /home/vscode/.bashrc \
    && echo 'alias start-frontend="cd /workspace/frontend && npm start"' >> /home/vscode/.bashrc

# 配置 tmux
RUN echo 'set -g mouse on' > /home/vscode/.tmux.conf \
    && echo 'set -g history-limit 10000' >> /home/vscode/.tmux.conf \
    && echo 'set -g default-terminal "screen-256color"' >> /home/vscode/.tmux.conf

# 准备工作区目录
WORKDIR /workspace

# 创建卷目录并设置权限
USER root
RUN mkdir -p /workspace/logs && \
    mkdir -p /workspace/frontend/node_modules && \
    mkdir -p /workspace/scripts && \
    mkdir -p /workspace/.devcontainer/scripts && \
    chown -R vscode:vscode /workspace/logs && \
    chown -R vscode:vscode /workspace/frontend/node_modules && \
    chown -R vscode:vscode /workspace/scripts && \
    chown -R vscode:vscode /workspace/.devcontainer/scripts

# 创建启动脚本
COPY .devcontainer/post-create-contents/start-dev.sh /workspace/start-dev.sh
RUN cp /workspace/start-dev.sh /workspace/scripts/start-dev.sh && \
    chmod +x /workspace/start-dev.sh && \
    chmod +x /workspace/scripts/start-dev.sh && \
    chown vscode:vscode /workspace/start-dev.sh && \
    chown vscode:vscode /workspace/scripts/start-dev.sh

# 预安装后端和前端依赖（仅安装不变的核心依赖）
USER vscode
# 安装核心Python依赖
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# 安装核心Node.js依赖（不包括可能会变化的依赖）
COPY frontend/package.json frontend/package-lock.json /tmp/
WORKDIR /tmp
RUN npm ci --no-optional

# 清理和最终设置
WORKDIR /workspace
USER vscode

# 添加以下命令，确保node_modules权限正确
USER root
RUN mkdir -p /workspace/frontend/node_modules && \
    chmod -R 777 /workspace/frontend/node_modules && \
    chown -R vscode:vscode /workspace/frontend/node_modules

# 切换回vscode用户
USER vscode 