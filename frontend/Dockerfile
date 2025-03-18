FROM node:16-alpine

# 创建app目录并设置适当的权限
WORKDIR /app

# 复制前端的package.json文件
COPY ./frontend/package.json ./frontend/package-lock.json ./

# 为缓存目录创建正确的权限
RUN mkdir -p node_modules/.cache

# 将用户切换为node并设置权限
RUN chown -R node:node /app
USER node

# 安装依赖
RUN npm ci

# 复制源代码
COPY --chown=node:node ./frontend/ .

EXPOSE 3000

CMD ["npm", "start"] 