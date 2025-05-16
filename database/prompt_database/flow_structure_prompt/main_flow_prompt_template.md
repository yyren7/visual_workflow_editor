# 机器人流程 XML 生成 - 主控模板

本文档是你执行机器人流程 XML 生成任务的主入口点。

**总体目标：** 根据用户提供的自然语言输入，生成一系列结构化、参数化的 XML 文件，最终组合成一个完整的机器人控制流程 XML 文件。

**执行流程：**

1.  **查阅占位符定义 (`flow_placeholders.md`)**:
    首先，请仔细阅读并理解同一目录下的 `flow_placeholders.md` 文件。该文件定义了本流程中使用的所有占位符 (例如 `{{OUTPUT_DIR_PATH}}`, `{{ROBOT_NAME_EXAMPLE}}` 等) 及其预期的示例值。在后续步骤中，你需要将这些占位符替换为实际的任务参数。

2.  **顺序执行以下步骤**:
    请严格按照以下顺序，参考对应的 Markdown 文件执行每一步操作。在执行每一步时，请确保你已经理解了 `flow_placeholders.md` 中的相关定义，并将它们应用于当前步骤的上下文中。

    - **步骤 1: 理解输入**

      - 参考文件: `flow_step1_understand_input.md`
      - 任务: 解析用户提供的自然语言描述，识别机器人型号、各个操作步骤及其参数。

    - **步骤 2: 生成独立的参数化节点 XML 文件**

      - 参考文件: `flow_step2_generate_node_xml.md`
      - 任务: 为第一步解析出的每一个操作（block）创建一个独立的、包含完整参数的 XML 文件，并保存在由 `{{OUTPUT_DIR_PATH}}` 指定的目录中。

    - **步骤 3: 生成节点关系结构文件 (`{{RELATION_FILE_NAME_ACTUAL}}`)**

      - 参考文件: `flow_step3_generate_relation_xml.md`
      - 任务: 创建一个名为 `{{RELATION_FILE_NAME_ACTUAL}}` 的 XML 文件，该文件仅包含所有节点的类型、ID 和它们之间的嵌套逻辑关系，不含具体参数。保存到 `{{OUTPUT_DIR_PATH}}`。

    - **步骤 4: 生成最终的完整流程文件 (`{{FINAL_FLOW_FILE_NAME_ACTUAL}}`)**
      - 参考文件: `flow_step4_generate_flow_xml.md`
      - 任务: 创建一个名为 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}` 的 XML 文件。该文件基于步骤 3 的结构，并用步骤 2 中各个独立节点 XML 文件中的详细参数进行填充。这是最终的、完整的流程文件。保存到 `{{OUTPUT_DIR_PATH}}`。

**重要提示：**

- 在整个过程中，请确保 ID 的唯一性和引用的一致性。
- 严格遵循每个步骤文件中提供的指令和示例格式。
- 所有生成的文件都应存放在 `{{OUTPUT_DIR_PATH}}` 所指定的目录中。
