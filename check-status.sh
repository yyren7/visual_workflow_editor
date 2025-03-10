#!/bin/bash

# 创建一个输出文件
OUTPUT_FILE="container_status.log"
echo "容器状态检查 - $(date)" > $OUTPUT_FILE

# 检查Docker容器状态
echo -e "\n=== Docker容器状态 ===" >> $OUTPUT_FILE
docker ps >> $OUTPUT_FILE 2>&1

# 检查前端容器日志
echo -e "\n=== 前端容器日志 ===" >> $OUTPUT_FILE
docker logs workflow-editor-frontend --tail 20 >> $OUTPUT_FILE 2>&1

# 检查前端应用是否可访问
echo -e "\n=== 前端应用访问检查 ===" >> $OUTPUT_FILE
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 >> $OUTPUT_FILE 2>&1

# 检查后端容器日志
echo -e "\n=== 后端容器日志 ===" >> $OUTPUT_FILE
docker logs workflow-editor-backend --tail 20 >> $OUTPUT_FILE 2>&1

# 检查后端API是否可访问
echo -e "\n=== 后端API访问检查 ===" >> $OUTPUT_FILE
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 >> $OUTPUT_FILE 2>&1

# 显示结果
echo "检查完成，结果已保存到 $OUTPUT_FILE"
cat $OUTPUT_FILE 