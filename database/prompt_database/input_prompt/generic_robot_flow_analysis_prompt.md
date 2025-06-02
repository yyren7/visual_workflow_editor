# 机器人流程分析通用 Prompt

## 目标

本 Prompt 旨在指导您拆解机器人程序流程的核心逻辑（通常为 Markdown 格式）。目标是深入理解流程的各个组成部分、识别模式并细分为和对应的程序流程文件（通常为 XML 格式，例如 Blockly 导出的文件）的单个步骤细则。

## 输入材料

1.  **任务描述文件 (.md)**：包含对机器人子程序和主流程的自然语言描述。

## 分析步骤与要求

请根据提供的输入材料，完成以下分析：

### 1. 子程序/函数名称与含义解析

- **识别缩写**：特别关注子程序名称中的缩写（例如 `BRG`, `PLT`, `CNV`, `RMC`, `LMC`, `BH`, `Crump`）。
- **推断含义**：结合子程序在描述文档中的动作描述、XML 文件中调用的具体指令（如 `moveP`, `set_output`, `wait_input`）以及操作的对象（如点位名称、IO 引脚），推断这些缩写的实际工程含义（例如：轴承、托盘、传送带、加工单元、夹具等）。
- **明确动作类型**：区分 `Get` (获取/拾取) 和 `Put` (放置/放下) 等常见动作前缀或后缀的含义。
- **成对操作**：注意识别成对出现的子程序，如 `Open_...` 和 `Close_...`，并阐明其功能。

### 2. 子程序间的共同模块与使用规律识别

- **标准化操作序列**：寻找在多个子程序中重复出现的标准操作序列。例如：
  - 物料抓取/放置流程：接近点 -> 精确点 -> 执行动作（如夹取）-> 离开点 -> 安全点。
  - 夹具操作的封装与调用。
- **模块化设计**：分析夹具控制、运动控制等是否被封装为独立的、可复用的模块/子程序。
- **参数化与配置**：观察是否有通过变量或参数（如速度设置 `set_speed`）来调整子程序行为的模式。
- **嵌套调用**：梳理子程序之间的调用关系，理解任务是如何被分解和组合的。
- **对称/对应操作**：识别功能上相互补充或对应的子程序对。

### 3. 主程序生成范式与核心逻辑总结

- **初始化阶段**：描述主程序开始时通常执行的初始化步骤（例如：选择机器人 `select_robot`, 启动电机 `set_motor`, 初始化变量 `set_number`）。
- **主控制结构**：识别主程序的控制流，如是否存在主循环 (`loop`)、条件判断 (`controls_if`) 等。
- **任务编排**：分析主程序是如何通过顺序调用子程序来完成整体任务的。
- **状态转换与同步**：关注程序如何通过等待输入 (`wait_input`, `wait_external_io_input`, `wait_block`) 或设置输出来与外部环境或其他设备进行同步和交互。
- **安全与过渡**：注意机器人是否在不同任务阶段之间移动到特定的安全点或过渡点。
- **错误处理与可选路径**：观察是否有被禁用 (`disabled="true"`) 的块，并思考其可能代表的意义（如调试、可选功能、未来扩展）。
- **结束与返回**：描述程序的结束方式 (`return`)。

总结来说，这些机器人程序通过模块化的子程序构建复杂的自动化流程，并依赖于清晰的初始化、循环控制、条件判断以及与外部环境的信号交互来实现其功能。共同模块（如夹具控制、标准化移动序列）的广泛复用是其核心特点。

### 4. 输出格式

请将您的拆解结果整理成清晰、结构化的 md 文档，步骤标号统一，附带实际 block 的 type。可以参考以下结构：

5.示例

## 示例任务（用于验证 Prompt 有效性）

[机器人任务描述：该自动化流程旨在协同完成一个涉及轴承（BRG）、轴承座（BH）和托盘（PLT）的装配与搬运任务。机器人首先从物料架或初始位置获取一个轴承和一个轴承座。随后，将这两个部件依次放置到右侧加工中心（RMC），推测在此处进行压装或组装操作。完成组装后，机器人从 RMC 取走已组装好的部件，并将其转移到左侧加工中心（LMC）进行暂存或后续处理。接着，机器人会去获取一个空托盘，并将此托盘放置到传送带（CNV）的指定工位。最后，机器人从 LMC 取回之前暂存的已组装部件，并将其精确地放置到传送带上的托盘中，完成整个循环作业。]

## 示例分析思考过程

### 一、子程序缩写及其含义分析

根据子程序的功能描述和其内部包含的操作，可以推断出各个缩写的可能含义：

- **`BRG`**: 很可能指 **Bearing** (轴承)。
  - 例如：`BRG_Get_BRG` - 获取轴承。
- **`PLT`**: 很可能指 **Pallet** (托盘) 或 **Plate** (板)。
  - 例如：`CNV_Get_PLT` - 从传送带获取托盘；`Open_BRG&PLT_Crump` - 打开用于操作轴承和托盘/板的夹具。
- **`BH`**: 很可能指 **Bearing Holder** (轴承座) 或某种类似的部件支架。
  - 例如：`CNV_Get_BH` - 从传送带获取轴承座；`Open_BH_Crump` - 打开操作轴承座的夹具。
- **`Crump`**: 根据上下文推测是指 **Clamp** (夹具)。这可能是特定术语或笔误。
  - 例如：`Open_BH_Crump` - 打开轴承座夹具；`Close_BRG&PLT_Crump` - 关闭轴承/托盘夹具。
- **`CNV`**: 很可能指 **Conveyor** (传送带)。
  - 例如：`CNV_Get_BH` - 从传送带获取轴承座；`CNV_Put_PLT` - 将托盘放置到传送带。
- **`RMC`**: 根据其操作内容（如放置轴承和轴承座，然后取出轴承座），推测为 **Right Machine Center/Station** (右侧加工中心/工位) 或类似的处理单元。
  - 例如：`RMC_Put_BH&BRG` - 将轴承座和轴承放置到 RMC；`RMC_Get_BH` - 从 RMC 获取轴承座。
- **`LMC`**: 类似 RMC，根据其操作内容推测为 **Left Machine Center/Station** (左侧加工中心/工位) 或类似的物料处理/暂存单元。
  - 例如：`LMC_Put_BH` - 将轴承座放置到 LMC；`LMC_Get_BH` - 从 LMC 获取轴承座。
- **`Get`**: 表示 **获取/拾取** 物料的动作。
- **`Put`**: 表示 **放置/放下** 物料的动作。
- **`Open_..._Crump` / `Close_..._Crump`**: 成对出现的子程序，分别表示 **打开** 和 **关闭** 特定类型的夹具。例如，`Open_BH_Crump` 和 `Close_BH_Crump` 控制操作 `BH` 的夹具；`Open_BRG&PLT_Crump` 和 `Close_BRG&PLT_Crump` 控制操作 `BRG` 和 `PLT` 的夹具。

### 二、子程序之间的共同模块使用规律

1.  **夹具操作的模块化与复用**：

    - 夹具的打开和关闭操作被封装为独立的子程序 (如 `Open_BH_Crump`, `Close_BH_Crump`, `Open_BRG&PLT_Crump`, `Close_BRG&PLT_Crump`)。
    - 这些夹具控制子程序在多个上层功能（如取料、放料）中被重复调用，例如 `CNV_Get_BH` 会调用 `Open_BH_Crump` 和 `Close_BH_Crump`。
    - 这种模块化设计提高了代码的可读性和可维护性，并减少了冗余。每个夹具控制子程序通过 `set_output` 控制特定输出引脚，并通过 `wait_input` 等待夹具到位传感器的反馈。

2.  **取/放物料的标准化流程**：

    - 许多涉及物料搬运的子程序（如 `CNV_Get_BH`, `RMC_Put_BH&BRG`, `LMC_Put_BH`）遵循一个相似的动作序列：
      1.  机器人移动 (`moveP`) 到目标物料附近的接近点。
      2.  机器人移动 (`moveP`) 到精确的抓取点或放置点。
      3.  调用相应的夹具子程序执行打开或关闭动作 (`procedures_callnoreturn`)。
      4.  机器人移动 (`moveP`) 到离开点或过渡点。
      5.  机器人移动 (`moveP`) 回到安全点或起始点。
    - 例如，在 `CNV_Get_BH` 中：移至 P31 -> 移至 P32 -> 调用`Open_BH_Crump` -> 移至 P33 -> 调用`Close_BH_Crump` -> 移至 P32 -> 移至 P31。

3.  **精细操作中的速度控制**：

    - 在需要较高精度的操作中（例如 `RMC_Put_BH&BRG` 中放置物料到工位，或 `CNV_Get_PLT` 中从传送带取托盘），会使用 `set_speed` 指令。
    - 通常在接近目标物料或执行放置动作前，将机器人速度降低（例如至 10%），以确保准确定位和避免碰撞。完成操作后，再将速度恢复（例如至 100%）以提高整体效率。

4.  **任务分解与子程序嵌套调用**：

    - 复杂的任务被分解为一系列更小、更具体的子程序。
    - 高层子程序会调用底层的原子操作子程序。例如，`BRG_Get_BRG` 子程序内部调用了 `Open_BRG&PLT_Crump` 和 `Close_BRG&PLT_Crump`。

5.  **对称或对应的操作**：
    - 存在许多功能上相互对应的子程序，如：
      - `Open_BH_Crump` 与 `Close_BH_Crump` (打开/关闭 BH 夹具)
      - `CNV_Get_BH` 与 `CNV_Put_BH` (从传送带取/放 BH)
      - `CNV_Get_PLT` 与 `CNV_Put_PLT` (从传送带取/放 PLT)

### 三、主程序的默认生成范式

主程序的 XML 结构揭示了一套典型的机器人任务执行流程：

1.  **初始化阶段**：

    - `select_robot`: 选择要控制的机器人型号 (这里是 `dobot_mg400`)。
    - `set_motor`: 启动机器人电机 (`on`)。
    - `set_number`: 初始化程序中可能用到的变量 (例如 `N5` 被设为 2，用于后续的条件判断)。

2.  **主控制循环 (`loop`)**：

    - 通常包含一个主循环，用于重复执行核心任务。在此例中，循环内部有一个基于变量 `N5` 的条件判断，这意味着核心流程可能只在特定条件下执行一次，或者 `N5` 的值会在其他地方被改变以控制循环行为（当前 XML 中未显示 N5 在循环内被修改）。

3.  **条件执行 (`controls_if`)**：

    - 核心的自动化流程被包裹在条件语句块中 (如 `IF N5 == 2 THEN ...`)。

4.  **顺序化的任务执行流程**：

    - 在满足条件后，主程序会按顺序调用一系列预定义的子程序来完成整个工作流程。
    - 例如：`moveP` 到初始点 -> (`wait_external_io_input`，被禁用) -> 调用 `BRG_Get_BRG` -> (`wait_block`，被禁用) -> 调用 `CNV_Get_BH` -> `moveP` 回初始点 -> `wait_input` -> 调用 `RMC_Put_BH&BRG` -> ... 依此类推。
    - 这个序列勾勒出一个完整的装配或处理流程：取轴承 -> 取轴承座 -> 将两者放到 RMC (推测进行装配) -> 从 RMC 取回装配好的部件 -> 将部件放到 LMC -> 取托盘 -> (可能)将托盘放到传送带的某个位置 -> 从 LMC 取回部件 -> 将部件放到传送带 (可能放到之前准备好的托盘上，但 XML 块中未直接体现此关联)。

5.  **工位间的过渡与安全点返回**：

    - 在执行完一个工位的操作或调用一个主要子程序后，机器人经常会通过 `moveP` 指令移动到一个已知的安全点或中间过渡点 (如此例中的 "P1")，然后再前往下一个目标。

6.  **与外部设备的同步与交互**：

    - 使用 `wait_input` (等待机器人自身的输入信号) 或 `wait_external_io_input` (等待外部设备的 IO 信号，部分被禁用) 来同步操作，例如等待工位准备好或物料到位。
    - 使用 `set_output` 或 `set_external_io_output_during` (部分被禁用) 向外部设备发送信号，例如通知任务完成或请求下一步操作。

7.  **程序结束或返回 (`return`)**：

    - 在主流程的末尾或特定子程序的末尾使用 `return` 块，表示当前任务序列的结束。

8.  **禁用块 (`disabled="true"`) 的使用**：
    - 流程中存在一些被标记为 `disabled="true"` 的块。这可能意味着这些步骤是可选的、正在开发调试中，或者是为特定场景预留的逻辑。

## 示例机器人操作流程详细步骤

## 子程序定义

1. **定义子程序 "BRG_Get_BRG"** (Block Type: `procedures_defnoreturn`)
2. PTP 移动到点 "P21" (Block Type: `moveP`)
3. PTP 移动到点 "P22" (Block Type: `moveP`)
4. 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`)
5. PTP 移动到点 "P23" (Block Type: `moveP`)
6. 调用子程序 "Close_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`)
7. PTP 移动到点 "P25" (Block Type: `moveP`)
8. PTP 移动到点 "P26" (Block Type: `moveP`)
9. PTP 移动到点 "P21" (Block Type: `moveP`)
10. **定义子程序 "Open_BH_Crump"** (Block Type: `procedures_defnoreturn`)
11. 等待定时器变量 "N483" (Block Type: `wait_timer`)
12. 设置机器人输出引脚 "1" 为 "on" (Block Type: `set_output`)
13. 等待机器人输入引脚 "0" 状态为 "on" (Block Type: `wait_input`)
14. **定义子程序 "CNV_Get_BH"** (Block Type: `procedures_defnoreturn`)
15. PTP 移动到点 "P31" (Block Type: `moveP`)
16. PTP 移动到点 "P32" (Block Type: `moveP`)
17. 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`)
18. PTP 移动到点 "P33" (Block Type: `moveP`)
19. 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`)
20. PTP 移动到点 "P32" (Block Type: `moveP`)
21. PTP 移动到点 "P31" (Block Type: `moveP`)
22. **定义子程序 "Close_BH_Crump"** (Block Type: `procedures_defnoreturn`)
23. 等待定时器变量 "N482" (Block Type: `wait_timer`)
24. 设置机器人输出引脚 "1" 为 "off" (Block Type: `set_output`)
25. 等待机器人输入引脚 "1" 状态为 "on" (Block Type: `wait_input`)
26. **定义子程序 "Open_BRG&PLT_Crump"** (Block Type: `procedures_defnoreturn`)
27. 等待定时器变量 "N482" (Block Type: `wait_timer`)
28. 设置机器人输出引脚 "2" 为 "on" (Block Type: `set_output`)
29. 等待机器人输入引脚 "2" 状态为 "on" (Block Type: `wait_input`)
30. **定义子程序 "RMC_Put_BH&BRG"** (Block Type: `procedures_defnoreturn`)
31. PTP 移动到点 "P20" (Block Type: `moveP`)
32. PTP 移动到点 "P11" (Block Type: `moveP`)
33. PTP 移动到点 "P12" (Block Type: `moveP`)
34. PTP 移动到点 "P14" (Block Type: `moveP`)
35. PTP 移动到点 "P15" (Block Type: `moveP`)
36. 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`)
37. 设置机器人速度为 10% (Block Type: `set_speed`)
38. PTP 移动到点 "P14" (Block Type: `moveP`)
39. 设置机器人速度为 100% (Block Type: `set_speed`)
40. PTP 移动到点 "P13" (Block Type: `moveP`)
41. PTP 移动到点 "P16" (Block Type: `moveP`)
42. PTP 移动到点 "P17" (Block Type: `moveP`)
43. 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`)
44. 设置机器人速度为 10% (Block Type: `set_speed`)
45. PTP 移动到点 "P16" (Block Type: `moveP`)
46. 设置机器人速度为 100% (Block Type: `set_speed`)
47. PTP 移动到点 "P12" (Block Type: `moveP`)
48. PTP 移动到点 "P11" (Block Type: `moveP`)
49. **定义子程序 "Close_BRG&PLT_Crump"** (Block Type: `procedures_defnoreturn`)
50. 等待定时器变量 "N482" (Block Type: `wait_timer`)
51. 设置机器人输出引脚 "2" 为 "off" (Block Type: `set_output`)
52. 等待机器人输入引脚 "3" 状态为 "on" (Block Type: `wait_input`)
53. **定义子程序 "RMC_Get_BH"** (Block Type: `procedures_defnoreturn`)
54. PTP 移动到点 "P11" (Block Type: `moveP`)
55. PTP 移动到点 "P12" (Block Type: `moveP`)
56. PTP 移动到点 "P14" (Block Type: `moveP`)
57. PTP 移动到点 "P15" (Block Type: `moveP`)
58. 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`)
59. PTP 移动到点 "P14" (Block Type: `moveP`)
60. PTP 移动到点 "P12" (Block Type: `moveP`)
61. PTP 移动到点 "P11" (Block Type: `moveP`)
62. PTP 移动到点 "P20" (Block Type: `moveP`)
63. **定义子程序 "LMC_Put_BH"** (Block Type: `procedures_defnoreturn`)
64. PTP 移动到点 "P41" (Block Type: `moveP`)
65. PTP 移动到点 "P42" (Block Type: `moveP`)
66. PTP 移动到点 "P43" (Block Type: `moveP`)
67. 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`)
68. PTP 移动到点 "P42" (Block Type: `moveP`)
69. PTP 移动到点 "P41" (Block Type: `moveP`)
70. PTP 移动到点 "P1" (Block Type: `moveP`)
71. **定义子程序 "CNV_Get_PLT"** (Block Type: `procedures_defnoreturn`)
72. PTP 移动到点 "P34" (Block Type: `moveP`)
73. PTP 移动到点 "P35" (Block Type: `moveP`)
74. 设置机器人速度为 10% (Block Type: `set_speed`)
75. PTP 移动到点 "P36" (Block Type: `moveP`)
76. 调用子程序 "Close_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`)
77. PTP 移动到点 "P35" (Block Type: `moveP`)
78. 设置机器人速度为 100% (Block Type: `set_speed`)
79. PTP 移动到点 "P34" (Block Type: `moveP`)
80. **定义子程序 "CNV_Put_PLT"** (Block Type: `procedures_defnoreturn`)
81. PTP 移动到点 "P37" (Block Type: `moveP`)
82. PTP 移动到点 "P38" (Block Type: `moveP`)
83. 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`)
84. PTP 移动到点 "P37" (Block Type: `moveP`)
85. PTP 移动到点 "P34" (Block Type: `moveP`)
86. **定义子程序 "LMC_Get_BH"** (Block Type: `procedures_defnoreturn`)
87. PTP 移动到点 "P41" (Block Type: `moveP`)
88. PTP 移动到点 "P42" (Block Type: `moveP`)
89. PTP 移动到点 "P43" (Block Type: `moveP`)
90. 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`)
91. PTP 移动到点 "P42" (Block Type: `moveP`)
92. PTP 移动到点 "P41" (Block Type: `moveP`)
93. **定义子程序 "CNV_Put_BH"** (Block Type: `procedures_defnoreturn`)
94. PTP 移动到点 "P39" (Block Type: `moveP`)
95. PTP 移动到点 "P40" (Block Type: `moveP`)
96. 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`)
97. PTP 移动到点 "P39" (Block Type: `moveP`)
98. PTP 移动到点 "P1" (Block Type: `moveP`)
99. 返回 (Block Type: `return`)

## 主程序执行流程

100. 选择机器人 "dobot_mg400" (Block Type: `select_robot`)
101. 设置电机状态为 "on" (Block Type: `set_motor`)
102. 设置数值变量 "N5" 为 数值 2 (Block Type: `set_number`)
103. 开始循环 - 循环内操作: (Block Type: `loop`)
104. 条件判断 - IF 条件: 数值变量 "N5" 等于 数值 2 - DO (如果条件为真): (Block Type: `controls_if`)
105. PTP 移动到点 "P1" (Block Type: `moveP`)
106. 等待外部 I/O 输入 (I/O 编号: 1, 引脚: "0", 状态: "on") (Block Type: `wait_external_io_input`) (此块被禁用)
107. 调用子程序 "BRG_Get_BRG" (Block Type: `procedures_callnoreturn`)
108. 等待复合条件 - 条件: (外部 I/O (I/O 编号 1) 引脚 "3" 等于 逻辑值 真) 与 (外部 I/O (I/O 编号 1) 引脚 "4" 等于 逻辑值 真) (Block Type: `wait_block`) (此块被禁用)
109. 调用子程序 "CNV_Get_BH" (Block Type: `procedures_callnoreturn`)
110. PTP 移动到点 "P1" (Block Type: `moveP`)
111. 等待机器人输入引脚 "12" 状态为 "on" (Block Type: `wait_input`)
112. 调用子程序 "RMC_Put_BH&BRG" (Block Type: `procedures_callnoreturn`)
113. 等待机器人输入引脚 "12" 状态为 "off" (Block Type: `wait_input`)
114. 设置机器人输出引脚 "6" 为 "on" (Block Type: `set_output`)
115. 等待复合条件 - 条件: (机器人 I/O 引脚 "10" 等于 逻辑值 真) 或 (机器人 I/O 引脚 "11" 等于 逻辑值 真) (Block Type: `wait_block`)
116. 调用子程序 "RMC_Get_BH" (Block Type: `procedures_callnoreturn`)
117. PTP 移动到点 "P1" (Block Type: `moveP`)
118. 调用子程序 "LMC_Put_BH" (Block Type: `procedures_callnoreturn`)
119. PTP 移动到点 "P1" (Block Type: `moveP`)
120. 调用子程序 "CNV_Get_PLT" (Block Type: `procedures_callnoreturn`)
121. 调用子程序 "CNV_Put_PLT" (Block Type: `procedures_callnoreturn`)
122. PTP 移动到点 "P1" (Block Type: `moveP`)
123. 调用子程序 "LMC_Get_BH" (Block Type: `procedures_callnoreturn`)
124. PTP 移动到点 "P1" (Block Type: `moveP`)
125. 调用子程序 "CNV_Put_BH" (Block Type: `procedures_callnoreturn`)
126. 在变量 "N483" 的持续时间内设置外部 I/O 输出 (I/O 编号: 1, 引脚: "3", 状态: "on") (Block Type: `set_external_io_output_during`) (此块被禁用)
127. 返回 (Block Type: `return`)
