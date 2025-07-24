## SAS 状态机简化重构计划 (TODO)

**目标**: 对 SAS Agent 的 `dialog_state` 状态机进行彻底简化，移除冗余和过渡状态，降低系统复杂度，提升代码的可维护性。

**核心原则**:

1.  如果一个状态总是无条件地流转到下一个状态，则将两者合并。
2.  移除所有纯粹用于图内部路由的过渡状态。
3.  用户在批准“模块步骤”后，流程直接进入 XML 生成，不再有最终确认步骤。

**核心流程图**:
graph TD;
A["用户输入<br/>(initial)"] --> B{"1. 生成任务列表<br/>(user_input_to_task_list)"};
B --> C{"<br/>(sas_awaiting_task_list_review)"};
C -- "用户批准" --> D{"2. 生成模块步骤<br/>(task_list_to_module_steps)"};
D --> E{"<br/>(sas_awaiting_module_steps_review)"};
C -- "用户提供修改意见" --> B;

    E -- "用户批准并开始生成" --> F{"<br/>(sas_generating_individual_xmls)"};
    E -- "用户提供修改意见" --> D;

    F --> G{"<br/>(sas_individual_xmls_generated_ready_for_mapping)"};
    G --> H{"3. 参数映射<br/>(parameter_mapping)"};
    H --> I{"<br/>(sas_step3_completed)"};
    I --> J{"4. 合并XML<br/>(merge_xml)"};
    J --> K{"<br/>(sas_merging_completed)"};
    K --> L["✅ 流程结束<br/>(final_xml_generated_success)"];

    subgraph "关键用户交互点"
        C; E;
    end

    subgraph "后端自动处理流程"
        F; G; H; I; J; K; L;
    end

---

### 第一阶段：后端逻辑重构

#### 任务 1.1: 更新状态定义 (源头)

- [ ] **文件**: `backend/sas/state.py`
  - [ ] 从 `dialog_state` 的 `Literal` 类型定义中，移除以下所有 **14** 个计划废弃的状态：
    - `sas_step1_tasks_generated`
    - `sas_step2_module_steps_generated_for_review`
    - `sas_awaiting_xml_generation_approval`
    - `sas_awaiting_task_list_revision_input`
    - `sas_awaiting_module_steps_revision_input`
    - `sas_module_steps_accepted_proceeding`
    - `sas_all_steps_accepted_proceed_to_xml`
    - `sas_step3_to_merge_xml`
    - `sas_merging_completed_no_files`
    - `sas_merging_done_ready_for_concat`
    - `generating_xml_relation`
    - `generating_xml_final`
    - `sas_xml_generation_approved`
    - `sas_processing_error`
  - [ ] 确认最终保留的状态为 **10** 个核心状态。

#### 任务 1.2: 修改 LangGraph 图与节点定义

- [ ] **文件**: `backend/sas/graph_builder.py`
  - [ ] **重构条件边 (Conditional Edges)**: 找到决定流程走向的条件判断函数，移除所有对已废弃状态的路由逻辑，并调整 `sas_awaiting_module_steps_review` 批准后的路由。
- [ ] **文件**: `backend/sas/nodes/*.py` (例如 `user_input_to_task_list.py`, `review_and_refine.py` 等)
  - [ ] **修改节点逻辑**: 确保所有节点不再返回或依赖任何已废弃的状态。

---

### 第二阶段：后端 API 接口与应用入口调整

- [ ] **文件**: `backend/app/routers/sas_chat.py`

  - [ ] **调整 `_process_sas_events` 函数**: 修改处理前端指令 (`FRONTEND_APPROVE_...`) 的逻辑，移除对废弃状态的判断。
  - [ ] **更新状态重置/回滚逻辑**: 在 `reset_stuck_state`, `rollback_to_previous_state`, `force_reset_state` 函数中，更新所有硬编码的状态列表 (`stuck_states`, `stable_states`, `stable_states_priority`)。
  - [ ] **审查 `on_chain_end` 和 `_prepare_frontend_update`**: 确保不再基于废弃状态来同步前端。

- [ ] **文件**: `backend/app/main.py`
  - [ ] **同步更新状态列表**: 检查文件中可能存在的、用于状态重置的硬编码状态列表（如 `stuck_states`），并进行同步更新。

---

### 第三阶段：前端 UI 和交互逻辑适配

- [ ] **文件**: `frontend/src/app/sas/components/SASChat.tsx` (或类似文件)

  - [ ] **清理 UI 渲染逻辑**: 查找并删除基于废弃 `dialog_state` 的 `switch...case` 或 `if...else` 渲染逻辑。
  - [ ] **修改操作按钮**: 将“批准模块步骤”按钮的文案改为“批准并生成 XML”，并确保其交互行为正确。
  - [ ] **移除废弃的 UI 元素和注释**: 删除不再需要的 UI 组件和更新描述旧流程的注释 (例如 `LangGraphTaskNode.tsx` 中的注释)。

- [ ] **文件**: `frontend/src/components/nodes/LangGraphInputNode/useNodeState.ts`

  - [ ] **清理 Hook 逻辑**: 移除所有对已废弃状态的引用，包括 `case` 语句和派生状态的计算。

- [ ] **文件**: `frontend/src/store/` 或 `frontend/src/hooks/`
  - [ ] **审查状态管理**: 检查 Redux/Zustand 等状态管理器或自定义 Hooks，移除对废弃状态的依赖。

---

### 第四阶段：辅助工具与文档同步

- [ ] **文件**: 根目录下的 `analyze_*.py` 脚本

  - [ ] (低优先级) 更新这些开发/调试脚本，使其能够兼容新的状态机，或将其移除。

- [ ] **文件**: `docs/` 目录下的所有相关文档
  - [ ] **更新 Markdown 文档**: 修改 `.md` 文件中对旧状态机模型的描述。
  - [ ] **重新生成图表**: 更新 `.mermaid` 文件并重新生成 `.svg` 图，以准确反映简化的状态流。

---

### 第五阶段：测试与验证

- [ ] **端到端流程测试 (Happy Path)**: 运行一个完整的流程，从输入到最终生成 XML，确保每一步状态转换正确，UI 显示正常。
- [ ] **用户修订流程测试**: 测试在两个审核阶段提供修改意见的场景。
- [ ] **状态重置功能测试**: 测试 `reset-stuck-state` 和 `rollback-to-previous` 功能。
- [ ] **错误处理测试**: 模拟 LLM 生成失败，验证 `generation_failed` 状态。

---

### 第六阶段：清理工作

- [ ] **代码审查**: 邀请团队成员审查所有变更。
- [ ] **文档更新**: 确保项目中无残留的旧状态机描述。
- [ ] **删除此 TODO 文件**: 在所有任务完成后，此文件即可归档或删除。
