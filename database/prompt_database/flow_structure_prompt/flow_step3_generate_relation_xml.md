**第三步：生成节点关系结构文件 (`{{RELATION_FILE_NAME_ACTUAL}}`)**

你的任务是根据下面提供的`PARSED_FLOW_STRUCTURE_WITH_IDS_JSON`（一个描述流程步骤及其最终 Block ID 的 JSON 结构），生成一个名为 `{{RELATION_FILE_NAME_ACTUAL}}` 的 XML 文件。这个文件仅定义节点之间的逻辑结构和层级关系。
输出结果应存放在目录 `{{OUTPUT_DIR_PATH}}` 中。

**核心要求与约束:**

1.  **基于提供的 JSON 结构**: 生成的 XML 关系必须精确反映`PARSED_FLOW_STRUCTURE_WITH_IDS_JSON`中定义的顺序和层级（`sub_steps`）。
2.  **使用正确的 ID 和类型**: XML 中的每个`<block>`必须使用 JSON 中提供的对应`id`和`type`。
3.  **纯粹结构**: 输出的 XML**不应包含**任何`<field>`参数值或`data-blockNo`属性。它是一个纯粹的结构骨架。
4.  **连接方式**:
    - 同一层级的顺序块通过嵌套的`<next><block ...></block></next>`连接。
    - 对于包含`sub_steps`的块（如`loop`），其子步骤应嵌套在父块的`<statement name="DO">`标签内，同样遵循`<next>`连接规则。
5.  **XML 格式**: 输出必须是完整且格式正确的 XML，以`<?xml version="1.0" encoding="UTF-8"?>`开头，根元素为`<xml xmlns="https://developers.google.com/blockly/xml">`。

**输入 - 流程结构 (你需要处理这个 JSON):**

```json
{{PARSED_FLOW_STRUCTURE_WITH_IDS_JSON}}
```

**参考输出结构 (这是一个通用示例，请主要依据上面提供的 JSON 生成实际内容，并使用其中的 ID 和类型):**

```xml
{{EXAMPLE_RELATION_XML_CONTENT}}
```

**重要：你的回复必须只包含生成的 `{{RELATION_FILE_NAME_ACTUAL}}` 的 XML 内容，不应包含任何解释、说明、Markdown 标记或其他非 XML 文本。**
