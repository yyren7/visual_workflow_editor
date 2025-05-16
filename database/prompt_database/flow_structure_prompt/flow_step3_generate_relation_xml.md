**第三步：生成节点关系结构文件 (`{{RELATION_FILE_NAME_ACTUAL}}`)**
在同一输出目录 (`{{OUTPUT_DIR_PATH}}`) 中创建一个名为 `{{RELATION_FILE_NAME_ACTUAL}}` 的文件。

- 此文件**仅定义节点之间的逻辑结构和层级关系**。它应包含所有节点的 `type` 和它们在第二步中被赋予的唯一 `id`，并通过 `<next>` 和 `<statement name="DO">` (用于循环等) 标签展示它们如何连接。
- **重要**: `{{RELATION_FILE_NAME_ACTUAL}}` **不应包含**任何 `<field>` 参数值或 `data-blockNo` 属性。它是一个纯粹的结构骨架。
- 参考 `{{EXAMPLE_FLOW_STRUCTURE_DOC_PATH}}` 中展示的节点连接方法。

_示例：基于第一步输入的 `{{RELATION_FILE_NAME_ACTUAL}}`_
\'\'\'xml

<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="select_robot" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_1">
    <next>
      <block type="set_motor" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_2">
        <next>
          <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_3">
            <next>
              <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_4">
                <next>
                  <block type="loop" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5">
                    <statement name="DO">
                      <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5a">
                        <next>
                          <!-- ... 此处省略了 {{BLOCK_ID_PREFIX_EXAMPLE}}_5b 到 {{BLOCK_ID_PREFIX_EXAMPLE}}_5e 的结构 ... -->
                          <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5f">
                             <next>
                               <block type="return" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5g"></block>
                             </next>
                          </block>
                        </next>
                      </block>
                    </statement>
                  </block>
                </next>
              </block>
            </next>
          </block>
        </next>
      </block>
    </next>
  </block>
</xml>
\'\'\'
