**第四步：生成最终的完整流程文件 (`{{FINAL_FLOW_FILE_NAME_ACTUAL}}`)**
最后，在同一输出目录 (`{{OUTPUT_DIR_PATH}}`) 中，创建名为 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}` 的文件。

- 此文件是最终的、可执行的机器人流程 XML。
- 它的内容应与第三步生成的 `{{RELATION_FILE_NAME_ACTUAL}}` 结构完全一致，但是**必须包含所有节点的所有参数** (即 `<field>` 标签和值，以及 `data-blockNo` 等属性)。这些参数和属性应从第二步生成的各个独立、参数化的节点 XML 文件中获取和整合。
- 实质上，`{{FINAL_FLOW_FILE_NAME_ACTUAL}}` 是将 `{{RELATION_FILE_NAME_ACTUAL}}` 的结构骨架用各个独立节点文件的参数细节"填充"或"合并"后的结果。 `data-blockNo` 属性应在 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}` 中根据其在完整流程中的上下文正确设置, 根据该类 block 的出现顺序累加编号。

_示例：基于第一步输入的 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}`_
\'\'\'xml

<?xml version="1.0" encoding="UTF-8"?>
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="select_robot" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_1" data-blockNo="1">
    <field name="robotName">{{ROBOT_NAME_EXAMPLE}}</field>
    <next>
      <block type="set_motor" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_2" data-blockNo="1">
        <field name="state_list">on</field>
        <next>
          <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_3" data-blockNo="1"> <!-- 注意：此处的 data-blockNo 是基于流程上下文的 -->
            <field name="point_name_list">{{POINT_NAME_EXAMPLE_1}}</field>
            <field name="control_x">disable</field>
            <field name="control_y">disable</field>
            <field name="control_z">enable</field>
            <field name="control_rz">disable</field>
            <field name="control_ry">disable</field>
            <field name="control_rx">disable</field>
            <field name="pallet_list">none</field>
            <field name="camera_list">none</field>
            <next>
              <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_4" data-blockNo="2">
                <field name="point_name_list">{{POINT_NAME_EXAMPLE_1}}</field>
                <field name="control_x">enable</field>
                <!-- ... 其他 enabled control fields 和 pallet/camera ... -->
                <field name="control_rx">enable</field>
                <field name="pallet_list">none</field>
                <field name="camera_list">none</field>
                <next>
                  <block type="loop" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5" data-blockNo="1">
                    <statement name="DO">
                      <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5a" data-blockNo="3">
                         <field name="point_name_list">{{POINT_NAME_EXAMPLE_2}}</field>
                         <!-- ... all control fields enabled 和 pallet/camera ... -->
                         <field name="camera_list">none</field>
                        <next>
                          <!-- ... 此处省略了 {{BLOCK_ID_PREFIX_EXAMPLE}}_5b 到 {{BLOCK_ID_PREFIX_EXAMPLE}}_5e 的完整参数化节点 ... -->
                          <block type="moveL" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5f" data-blockNo="8">
                             <field name="point_name_list">{{POINT_NAME_EXAMPLE_1}}</field>
                             <!-- ... all control fields enabled 和 pallet/camera ... -->
                             <field name="camera_list">none</field>
                             <next>
                               <block type="return" id="{{BLOCK_ID_PREFIX_EXAMPLE}}_5g" data-blockNo="1"></block>
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

**核心要求：**
确保最终生成的 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}` 文件能够准确反映自然语言输入描述的完整流程，并且其结构和参数均正确无误。所有三种类型的文件（独立的参数化节点 XML、结构化的 `{{RELATION_FILE_NAME_ACTUAL}}` 和最终的 `{{FINAL_FLOW_FILE_NAME_ACTUAL}}`）都应存放在指定的输出目录 (`{{OUTPUT_DIR_PATH}}`) 中。
