#!/bin/bash

echo "停止所有容器..."
docker compose down

echo "重新构建容器..."
docker compose build

echo "启动容器..."
docker compose up -d

echo "检查容器状态..."
docker ps 