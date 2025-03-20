#!/bin/bash
echo "正在修复数据库权限..."
if [ -f "/workspace/flow_editor.db" ]; then
  chmod 666 /workspace/flow_editor.db
  echo "已设置 /workspace/flow_editor.db 权限为666 (可读写)"
fi
if [ -d "/workspace/database" ]; then
  chmod -R 777 /workspace/database
  echo "已设置 /workspace/database 目录权限为777 (完全访问)"
fi
echo "数据库权限修复完成！" 