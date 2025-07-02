# Flow 复制功能测试指南

## 功能改进概述

已改进的 flow 复制功能现在支持：

1. **完整的 LangGraph 持久化状态复制** - 包括`sas_state`
2. **重新生成所有相关 ID** - 确保复制的 flow 有独立的节点和边 ID
3. **智能状态重置** - 清理运行时状态，保留配置状态

## 主要改进点

### 1. 前端改进 (`frontend/src/api/flowApi.ts`)

- 添加了 ID 重新生成逻辑
- 实现了深度复制和 ID 重映射
- 支持 sas_state 的复制和清理

### 2. 后端改进 (`backend/app/schemas.py` 和 `backend/app/routers/flow.py`)

- 添加了`sas_state`字段支持到 FlowCreate schema
- 修改了 create_flow API 以处理传递的 sas_state
- 添加了状态验证和回退机制

## 测试步骤

### 1. 启动开发环境

```bash
cd /workspace
./start-dev.sh logs
```

### 2. 创建测试流程图

1. 登录系统
2. 创建一个新的流程图
3. 添加一些节点（如：moveL 节点、condition 节点等）
4. 使用 LangGraph 功能生成一些任务和状态

### 3. 测试复制功能

1. 在流程图选择界面，找到刚创建的流程图
2. 点击复制按钮（ContentCopy 图标）
3. 验证以下项目：

#### 3.1 ID 重新生成验证

- 检查复制的流程图中所有节点 ID 都是新的
- 验证边的 ID 也被重新生成
- 确保边的 source 和 target 引用指向新的节点 ID

#### 3.2 sas_state 复制验证

- 打开浏览器开发者工具查看网络请求
- 检查 createFlow 请求中是否包含 sas_state
- 验证复制的流程图有独立的 LangGraph 状态

#### 3.3 状态清理验证

以下字段应该被重置：

- `current_user_request`: null
- `dialog_state`: 'initial'
- `messages`: []
- `task_list_accepted`: false
- `module_steps_accepted`: false
- `is_error`: false
- `error_message`: null

以下字段应该被保留：

- 配置相关的字段
- 非运行时状态

### 4. 验证复制结果

1. 确认新流程图有唯一的 ID
2. 确认所有节点和边都可以正常操作
3. 确认 LangGraph 功能在复制的流程图中正常工作
4. 确认原始流程图不受影响

## 预期结果

- ✅ 复制的流程图有完全独立的 ID 体系
- ✅ 复制的流程图有独立的 LangGraph 持久化状态
- ✅ 运行时状态被正确重置
- ✅ 配置状态被正确保留
- ✅ 复制操作不影响原始流程图
- ✅ 复制的流程图功能完全正常

## 故障排除

### 问题：复制失败

**可能原因：**

- sas_state 格式不正确
- 后端状态验证失败

**解决方法：**

1. 检查浏览器控制台是否有错误
2. 检查后端日志中的 sas_state 验证信息
3. 确认 RobotFlowAgentState 模型字段匹配

### 问题：ID 冲突

**可能原因：**

- ID 映射表构建错误
- 深度复制逻辑有缺陷

**解决方法：**

1. 检查生成的 ID 映射表
2. 验证 deepCopyAndRemapIds 函数执行结果
3. 确认所有引用都被正确更新

### 问题：状态不一致

**可能原因：**

- 状态重置逻辑不完整
- LangGraph 状态初始化失败

**解决方法：**

1. 检查 fieldsToReset 数组是否包含所有需要重置的字段
2. 验证后端 create_flow 的 LangGraph 初始化逻辑
3. 检查 PostgreSQL checkpointer 状态

## 开发注意事项

1. **ID 生成策略**：当前使用时间戳，可以考虑使用 UUID 以获得更好的唯一性
2. **状态验证**：添加了 RobotFlowAgentState 验证，确保状态格式正确
3. **错误处理**：复制失败时提供详细的错误信息
4. **性能考虑**：大型流程图的深度复制可能需要优化

## 相关文件

- `frontend/src/api/flowApi.ts` - 前端复制逻辑
- `backend/app/schemas.py` - schema 定义
- `backend/app/routers/flow.py` - 后端 API
- `backend/sas/state.py` - RobotFlowAgentState 定义
