# Visual Workflow Editor 后端重构计划

## 核心问题

当前架构中存在明显的设计问题：LLM 交互逻辑分散在不同位置，而不是集中在`langchainchat`模块中。这导致代码重复、职责不清晰以及维护困难等问题。

根据设计原则，`langchainchat`模块应当控制所有与 LLM 交互的部分，而当前`app/services`目录下的 prompt 相关和 tool_calling 相关功能需要重新组织。

## 核心重构方向

### 1. 统一 LLM 交互层

- **优先级**：极高
- **工作量**：3-4 周
- **具体任务**：
  - [x] 将`app/services/deepseek_client_service.py`重构为`langchainchat/models/deepseek.py`
  - [x] 将`app/services/prompt_expansion_service.py`移至`langchainchat/prompts/expansion.py`
  - [x] 将`app/services/tool_calling_service.py`重构为`langchainchat/tools/tool_manager.py`
  - [x] 统一所有 LLM 相关配置到`langchainchat/config.py`
  - [x] 将`app/services/workflow_prompt_service.py`中的 LLM 交互逻辑迁移到`langchainchat`

### 2. 重新设计服务层与 LLM 交互层的边界

- **优先级**：高
- **工作量**：2 周
- **具体任务**：
  - [ ] 定义清晰的`langchainchat` API，提供统一的 LLM 调用接口
  - [ ] 重构服务层代码，通过标准接口调用`langchainchat`功能
  - [ ] 确保服务层专注于业务逻辑，将所有 AI 交互委托给`langchainchat`
  - [ ] 为`langchainchat`添加全面的单元测试，确保接口稳定性

### 3. LangChainChat 模块内部结构优化

- **优先级**：高
- **工作量**：2 周
- **具体任务**：
  - [ ] 完善`langchainchat/models/`目录，统一管理所有 LLM 模型连接
  - [ ] 增强`langchainchat/prompts/`目录，系统化管理所有提示模板
  - [ ] 优化`langchainchat/tools/`目录，规范化工具定义和调用
  - [ ] 完善`langchainchat/chains/`目录，实现复杂的推理链
  - [ ] 建立`langchainchat/services/`目录，提供面向业务的高级功能

## 详细重构步骤

### 第一阶段：结构重组（2 周）

#### 1. LangChainChat 核心结构优化

- **优先级**：极高
- **工作量**：1 周
- **具体任务**：
  - [x] 重构`langchainchat/config.py`，集中管理所有 LLM 配置
  - [ ] 创建`langchainchat/base.py`，定义核心抽象类和接口
  - [ ] 完善目录结构，确保职责清晰分离
  - [ ] 建立统一的异常处理和日志机制

#### 2. 服务迁移准备

- **优先级**：高
- **工作量**：1 周
- **具体任务**：
  - [ ] 分析当前服务中的 LLM 相关代码，确定迁移范围
  - [ ] 识别代码依赖，确保迁移不破坏现有功能
  - [ ] 设计迁移测试方案，确保功能等效性
  - [ ] 建立临时兼容层，支持平滑迁移

### 第二阶段：核心功能迁移（3 周）

#### 3. 模型客户端迁移

- **优先级**：高
- **工作量**：1 周
- **具体任务**：
  - [x] 将`deepseek_client_service.py`重构为标准 LangChain 模型适配器
  - [ ] 实现统一的模型接口，支持模型切换
  - [ ] 添加模型性能监控和日志记录
  - [ ] 实现模型调用的错误处理和重试机制

#### 4. 提示管理迁移

- **优先级**：高
- **工作量**：1 周
- **具体任务**：
  - [x] 将`prompt_expansion_service.py`中的功能重构为提示模板系统
  - [x] 从 workflow_prompt_service 提取并迁移提示相关逻辑
  - [ ] 建立提示模板库，支持模板版本管理
  - [ ] 实现提示模板测试框架，验证提示效果

#### 5. 工具调用迁移

- **优先级**：高
- **工作量**：1 周
- **具体任务**：
  - [x] 将`tool_calling_service.py`重构为标准 LangChain 工具系统
  - [ ] 实现声明式工具定义，简化工具创建
  - [ ] 添加工具执行日志和性能监控
  - [ ] 实现工具错误处理和安全验证

### 第三阶段：服务层重构（2 周）

#### 6. 业务服务重构

- **优先级**：高
- **工作量**：1 周
- **具体任务**：
  - [x] 重构`workflow_prompt_service.py`，移除 LLM 交互代码
  - [ ] 将业务服务改为调用`langchainchat` API
  - [ ] 确保服务层专注于工作流业务逻辑
  - [ ] 添加服务层单元测试，验证重构正确性

#### 7. API 路由适配

- **优先级**：中
- **工作量**：1 周
- **具体任务**：
  - [ ] 更新 API 路由，适应新的服务结构
  - [ ] 确保 API 向后兼容，不破坏现有客户端
  - [ ] 优化 API 响应格式，提供更好的错误信息
  - [ ] 添加 API 文档，说明新的交互方式

### 第四阶段：高级功能集成（3 周）

#### 8. 会话管理增强

- **优先级**：中
- **工作量**：1 周
- **具体任务**：
  - [ ] 增强`langchainchat/sessions/`模块，支持复杂对话管理
  - [ ] 实现会话上下文跟踪和管理
  - [ ] 添加会话持久化和恢复功能
  - [ ] 实现会话级别的配置和个性化

#### 9. 记忆和检索增强

- **优先级**：中
- **工作量**：1 周
- **具体任务**：
  - [ ] 优化`langchainchat/memory/`模块，支持多种记忆类型
  - [ ] 增强`langchainchat/retrievers/`，改进上下文获取
  - [ ] 实现流程图特定的上下文检索逻辑
  - [ ] 添加对话历史压缩和摘要功能

#### 10. 代理系统实现

- **优先级**：中
- **工作量**：1 周
- **具体任务**：
  - [ ] 在`langchainchat/agents/`中实现流程图专用 Agent
  - [ ] 定义 Agent 行为策略和决策逻辑
  - [ ] 实现 Agent 与工具和流程图的交互
  - [ ] 添加 Agent 执行监控和控制接口

## 测试与质量保障

### 自动化测试建设

- **优先级**：高
- **工作量**：贯穿整个重构过程
- **具体任务**：
  - [ ] 为每个迁移的模块编写全面的单元测试
  - [ ] 实现关键功能的集成测试
  - [ ] 建立回归测试套件，防止功能退化
  - [ ] 设置 CI/CD 流程，确保代码质量

### 文档与示例

- **优先级**：中
- **工作量**：贯穿整个重构过程
- **具体任务**：
  - [ ] 编写`langchainchat`模块使用文档
  - [ ] 为每个核心功能提供示例代码
  - [ ] 创建架构图，说明模块交互关系
  - [ ] 记录设计决策和最佳实践

## 风险与缓解措施

1. **功能中断风险**

   - 实施分阶段迁移，确保每个阶段都可以单独测试
   - 建立临时兼容层，支持旧代码和新代码并行运行
   - 增加日志和监控，及时发现问题

2. **性能风险**

   - 实施性能基准测试，跟踪重构前后的性能变化
   - 逐步优化性能瓶颈，避免大规模性能退化
   - 实现可监控的性能指标，便于持续改进

3. **复杂度风险**
   - 严格执行代码审查，确保新架构清晰简洁
   - 实现明确的接口契约，减少模块间耦合
   - 持续重构和改进，避免技术债务累积

## 重构后的目标架构

```
backend/
├── app/                     # 核心业务逻辑 (FastAPI)
│   ├── alembic/             # 数据库迁移
│   ├── api/                 # API 路由和端点
│   │   └── endpoints/
│   ├── core/                # 核心配置、安全、日志等
│   ├── crud/                # 数据访问层 (CRUD 操作)
│   ├── db/                  # 数据库连接、会话、模型基类
│   ├── models/              # SQLAlchemy 数据模型 (无变化)
│   ├── schemas/             # Pydantic 数据验证模式 (无变化)
│   ├── services/            # 核心业务逻辑服务 (重构, 不含 LLM 交互)
│   │   ├── flow_service.py
│   │   ├── node_service.py
│   │   └── ...
│   ├── utils/               # 工具函数
│   ├── main.py              # FastAPI 应用入口 (无变化)
│   └── dependencies.py      # 依赖项注入
├── langchainchat/           # LLM 交互统一层 (强化)
│   ├── agents/              # LangChain Agents (可选)
│   ├── base.py              # 核心抽象类和接口 (可选)
│   ├── chains/              # LangChain Chains
│   ├── config.py            # LLM 相关配置 (从 app 迁移整合)
│   ├── memory/              # 对话记忆管理
│   ├── models/              # LLM 模型封装和适配器 (从 app/services 迁移)
│   ├── prompts/             # Prompt 模板管理 (从 app/services 迁移)
│   ├── retrievers/          # 检索器 (可选, 用于 RAG)
│   ├── services/            # 面向业务的 LLM 服务接口 (从 app/services 迁移整合)
│   ├── sessions/            # 会话管理 (可选)
│   ├── tools/               # LangChain Tools (从 app/services 迁移)
│   └── utils/               # LLM 相关工具函数
├── tests/                   # 单元和集成测试
└── pyproject.toml           # 项目配置和依赖
```

## 总结

这个重构计划聚焦于将所有 LLM 交互逻辑统一到`langchainchat`模块中，建立清晰的架构分层，使系统更易于维护和扩展。重构完成后，我们将拥有一个更加模块化、可测试和可靠的后端系统，为未来功能扩展奠定坚实基础。

重构不是一蹴而就的过程，需要分阶段、有计划地进行，同时确保系统始终处于可用状态。通过这种方式，我们可以在不中断现有服务的情况下，逐步提升系统质量。

## 参考资源

- [LangChain 文档](https://docs.langchain.com/)
- [FastAPI 最佳实践](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Clean Architecture 原则](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Python 应用架构模式](https://www.cosmicpython.com/)
