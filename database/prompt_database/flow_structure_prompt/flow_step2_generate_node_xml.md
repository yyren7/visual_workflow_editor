{{GENERAL_INSTRUCTION_INTRO}} <!-- Assuming this is a general header -->

**第二步：生成独立的参数化节点 XML 文件**

你会收到关于单个机器人操作步骤的详细信息，包括其类型、自然语言描述、从用户输入中提取的参数（JSON 格式），以及该操作类型的节点模板 XML 内容。
你的任务是严格根据提供的 **`{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}`** (节点模板 XML 内容) 的结构，为这一个操作步骤生成一个符合 Blockly 格式的 XML 片段。

**核心要求与约束:**

1.  **严格基于模板**: 生成的 XML 必须严格遵循所提供的 `{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}` 的结构。这意味着：
    - 所有在模板中定义的 `<field name="xxx">...</field>` 标签都应存在于你的输出中。
    - `<block type="xxx">` 中的 `type` 必须与 `{{CURRENT_NODE_TYPE}}` 一致。
2.  **参数填充**:
    - 参考 `{{CURRENT_NODE_PARAMETERS_JSON}}` (一个包含初步提取参数的 JSON 字符串，你需要解析它) 以及 `{{CURRENT_NODE_DESCRIPTION}}` (自然语言描述)，智能地将参数值填充到 `{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}` (节点模板) 中的相应 `<field>` 标签。
    - 如果模板中的某个 `<field>` 在 `{{CURRENT_NODE_PARAMETERS_JSON}}` 中找不到对应的参数：
      - 首先检查模板中该字段是否有默认值或常见用法，并据此填充。
      - 如果上下文中没有明确指示，且字段看起来是可选的，则可以保留模板中的默认值或将其设置为空字符串 `""` (如果适用)。**不要随意省略字段，除非模板本身表明它是完全可选的。**
3.  **Block ID 和编号**:
    - 将最外层 `<block>` 标签的 `id` 属性设置为 `{{TARGET_XML_BLOCK_ID}}`。
    - 将最外层 `<block>` 标签的 `data-blockNo` 属性设置为 `{{TARGET_XML_DATA_BLOCK_NO}}`。
4.  **机器人名称**: 如果模板中需要机器人名称 (例如在 `select_robot` 类型的节点中)，请使用 `{{ROBOT_MODEL_NAME_FROM_STATE}}` 作为机器人名称。
5.  **输出格式**: 你的输出应该是一个**完整且独立的 XML 片段**，通常以 `<?xml version="1.0" encoding="UTF-8"?>` (可选) 开头，并包含一个根 `<xml xmlns="https://developers.google.com/blockly/xml">` 标签，内部嵌套着配置好的 `<block>...</block>`。确保 XML 格式正确。
6.  **控制流块处理 (如 loop, if, etc.)**: 对于像 'loop' 这样的控制流块，当为其生成独立的 XML 时，其内部的 `<statement>` 元素（例如 `<statement name="DO">` 对于 'loop'）应该保持为空。其子操作将在后续步骤中通过关系定义进行连接，而不是直接嵌套在父控制流块的独立 XML 中。

**输入信息概览 (你将获得以下占位符的值):**

- `{{CURRENT_NODE_TYPE}}`: 当前操作的类型 (例如: "moveL", "set_motor")。
- `{{CURRENT_NODE_DESCRIPTION}}`: 当前操作的自然语言描述 (例如: "线性移动到点 P1")。
- `{{TARGET_XML_BLOCK_ID}}`: 你在 `<block>` 标签中要使用的 `id` (例如: "block_uuid_1")。
- `{{TARGET_XML_DATA_BLOCK_NO}}`: 你在 `<block>` 标签中要使用的 `data-blockNo` (例如: "1")。
- `{{ROBOT_MODEL_NAME_FROM_STATE}}`: 当前流程使用的机器人型号 (例如: "dobot_mg400")。
- `{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}`: **[关键]** 与 `{{CURRENT_NODE_TYPE}}` 对应的节点模板的完整 XML 内容字符串。这是你生成 XML 的主要依据。
- _(其他辅助占位符如 `{{BLOCK_ID_PREFIX_EXAMPLE}}`, `{{ROBOT_NAME_EXAMPLE}}` 仅为上下文或旧示例参考，请优先使用上面明确指定的 TARGET 和 CURRENT 值。)_

**示例场景:**
假设 `{{CURRENT_NODE_TYPE}}` 是 "set_motor", `{{CURRENT_NODE_PARAMETERS_JSON}}` 是 `'\'\'\'{"state_list": "on"}\'\'\''`, `{{TARGET_XML_BLOCK_ID}}` 是 "block_uuid_5", `{{TARGET_XML_DATA_BLOCK_NO}}` 是 "5", 并且 `{{NODE_TEMPLATE_XML_CONTENT_AS_STRING}}` 如下:

```xml
<block type="set_motor" id="template_id_placeholder" data-blockNo="template_no_placeholder">
  <field name="state_list">off</field> <!-- 注意模板中的默认值 -->
</block>
```

你的输出应该是 (注意 `id`, `data-blockNo` 和 `state_list` 的值如何被替换):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="set_motor" id="block_uuid_5" data-blockNo="5">
    <field name="state_list">on</field>
  </block>
</xml>
```

请现在根据实际传入的上述占位符的值，为当前操作生成 XML。
**重要：你的回复必须只包含生成的 XML 内容，不应包含任何解释、说明、Markdown 标记或其他非 XML 文本。**
