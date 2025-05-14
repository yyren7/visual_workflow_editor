# 块定义和节点集成规则

本文档定义了流程中使用的块（block）的规则，格式严格遵循 `flow.xml` 的结构，旨在为前端提供可直接解析的块定义模板。
参数的可选范围和说明通过 XML 注释标明。

## 1. XML 流程结构 (通用参考)

实际的流程（如 `flow.xml`）通常由一个 XML 文件表示，其基本结构如下：

```xml
<xml xmlns="https://developers.google.com/blockly/xml">
  <block type="block_type_1" id="unique_id_1" data-blockNo="1">
    <field name="param1">value1</field>
    <field name="param2">value2</field>
    <next>
      <block type="block_type_2" id="unique_id_2" data-blockNo="2">
        <!-- ... -->
      </block>
    </next>
    <statement name="DO">
       <block type="block_type_3" id="unique_id_3" data-blockNo="3">
         <!-- ... -->
       </block>
    </statement>
  </block>
</xml>
```

## 2. 块定义模板 (XML 格式)

以下是各个块类型的定义模板。`id` 和 `data-blockNo` 在实际使用中会具体分配。

---

### 块类型: `select_robot`

```xml
<block type="select_robot" id="GENERATED_ID" data-blockNo="1">
  <field name="robotName">
    <!-- robotName (ロボット名): 指定操作的机器人名称。 -->
    <!-- 有效范围: 预定义的机器人列表 (例如 fairino_FR, Dobot MG400 等) -->
    <!-- 示例: fairino_FR -->
  </field>
  <!-- <next> ... </next> -->
</block>
```

---

### 块类型: `set_motor`

```xml
<block type="set_motor" id="GENERATED_ID" data-blockNo="1">
  <field name="state_list">
    <!-- state_list (motorStatus - サーボモータ操作): 伺服马达电源的操作状态。 -->
    <!-- 有效范围: on (电源启动), off (电源停止) -->
    <!-- 初期値: ON -->
    <!-- 示例: on -->
  </field>
  <!-- <next> ... </next> -->
</block>
```

---

### 块类型: `moveL`

```xml
<block type="moveL" id="GENERATED_ID" data-blockNo="1">
  <field name="point_name_list">
    <!-- point_name_list (pointName - 目標位置名): 机器人要到达的目标位置名称。 -->
    <!-- 有效范围: 在示教表中设定的点位名称 (最多 100 点) -->
    <!-- 初期値: P1 のポイント名 -->
    <!-- 示例: P1 -->
  </field>
  <field name="control_x">
    <!-- control_x (X - X軸動作有無): X轴移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: X (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="control_y">
    <!-- control_y (Y - Y軸動作有無): Y轴移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: Y (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="control_z">
    <!-- control_z (Z - Z軸動作有無): Z轴移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: Z (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="control_rz">
    <!-- control_rz (Rz - Rz軸動作有無): Rz轴 (通常是旋转轴) 移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: Rz (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="control_ry">
    <!-- control_ry (Ry - Ry軸動作有無): Ry轴移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: Ry (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="control_rx">
    <!-- control_rx (Rx - Rx軸動作有無): Rx轴移动是否有效。 -->
    <!-- 有效范围: enable (有效), disable (无效) -->
    <!-- 初期値: Rx (有效) -->
    <!-- 示例: enable -->
  </field>
  <field name="pallet_list">
    <!-- pallet_list (pallet No. - パレット番号): 用于偏移目标位置的托盘补正量。 -->
    <!-- 有效范围: pallet No.1 ~ 10, no pallet (不使用托盘) -->
    <!-- 初期値: no pallet -->
    <!-- 示例: none (对应 no pallet) -->
  </field>
  <field name="camera_list">
    <!-- camera_list (camera No. - カメラ番号): 用于偏移目标位置的相机补正量。 -->
    <!-- 有效范围: camera No.1 ~ 10, no camera (不使用相机) -->
    <!-- 初期値: no camera -->
    <!-- 示例: none (对应 no camera) -->
  </field>
  <!-- <next> ... </next> -->
</block>
```

---

### 块类型: `loop`

```xml
<block type="loop" id="GENERATED_ID" data-blockNo="1">
  <statement name="DO">
    <!-- 此处嵌套循环执行的块 -->
    <!-- 例如: -->
    <!-- <block type="moveL" ...> <next> <block type="return" ...> </block> </next> </block> -->
  </statement>
  <!-- <next> ... </next>  (通常loop后紧跟statement内的return, 或者loop是末端) -->
</block>
```

---

### 块类型: `return`

```xml
<block type="return" id="GENERATED_ID" data-blockNo="1">
  <!-- 该块通常没有自己的 'field' 参数 -->
  <!-- 用于从 loop 块的 statement 中返回循环开始 -->
</block>
```

---

## 3. 注意事项

- 本文件旨在提供块的"模板"或"定义"。实际在 `flow.xml` 中使用时，`<field>` 标签内将是具体的值，而不是注释。
- `id` 属性在实际流程中应为唯一值。`data-blockNo` 通常表示同类型块的序号，不可重复。
- `<next>` 和 `<statement>` 的内容取决于具体的流程逻辑。
- 对于 `quickfcpr.md` 中定义的更多块类型，可以按照此处的格式进行补充。
