# --- Build Stage ---
FROM node:16-alpine AS builder 
WORKDIR /app

# 复制 package 文件
COPY ./frontend/package.json ./frontend/package-lock.json ./

# 安装依赖 (使用 npm ci)
RUN npm ci

# 复制前端源代码
# 使用 /app/frontend 作为源代码目录，避免与根目录下的文件冲突
WORKDIR /app/frontend 
COPY ./frontend/ ./

# 声明并设置版本环境变量 (必须在 build 之前)
ARG REACT_APP_VERSION=dev
ENV REACT_APP_VERSION=$REACT_APP_VERSION
RUN echo "Building frontend version: $REACT_APP_VERSION"

# 执行生产构建
# 切换回 /app 目录执行构建，如果 craco 配置需要
WORKDIR /app 
# 使用 package.json 中的 build script (npx craco build)
RUN npm run build --prefix frontend

# --- Production Stage ---
FROM nginx:stable-alpine

# 将构建好的静态文件复制到 Nginx 服务目录
COPY --from=builder /app/frontend/build /usr/share/nginx/html

# (可选) 复制自定义的 Nginx 配置。如果没有这个文件，会使用默认配置。
# 你可能需要创建一个 nginx.conf 文件来处理 React Router 路由。
# COPY nginx.conf /etc/nginx/conf.d/default.conf 

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"] 