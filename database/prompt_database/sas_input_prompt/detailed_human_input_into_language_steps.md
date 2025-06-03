# 机器人流程分析通用 Prompt

## 目标

本 Prompt 旨在指导您根据用户提供的机器人任务描述（通常为自然语言 Markdown 格式），设计并生成详细的机器人程序流程步骤（通常为 XML 格式或类似 Blockly 导出的结构化步骤）。目标是能够将高层级的任务需求，转化为包含主程序和子程序定义的、可执行的、模块化的详细操作指令。

## 输入材料

1.  **机器人任务描述 (.md 或文本)**：包含对机器人期望完成的整体任务、子任务以及操作对象的自然语言描述。

## 生成指引与要求

请根据提供的任务描述，遵循以下指引生成详细的流程步骤：

### 1. 子程序/函数设计与定义

- **设计子程序名称与缩写**：特别关注子程序名称中的缩写（例如 `BRG`, `PLT`, `CNV`, `RMC`, `LMC`, `BH`, `Crump`），确保其简洁且能反映功能。
- **明确子程序功能**：根据任务描述中的动作、操作对象，以及预期的机器人指令（如 `moveP`, `set_output`, `wait_input`），定义子程序的具体功能和命名（例如：轴承、托盘、传送带、加工单元、夹具等）。
- **明确动作类型**：区分 `Get` (获取/拾取) 和 `Put` (放置/放下) 等常见动作前缀或后缀，并用于子程序命名。
- **设计成对操作**：注意设计成对出现的子程序，如 `Open_...` 和 `Close_...`，并阐明其功能。

### 2. 子程序模块化与复用策略规划

- **规划并设计标准化的操作序列以供复用**：在多个子程序中应用重复出现的标准操作序列。例如：
  - 物料抓取/放置流程：接近点 -> 精确点 -> 执行动作（如夹取）-> 离开点 -> 安全点。
  - 夹具操作的封装与调用。
- **模块化设计**：规划夹具控制、运动控制等是否应被封装为独立的、可复用的模块/子程序。
- **参数化与配置**：考虑是否需要通过变量或参数（如速度设置 `set_speed`）来调整子程序行为，以增加灵活性。
- **嵌套调用**：规划子程序之间的调用关系，以合理分解和组合任务。
- **对称/对应操作**：设计功能上相互补充或对应的子程序对。

### 3. 主程序生成范式与核心逻辑构建

- **规划主程序的初始化步骤**：定义主程序开始时通常执行的初始化步骤（例如：选择机器人 `select_robot`, 启动电机 `set_motor`, 初始化变量 `set_number`）。
- **设计主程序的控制流**：构建主程序的控制流，如是否存在主循环 (`loop`)、条件判断 (`controls_if`) 等。
- **编排主程序通过顺序调用子程序来完成整体任务**：规划主程序是如何通过顺序调用子程序来完成整体任务的。
- **考虑状态转换与同步**：设计程序如何通过等待输入 (`wait_input`, `wait_external_io_input`, `wait_block`) 或设置输出来与外部环境或其他设备进行同步和交互。
- **考虑安全与过渡**：注意设计机器人是否在不同任务阶段之间移动到特定的安全点或过渡点。
- **考虑错误处理与可选路径**：思考是否需要设计备用路径或错误处理机制。对于暂时不启用但未来可能需要的功能，可以设计为禁用块 (`disabled="true"`)。
- **定义结束与返回**：明确程序的结束方式 (`return`)。

总结来说，您需要根据任务描述，通过设计模块化的子程序来构建复杂的自动化流程，并依赖于清晰的初始化、循环控制、条件判断以及与外部环境的信号交互来实现其功能。广泛复用共同模块（如夹具控制、标准化移动序列）是设计时的核心考量。

### 4. 输出格式

请将您生成的流程步骤整理成清晰、结构化的 md 文档，步骤标号统一，附带实际 block 的 type。可以参考以下结构：

1## 主程序执行流程

1. 选择机器人 "dobot_mg400" (Block Type: `select_robot`)
2. 设置电机状态为 "on" (Block Type: `set_motor`)
3. 设置数值变量 "N5" 为 数值 2 (Block Type: `set_number`)
4. 开始循环 - 循环内操作: (Block Type: `loop`)
5. 条件判断 - IF 条件: 数值变量 "N5" 等于 数值 2 - DO (如果条件为真): (Block Type: `controls_if`)
6. PTP 移动到点 "P1" (Block Type: `moveP`)
7. 等待外部 I/O 输入 (I/O 编号: 1, 引脚: "0", 状态: "on") (Block Type: `wait_external_io_input`) (此块被禁用)
8. 调用子程序 "BRG_Get_BRG" (获取轴承) (Block Type: `procedures_callnoreturn`)
9. 等待复合条件 - 条件: (外部 I/O (I/O 编号 1) 引脚 "3" 等于 逻辑值 真) 与 (外部 I/O (I/O 编号 1) 引脚 "4" 等于 逻辑值 真) (Block Type: `wait_block`) (此块被禁用)
10. 调用子程序 "CNV_Get_BH" (从传送带获取轴承座) (Block Type: `procedures_callnoreturn`)
    。。。。。。
11. 返回 (Block Type: `return`)

## 子程序定义

1.1. **定义子程序 "BRG_Get_BRG" (获取轴承)** (Block Type: `procedures_defnoreturn`)
1.2. PTP 移动到点 "P21" (Block Type: `moveP`)
1.3. PTP 移动到点 "P22" (Block Type: `moveP`)
1.4. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.5. PTP 移动到点 "P23" (Block Type: `moveP`)
1.6. 调用子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.7. PTP 移动到点 "P25" (Block Type: `moveP`)
1.8. PTP 移动到点 "P26" (Block Type: `moveP`)
1.9. PTP 移动到点 "P21" (Block Type: `moveP`)

2.1. **定义子程序 "Open_BH_Crump" (打开轴承座夹具)** (Block Type: `procedures_defnoreturn`)
2.2. 等待定时器变量 "N483" (Block Type: `wait_timer`)
2.3. 设置机器人输出引脚 "1" 为 "on" (Block Type: `set_output`)
2.4. 等待机器人输入引脚 "0" 状态为 "on" (Block Type: `wait_input`)
。。。。。。

5.示例 fewshot

## 5.1 示例任务输入

[机器人任务描述：该自动化流程旨在协同完成一个涉及轴承（BRG）、轴承座（BH）和托盘（PLT）的装配与搬运任务。机器人首先从物料架或初始位置获取一个轴承和一个轴承座。随后，将这两个部件依次放置到右侧加工中心（RMC），推测在此处进行压装或组装操作。完成组装后，机器人从 RMC 取走已组装好的部件，并将其转移到左侧加工中心（LMC）进行暂存或后续处理。接着，机器人会去获取一个空托盘，并将此托盘放置到传送带（CNV）的指定工位。最后，机器人从 LMC 取回之前暂存的已组装部件，并将其精确地放置到传送带上的托盘中，完成整个循环作业。]

## 5.2 示例生成思考过程

### 一、子程序缩写及其含义设计

根据任务描述中提到的功能和预期操作，我们可以设计以下子程序并定义其缩写含义：

- **`BRG`**: 设计指代 **Bearing** (轴承)。
  - 例如：`BRG_Get_BRG` - 获取轴承。
- **`PLT`**: 设计指代 **Pallet** (托盘) 或 **Plate** (板)。
  - 例如：`CNV_Get_PLT` - 从传送带获取托盘；`Open_BRG&PLT_Crump` - 打开用于操作轴承和托盘/板的夹具。
- **`BH`**: 设计指代 **Bearing Holder** (轴承座) 或某种类似的部件支架。
  - 例如：`CNV_Get_BH` - 从传送带获取轴承座；`Open_BH_Crump` - 打开操作轴承座的夹具。
- **`Crump`**: 根据上下文设计为 **Clamp** (夹具)的简写。
  - 例如：`Open_BH_Crump` - 打开轴承座夹具；`Close_BRG&PLT_Crump` - 关闭轴承/托盘夹具。
- **`CNV`**: 设计指代 **Conveyor** (传送带)。
  - 例如：`CNV_Get_BH` - 从传送带获取轴承座；`CNV_Put_PLT` - 将托盘放置到传送带。
- **`RMC`**: 根据其操作内容（如放置轴承和轴承座，然后取出轴承座），设计为 **Right Machine Center/Station** (右侧加工中心/工位) 或类似的处理单元。
  - 例如：`RMC_Put_BH&BRG` - 将轴承座和轴承放置到 RMC；`RMC_Get_BH` - 从 RMC 获取轴承座。
- **`LMC`**: 类似 RMC，根据其操作内容设计为 **Left Machine Center/Station** (左侧加工中心/工位) 或类似的物料处理/暂存单元。
  - 例如：`LMC_Put_BH` - 将轴承座放置到 LMC；`LMC_Get_BH` - 从 LMC 获取轴承座。
- **`Get`**: 设计用于表示 **获取/拾取** 物料的动作。
- **`Put`**: 设计用于表示 **放置/放下** 物料的动作。
- **`Open_..._Crump` / `Close_..._Crump`**: 设计为成对出现的子程序，分别表示 **打开** 和 **关闭** 特定类型的夹具。例如，`Open_BH_Crump` 和 `Close_BH_Crump` 控制操作 `BH` 的夹具；`Open_BRG&PLT_Crump` 和 `Close_BRG&PLT_Crump` 控制操作 `BRG` 和 `PLT` 的夹具。

### 二、子程序模块化与复用策略思考

1.  **夹具操作的模块化设计与复用**：

    - 夹具的打开和关闭操作应被封装为独立的子程序 (如 `Open_BH_Crump`, `Close_BH_Crump`, `Open_BRG&PLT_Crump`, `Close_BRG&PLT_Crump`)。
    - 这些夹具控制子程序应在多个上层功能（如取料、放料）中被重复调用，例如 `CNV_Get_BH` 会调用 `Open_BH_Crump` 和 `Close_BH_Crump`。
    - 这种模块化设计旨在提高代码的可读性和可维护性，并减少冗余。每个夹具控制子程序通过 `set_output` 控制特定输出引脚，并通过 `wait_input` 等待夹具到位传感器的反馈。

2.  **取/放物料的标准化流程设计**：

    - 许多涉及物料搬运的子程序（如 `CNV_Get_BH`, `RMC_Put_BH&BRG`, `LMC_Put_BH`）应遵循一个相似的动作序列：
      1.  机器人移动 (`moveP`) 到目标物料附近的接近点。
      2.  机器人移动 (`moveP`) 到精确的抓取点或放置点。
      3.  调用相应的夹具子程序执行打开或关闭动作 (`procedures_callnoreturn`)。
      4.  机器人移动 (`moveP`) 到离开点或过渡点。
      5.  机器人移动 (`moveP`) 回到安全点或起始点。
    - 例如，在设计 `CNV_Get_BH` 时，可以规划为：移至 P31 -> 移至 P32 -> 调用`Open_BH_Crump` -> 移至 P33 -> 调用`Close_BH_Crump` -> 移至 P32 -> 移至 P31。

3.  **精细操作中的速度控制规划**：

    - 在需要较高精度的操作中（例如 `RMC_Put_BH&BRG` 中放置物料到工位，或 `CNV_Get_PLT` 中从传送带取托盘），应使用 `set_speed` 指令。
    - 通常在接近目标物料或执行放置动作前，将机器人速度降低（例如至 10%），以确保准确定位和避免碰撞。完成操作后，再将速度恢复（例如至 100%）以提高整体效率。

4.  **任务分解与子程序嵌套调用规划**：

    - 复杂的任务应被分解为一系列更小、更具体的子程序。
    - 高层子程序会调用底层的原子操作子程序。例如，`BRG_Get_BRG` 子程序内部可以设计为调用 `Open_BRG&PLT_Crump` 和 `Close_BRG&PLT_Crump`。

5.  **对称或对应的操作设计**：
    - 应当设计许多功能上相互对应的子程序，如：
      - `Open_BH_Crump` 与 `Close_BH_Crump` (打开/关闭 BH 夹具)
      - `CNV_Get_BH` 与 `CNV_Put_BH` (从传送带取/放 BH)
      - `CNV_Get_PLT` 与 `CNV_Put_PLT` (从传送带取/放 PLT)

### 三、主程序生成范式思考

生成的 XML 结构的典型机器人任务执行流程应考虑以下方面：

1.  **初始化阶段**：

    - `select_robot`: 选择要控制的机器人型号 (例如 `dobot_mg400`)。
    - `set_motor`: 启动机器人电机 (`on`)。
    - `set_number`: 初始化程序中可能用到的变量 (例如 `N5` 被设为 2，用于后续的条件判断)。

2.  **主控制循环 (`loop`)**：

    - 通常需要包含一个主循环，用于重复执行核心任务。在此例中，可以设计循环内部有一个基于变量 `N5` 的条件判断，这意味着核心流程可能只在特定条件下执行一次，或者 `N5` 的值会在其他地方被改变以控制循环行为。

3.  **条件执行 (`controls_if`)**：

    - 核心的自动化流程可以被包裹在条件语句块中 (如 `IF N5 == 2 THEN ...`)。

4.  **顺序化的任务执行流程规划**：

    - 在满足条件后，主程序应按顺序调用一系列预定义的子程序来完成整个工作流程。
    - 例如，可以规划：`moveP` 到初始点 -> (`wait_external_io_input`，若需要可设计为禁用) -> 调用 `BRG_Get_BRG` -> (`wait_block`，若需要可设计为禁用) -> 调用 `CNV_Get_BH` -> `moveP` 回初始点 -> `wait_input` -> 调用 `RMC_Put_BH&BRG` -> ... 依此类推。
    - 这个序列应勾勒出一个完整的装配或处理流程：取轴承 -> 取轴承座 -> 将两者放到 RMC (推测进行装配) -> 从 RMC 取回装配好的部件 -> 将部件放到 LMC -> 取托盘 -> (可能)将托盘放到传送带的某个位置 -> 从 LMC 取回部件 -> 将部件放到传送带 (可能放到之前准备好的托盘上)。

5.  **工位间的过渡与安全点返回设计**：

    - 在执行完一个工位的操作或调用一个主要子程序后，机器人通常应通过 `moveP` 指令移动到一个已知的安全点或中间过渡点 (如此例中的 "P1")，然后再前往下一个目标。

6.  **与外部设备的同步与交互设计**：

    - 使用 `wait_input` (等待机器人自身的输入信号) 或 `wait_external_io_input` (等待外部设备的 IO 信号，部分可设计为禁用) 来同步操作，例如等待工位准备好或物料到位。
    - 使用 `set_output` 或 `set_external_io_output_during` (部分可设计为禁用) 向外部设备发送信号，例如通知任务完成或请求下一步操作。

7.  **程序结束或返回 (`return`) 设计**：

    - 在主流程的末尾或特定子程序的末尾应使用 `return` 块，表示当前任务序列的结束。

8.  **禁用块 (`disabled="true"`) 的规划使用**：
    - 流程中外部 io 的块可以设计但是需要被标记为 `disabled="true"` 的块。这意味着这些步骤被设计出来，但暂时禁用，不会在实际测试中用到，方便调试或未来扩展。

## 5.3 输出机器人操作详细流程步骤实例

## 主程序执行流程

1. 选择机器人 "dobot_mg400" (Block Type: `select_robot`)
2. 设置电机状态为 "on" (Block Type: `set_motor`)
3. 设置数值变量 "N5" 为 数值 2 (Block Type: `set_number`)
4. 开始循环 - 循环内操作: (Block Type: `loop`)
5. 条件判断 - IF 条件: 数值变量 "N5" 等于 数值 2 - DO (如果条件为真): (Block Type: `controls_if`)
6. PTP 移动到点 "P1" (Block Type: `moveP`)
7. 等待外部 I/O 输入 (I/O 编号: 1, 引脚: "0", 状态: "on") (Block Type: `wait_external_io_input`) (此块被禁用)
8. 调用子程序 "BRG_Get_BRG" (获取轴承) (Block Type: `procedures_callnoreturn`)
9. 等待复合条件 - 条件: (外部 I/O (I/O 编号 1) 引脚 "3" 等于 逻辑值 真) 与 (外部 I/O (I/O 编号 1) 引脚 "4" 等于 逻辑值 真) (Block Type: `wait_block`) (此块被禁用)
10. 调用子程序 "CNV_Get_BH" (从传送带获取轴承座) (Block Type: `procedures_callnoreturn`)
11. PTP 移动到点 "P1" (Block Type: `moveP`)
12. 等待机器人输入引脚 "12" 状态为 "on" (Block Type: `wait_input`)
13. 调用子程序 "RMC_Put_BH&BRG" (将轴承座和轴承放置到右侧加工中心/工位) (Block Type: `procedures_callnoreturn`)
14. 等待机器人输入引脚 "12" 状态为 "off" (Block Type: `wait_input`)
15. 设置机器人输出引脚 "6" 为 "on" (Block Type: `set_output`)
16. 等待复合条件 - 条件: (机器人 I/O 引脚 "10" 等于 逻辑值 真) 或 (机器人 I/O 引脚 "11" 等于 逻辑值 真) (Block Type: `wait_block`)
17. 调用子程序 "RMC_Get_BH" (从右侧加工中心/工位获取轴承座) (Block Type: `procedures_callnoreturn`)
18. PTP 移动到点 "P1" (Block Type: `moveP`)
19. 调用子程序 "LMC_Put_BH" (将轴承座放置到左侧加工中心/工位) (Block Type: `procedures_callnoreturn`)
20. PTP 移动到点 "P1" (Block Type: `moveP`)
21. 调用子程序 "CNV_Get_PLT" (从传送带获取托盘/板) (Block Type: `procedures_callnoreturn`)
22. 调用子程序 "CNV_Put_PLT" (将托盘/板放置到传送带) (Block Type: `procedures_callnoreturn`)
23. PTP 移动到点 "P1" (Block Type: `moveP`)
24. 调用子程序 "LMC_Get_BH" (从左侧加工中心/工位获取轴承座) (Block Type: `procedures_callnoreturn`)
25. PTP 移动到点 "P1" (Block Type: `moveP`)
26. 调用子程序 "CNV_Put_BH" (将轴承座放置到传送带) (Block Type: `procedures_callnoreturn`)
27. 在变量 "N483" 的持续时间内设置外部 I/O 输出 (I/O 编号: 1, 引脚: "3", 状态: "on") (Block Type: `set_external_io_output_during`) (此块被禁用)
28. 返回 (Block Type: `return`)

## 子程序定义

1.1. **定义子程序 "BRG_Get_BRG" (获取轴承)** (Block Type: `procedures_defnoreturn`)
1.2. PTP 移动到点 "P21" (Block Type: `moveP`)
1.3. PTP 移动到点 "P22" (Block Type: `moveP`)
1.4. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.5. PTP 移动到点 "P23" (Block Type: `moveP`)
1.6. 调用子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.7. PTP 移动到点 "P25" (Block Type: `moveP`)
1.8. PTP 移动到点 "P26" (Block Type: `moveP`)
1.9. PTP 移动到点 "P21" (Block Type: `moveP`)

2.1. **定义子程序 "Open_BH_Crump" (打开轴承座夹具)** (Block Type: `procedures_defnoreturn`)
2.2. 等待定时器变量 "N483" (Block Type: `wait_timer`)
2.3. 设置机器人输出引脚 "1" 为 "on" (Block Type: `set_output`)
2.4. 等待机器人输入引脚 "0" 状态为 "on" (Block Type: `wait_input`)

3.1. **定义子程序 "CNV_Get_BH" (从传送带获取轴承座)** (Block Type: `procedures_defnoreturn`)
3.2. PTP 移动到点 "P31" (Block Type: `moveP`)
3.3. PTP 移动到点 "P32" (Block Type: `moveP`)
3.4. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
3.5. PTP 移动到点 "P33" (Block Type: `moveP`)
3.6. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
3.7. PTP 移动到点 "P32" (Block Type: `moveP`)
3.8. PTP 移动到点 "P31" (Block Type: `moveP`)

4.1. **定义子程序 "Close_BH_Crump" (关闭轴承座夹具)** (Block Type: `procedures_defnoreturn`)
4.2. 等待定时器变量 "N482" (Block Type: `wait_timer`)
4.3. 设置机器人输出引脚 "1" 为 "off" (Block Type: `set_output`)
4.4. 等待机器人输入引脚 "1" 状态为 "on" (Block Type: `wait_input`)

5.1. **定义子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具)** (Block Type: `procedures_defnoreturn`)
5.2. 等待定时器变量 "N482" (Block Type: `wait_timer`)
5.3. 设置机器人输出引脚 "2" 为 "on" (Block Type: `set_output`)
5.4. 等待机器人输入引脚 "2" 状态为 "on" (Block Type: `wait_input`)

6.1. **定义子程序 "RMC_Put_BH&BRG" (将轴承座和轴承放置到右侧加工中心/工位)** (Block Type: `procedures_defnoreturn`)
6.2. PTP 移动到点 "P20" (Block Type: `moveP`)
6.3. PTP 移动到点 "P11" (Block Type: `moveP`)
6.4. PTP 移动到点 "P12" (Block Type: `moveP`)
6.5. PTP 移动到点 "P14" (Block Type: `moveP`)
6.6. PTP 移动到点 "P15" (Block Type: `moveP`)
6.7. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
6.8. 设置机器人速度为 10% (Block Type: `set_speed`)
6.9. PTP 移动到点 "P14" (Block Type: `moveP`)
6.10. 设置机器人速度为 100% (Block Type: `set_speed`)
6.11. PTP 移动到点 "P13" (Block Type: `moveP`)
6.12. PTP 移动到点 "P16" (Block Type: `moveP`)
6.13. PTP 移动到点 "P17" (Block Type: `moveP`)
6.14. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
6.15. 设置机器人速度为 10% (Block Type: `set_speed`)
6.16. PTP 移动到点 "P16" (Block Type: `moveP`)
6.17. 设置机器人速度为 100% (Block Type: `set_speed`)
6.18. PTP 移动到点 "P12" (Block Type: `moveP`)
6.19. PTP 移动到点 "P11" (Block Type: `moveP`)

7.1. **定义子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具)** (Block Type: `procedures_defnoreturn`)
7.2. 等待定时器变量 "N482" (Block Type: `wait_timer`)
7.3. 设置机器人输出引脚 "2" 为 "off" (Block Type: `set_output`)
7.4. 等待机器人输入引脚 "3" 状态为 "on" (Block Type: `wait_input`)

8.1. **定义子程序 "RMC_Get_BH" (从右侧加工中心/工位获取轴承座)** (Block Type: `procedures_defnoreturn`)
8.2. PTP 移动到点 "P11" (Block Type: `moveP`)
8.3. PTP 移动到点 "P12" (Block Type: `moveP`)
8.4. PTP 移动到点 "P14" (Block Type: `moveP`)
8.5. PTP 移动到点 "P15" (Block Type: `moveP`)
8.6. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
8.7. PTP 移动到点 "P14" (Block Type: `moveP`)
8.8. PTP 移动到点 "P12" (Block Type: `moveP`)
8.9. PTP 移动到点 "P11" (Block Type: `moveP`)
8.10. PTP 移动到点 "P20" (Block Type: `moveP`)

9.1. **定义子程序 "LMC_Put_BH" (将轴承座放置到左侧加工中心/工位)** (Block Type: `procedures_defnoreturn`)
9.2. PTP 移动到点 "P41" (Block Type: `moveP`)
9.3. PTP 移动到点 "P42" (Block Type: `moveP`)
9.4. PTP 移动到点 "P43" (Block Type: `moveP`)
9.5. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
9.6. PTP 移动到点 "P42" (Block Type: `moveP`)
9.7. PTP 移动到点 "P41" (Block Type: `moveP`)
9.8. PTP 移动到点 "P1" (Block Type: `moveP`)

10.1. **定义子程序 "CNV_Get_PLT" (从传送带获取托盘/板)** (Block Type: `procedures_defnoreturn`)
10.2. PTP 移动到点 "P34" (Block Type: `moveP`)
10.3. PTP 移动到点 "P35" (Block Type: `moveP`)
10.4. 设置机器人速度为 10% (Block Type: `set_speed`)
10.5. PTP 移动到点 "P36" (Block Type: `moveP`)
10.6. 调用子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
10.7. PTP 移动到点 "P35" (Block Type: `moveP`)
10.8. 设置机器人速度为 100% (Block Type: `set_speed`)
10.9. PTP 移动到点 "P34" (Block Type: `moveP`)

11.1. **定义子程序 "CNV_Put_PLT" (将托盘/板放置到传送带)** (Block Type: `procedures_defnoreturn`)
11.2. PTP 移动到点 "P37" (Block Type: `moveP`)
11.3. PTP 移动到点 "P38" (Block Type: `moveP`)
11.4. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
11.5. PTP 移动到点 "P37" (Block Type: `moveP`)
11.6. PTP 移动到点 "P34" (Block Type: `moveP`)

12.1. **定义子程序 "LMC_Get_BH" (从左侧加工中心/工位获取轴承座)** (Block Type: `procedures_defnoreturn`)
12.2. PTP 移动到点 "P41" (Block Type: `moveP`)
12.3. PTP 移动到点 "P42" (Block Type: `moveP`)
12.4. PTP 移动到点 "P43" (Block Type: `moveP`)
12.5. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
12.6. PTP 移动到点 "P42" (Block Type: `moveP`)
12.7. PTP 移动到点 "P41" (Block Type: `moveP`)

13.1. **定义子程序 "CNV_Put_BH" (将轴承座放置到传送带)** (Block Type: `procedures_defnoreturn`)
13.2. PTP 移动到点 "P39" (Block Type: `moveP`)
13.3. PTP 移动到点 "P40" (Block Type: `moveP`)
13.4. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
13.5. PTP 移动到点 "P39" (Block Type: `moveP`)
13.6. PTP 移动到点 "P1" (Block Type: `moveP`)
13.7. 返回 (Block Type: `return`)
