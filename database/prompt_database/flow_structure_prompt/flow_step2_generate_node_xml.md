**第二步：生成独立的参数化节点 XML 文件**
根据解析的自然语言流程（如第一步中的示例），为每一个操作步骤（block）创建一个独立的 XML 文件。

- 这些文件应包含该节点的**完整参数** (即所有 `<field>` 标签及其值, `data-blockNo` 属性等) 和一个在整个流程中唯一的 `id` 属性 (例如，使用 `{{BLOCK_ID_PREFIX_EXAMPLE}}_` 加数字或字母后缀)。
- 请参考 `{{NODE_TEMPLATE_DIR_PATH}}` 目录下的节点模板来创建这些文件。
- 将这些独立的 XML 文件存放到指定的输出目录 `{{OUTPUT_DIR_PATH}}`。
- 命名约定示例：`{{BLOCK_ID_PREFIX_EXAMPLE}}_1_select_robot.xml`, `{{BLOCK_ID_PREFIX_EXAMPLE}}_2_set_motor.xml`, `{{BLOCK_ID_PREFIX_EXAMPLE}}_3_moveL_P3_Z_on.xml` (确保文件名能体现其内容和 ID)。

_示例：为第一步输入创建的 `{{BLOCK_ID_PREFIX_EXAMPLE}}_1_select_robot.xml`_
\'\'\'xml

<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="select_robot" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_1" data-blockNo="1">
    <field name="robotName">{{ROBOT_NAME_EXAMPLE}}</field>
  </block>
</xml>
\'\'\'

_示例：为第一步输入创建的 `{{BLOCK_ID_PREFIX_EXAMPLE}}_2_set_motor.xml`_
\'\'\'xml

<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="set_motor" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_2" data-blockNo="1"> <!-- 注意：data-blockNo 在此上下文中通常为1，因为它代表单个节点的序号，但在最终的 {{FINAL_FLOW_FILE_NAME_ACTUAL}} 中可能需要根据全局顺序调整 -->
    <field name="state_list">on</field>
  </block>
</xml>
\'\'\'
