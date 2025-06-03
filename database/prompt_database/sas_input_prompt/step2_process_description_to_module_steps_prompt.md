# 机器人流程生成 Prompt - 阶段二：详细流程描述到模块步骤

## 目标

- 本 Prompt 旨在指导您根据上一阶段生成的"详细流程描述方案"中的 **单个主流程** 或 **单个子流程** 的文字描述，将其转化为具体的、可执行的机器人程序模块步骤（通常为 XML 格式或类似 Blockly 导出的结构化步骤）。
- 目标是能够将提供的 **那一个** 详细文字流程方案，精确映射为包含具体指令、点位、参数和控制逻辑的机器人操作序列。
- **重要特性：本 Prompt 设计为并发处理。每次调用时，仅针对输入的一个主流程描述或一个子流程描述，生成其对应的模块步骤。**

## 输入材料

1.  **单个主流程或单个子流程的详细流程描述方案 (文本/Markdown)**：包含该主程序或该子程序的功能、核心逻辑步骤、交互点等的详细文字描述。

## 生成指引与要求

请根据提供的"详细流程描述方案"，遵循以下指引生成具体的模块步骤：

### 1. 将描述性步骤转化为具体指令

- **动作指令映射**：将描述中的"移动到"、"抓取"、"放置"、"打开夹具"、"关闭夹具"、"等待信号"等操作，精确映射到机器人指令集中的具体指令（如 `moveP`, `set_output`, `wait_input`, `procedures_callnoreturn` 等）。
- **点位定义与使用**：为描述中提到的关键位置（如预备点、接近点、精确抓取/放置点、离开点、安全点）分配具体的点位代号（如 `P1`, `P21`, `P22`, `P23` 等），并在 `moveP` 等指令中正确使用这些点位。确保点位在子程序内部以及主程序中的一致性和逻辑性。
- **参数设置**：
  - **速度**：根据描述中提及的精度要求（如"精确移动"、"低速"），使用 `set_speed` 指令在适当时机调整机器人速度（例如，精确操作前降速，完成后恢复常速）。
  - **I/O 引脚**：为夹具控制 (`set_output`)、传感器反馈 (`wait_input`)、外部设备交互 (`wait_external_io_input`, `set_external_io_output_during`) 指定具体的 I/O 编号和引脚号。
  - **变量**：为流程控制（如循环计数、条件判断）中使用的变量 (`set_number`, `controls_if` 条件中的变量）赋予明确的名称和初始值。
  - **定时器**：为操作延时 (`wait_timer`) 指定定时器变量和延时时长。

### 2. 构建主程序和子程序的结构

请根据输入的是主流程描述还是子流程描述，构建相应的结构：

- **若输入为主流程描述，则生成主程序结构**：
  - **初始化块**：以 `select_robot`, `set_motor`, `set_number` (初始化变量) 等指令开始。
  - **控制流块**：使用 `loop` 实现主循环，使用 `controls_if` 实现条件执行逻辑。
  - **子程序调用**：使用 `procedures_callnoreturn` 按顺序调用在详细描述方案中规划的子程序。
  - **过渡与安全移动**：在子程序调用之间或关键步骤后，插入 `moveP` 指令移动到安全点或过渡点。
  - **同步与交互块**：根据描述，插入 `wait_input`, `wait_external_io_input`, `wait_block`, `set_output`, `set_external_io_output_during` 等块，并正确配置其参数（引脚、状态、条件）。
  - **结束块**：以 `return` 块结束主程序逻辑。
- **若输入为子流程描述，则生成子程序结构**：
  - **定义块**：子程序以 `procedures_defnoreturn` 开始，并包含其名称。
  - **操作序列**：内部包含一系列 `moveP`, `procedures_callnoreturn` (调用其他原子子程序如夹具控制), `set_speed`, `wait_timer` 等指令，以实现描述方案中定义的功能。
  - **参数化调用**：确保子程序内对夹具等共享模块的调用是正确的。
  - **结束块**：子程序通常以 `return` 结束，或者直接执行完毕。

### 3. 实现模块化与复用

- **原子操作封装**：夹具的打开/关闭等应实现为独立的、参数化的子程序（如 `Open_BH_Crump`, `Close_BRG&PLT_Crump`），并在其他子程序中通过 `procedures_callnoreturn` 调用。
- **标准化移动序列**：对于物料抓取/放置，严格遵循描述中的"接近点 -> 精确点 -> 执行动作 -> 离开点 -> 安全点"模式，并将其转化为具体的 `moveP` 指令序列。

### 4. 特殊情况处理

- **禁用块 (`disabled="true"`)**：对于描述方案中提及的"可选/禁用逻辑"或在调试阶段暂时不需要执行的步骤（尤其是外部 IO 交互），在生成的对应块上添加 `disabled="true"` 属性。
- **错误处理**：若描述方案中提及错误处理逻辑，需转化为相应的条件判断和备用路径步骤。 (本示例中未详细展开，但实际应用中需考虑)。

总结来说，您需要将提供的 **那一个** 详细文字流程方案（无论是主流程还是子流程），精确地翻译成机器人可以解释和执行的结构化步骤列表，确保所有动作、参数、点位、控制流和模块调用都得到正确体现。

## 示例 fewshot

**注意：以下 fewshot 示例为了全面展示从复杂业务描述到完整模块化步骤的转换过程，提供了一个包含主流程和多个子流程的完整任务描述及其对应的全部模块步骤。在实际并发调用本 Prompt 时，输入将是分解后的单个主流程描述或单个子流程描述，输出也将是对应那单个流程的模块步骤。**

### 示例任务输入 (详细流程描述方案)

子程序及其功能描述

1.  **`BRG_Get_BRG` (获取轴承)**:

    - 功能：机器人从指定位置（如物料架）获取一个轴承。
    - 核心逻辑：移动到轴承预备点 -> 移动到轴承上方 -> 打开轴承夹具 -> 下降到轴承精确抓取点 -> 关闭轴承夹具 -> 抬升 -> 移动到离开点 -> 返回安全/初始点。
    - 涉及夹具：`BRG&PLT_Crump` (操作轴承和托盘的夹具)。

2.  **`CNV_Get_BH` (从传送带获取轴承座)**:

    - 功能：机器人从传送带的指定位置获取一个轴承座。
    - 核心逻辑：移动到传送带旁轴承座预备点 -> 移动到轴承座上方 -> 打开轴承座夹具 -> 下降到轴承座精确抓取点 -> 关闭轴承座夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BH_Crump` (操作轴承座的夹具)。

3.  **`RMC_Put_BH&BRG` (将轴承座和轴承放置到右侧加工中心)**:

    - 功能：机器人将先前获取的轴承座和轴承依次放置到右侧加工中心（RMC）的指定工位。
    - 核心逻辑：
      - 移动到 RMC 预备点。
      - 放置轴承座：移动到 RMC 轴承座放置点上方 -> 精确移动到放置点 -> 打开轴承座夹具 -> 抬升。
      - 放置轴承：移动到 RMC 轴承放置点上方 -> 精确移动到放置点 -> 打开轴承夹具 -> 抬升。
      - 移动到 RMC 离开点。
    - 涉及夹具：`BH_Crump`, `BRG&PLT_Crump`。
    - 注意：放置时可能需要降低速度以确保精度。

4.  **`RMC_Get_BH` (从右侧加工中心获取已组装部件)**:

    - 功能：机器人从右侧加工中心（RMC）获取已组装（或处理完毕）的轴承座（此时可能已与轴承组装）。
    - 核心逻辑：移动到 RMC 预备点 -> 移动到已组装部件上方 -> 打开轴承座夹具（若之前是打开的，则此步为准备抓取） -> 下降到精确抓取点 -> 关闭轴承座夹具 -> 抬升 -> 移动到离开点。
    - 涉及夹具：`BH_Crump`。

5.  **`LMC_Put_BH` (将部件放置到左侧加工中心)**:

    - 功能：机器人将从 RMC 取回的部件放置到左侧加工中心（LMC）进行暂存或后续处理。
    - 核心逻辑：移动到 LMC 预备点 -> 移动到 LMC 放置点上方 -> 精确移动到放置点 -> 打开轴承座夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BH_Crump`。

6.  **`CNV_Get_PLT` (从传送带获取托盘)**:

    - 功能：机器人从指定位置（可能是传送带的另一区域）获取一个空托盘。
    - 核心逻辑：移动到托盘预备点 -> 移动到托盘上方 -> （可能需要低速）精确移动到抓取点 -> 关闭托盘夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BRG&PLT_Crump`。

7.  **`CNV_Put_PLT` (将托盘放置到传送带)**:

    - 功能：机器人将获取到的空托盘放置到传送带的指定工位。
    - 核心逻辑：移动到传送带托盘放置点上方 -> 精确移动到放置点 -> 打开托盘夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BRG&PLT_Crump`。

8.  **`LMC_Get_BH` (从左侧加工中心获取部件)**:

    - 功能：机器人从左侧加工中心（LMC）取回之前暂存的部件。
    - 核心逻辑：移动到 LMC 预备点 -> 移动到部件上方 -> 精确移动到抓取点 -> 关闭轴承座夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BH_Crump`。

9.  **`CNV_Put_BH` (将部件放置到传送带的托盘上)**:

    - 功能：机器人将从 LMC 取回的部件精确放置到传送带上预先放置好的托盘中。
    - 核心逻辑：移动到传送带托盘上方（已装载部件） -> 精确移动到托盘内指定放置点 -> 打开轴承座夹具 -> 抬升 -> 返回安全/初始点。
    - 涉及夹具：`BH_Crump`。

10. **`Open_BH_Crump` (打开轴承座夹具)**:

    - 功能：控制机器人末端执行器打开用于夹持轴承座的夹具。
    - 核心逻辑：发送打开信号，等待夹具到位反馈。

11. **`Close_BH_Crump` (关闭轴承座夹具)**:

    - 功能：控制机器人末端执行器关闭用于夹持轴承座的夹具。
    - 核心逻辑：发送关闭信号，等待夹具到位反馈。

12. **`Open_BRG&PLT_Crump` (打开轴承/托盘夹具)**:

    - 功能：控制机器人末端执行器打开用于夹持轴承或托盘的夹具。
    - 核心逻辑：发送打开信号，等待夹具到位反馈。

13. **`Close_BRG&PLT_Crump` (关闭轴承/托盘夹具)**:
    - 功能：控制机器人末端执行器关闭用于夹持轴承或托盘的夹具。
    - 核心逻辑：发送关闭信号，等待夹具到位反馈。

主程序流程描述

选择机器人型号 (例如 "dobot*mg400")。
启动机器人电机。
初始化必要的流程控制变量 (例如 `N5 = 2`，用于示例中的条件判断)。
主循环开始
循环条件：可能基于特定条件或无限循环 (本例中基于 `N5 == 2` 执行一次核心流程)。
机器人移动到**初始/安全点位 (例如 "P1")**。
*(可选/禁用逻辑)_ 等待外部启动信号 (例如外部 IO 输入)。
调用子程序 `BRG_Get_BRG` (获取轴承)。
_(可选/禁用逻辑)_ 等待物料到位或工位清空信号。
调用子程序 `CNV_Get_BH` (从传送带获取轴承座)。
机器人移动到**初始/安全点位 (例如 "P1")**。
等待加工中心（RMC）准备就绪的信号。
调用子程序 `RMC_Put_BH&BRG` (将轴承座和轴承放置到 RMC)。
等待 RMC 加工完成信号。
发出信号通知 RMC 部件已取走或准备取走。
等待 RMC 确认信号。
调用子程序 `RMC_Get_BH` (从 RMC 获取已组装部件)。
机器人移动到**初始/安全点位 (例如 "P1")**。
调用子程序 `LMC_Put_BH` (将部件放置到 LMC)。
机器人移动到**初始/安全点位 (例如 "P1")**。
调用子程序 `CNV_Get_PLT` (从传送带获取托盘)。
调用子程序 `CNV_Put_PLT` (将托盘放置到传送带)。
机器人移动到**初始/安全点位 (例如 "P1")**。
调用子程序 `LMC_Get_BH` (从 LMC 获取部件)。
机器人移动到**初始/安全点位 (例如 "P1")**。
调用子程序 `CNV_Put_BH` (将部件放置到传送带的托盘上)。
_(可选/禁用逻辑)\_ 发送任务完成信号给外部系统。
主循环结束

#### 三、模块化与复用说明

- **夹具操作**：`Open/Close_BH_Crump` 和 `Open/Close_BRG&PLT_Crump` 为标准夹具控制子程序，会在各个物料拾取和放置子程序中被调用。
- **移动序列**：大部分拾取/放置子程序遵循"预备点 -> 接近点 -> 精确点 -> (执行动作) -> 抬升点 -> 离开点 -> 安全点"的移动逻辑。
- **速度控制**：在 `RMC_Put_BH&BRG`, `CNV_Get_PLT` 等精确操作中，应在描述中提及需规划低速移动阶段。
- **外部交互**：主流程中规划了多处与外部设备（RMC, LMC, 传送带传感器）的信号交互点，用于流程同步。部分不确定或调试期间可禁用的交互被标记为可选/禁用。

### 示例生成思考过程 (简要)

将上述描述性的主流程和子流程转换为模块步骤时，主要遵循以下映射关系：

- **主程序描述的初始化** -> `select_robot`, `set_motor`, `set_number` 块。
- **主程序描述的循环/条件** -> `loop`, `controls_if` 块。
- **主程序和子程序描述中的"调用子程序 X"** -> `procedures_callnoreturn` 块，其参数为子程序名称 X。
- **子程序描述中的"功能：..." 和 "核心逻辑：..."** -> `procedures_defnoreturn` 块，其参数为子程序名称，内部包含实现核心逻辑的指令序列。
- **"移动到 Y 点"** -> `moveP` 块，参数为点位 Y (如 "P1", "P21")。点位需根据上下文逻辑虚构或从已有库中选择。
- **夹具操作如"打开/关闭 Z 夹具"** -> 调用对应的夹具控制子程序，如 `Open_BH_Crump`，该子程序内部包含 `set_output` (控制夹具) 和 `wait_input` (等待夹具传感器反馈)。
- **"等待 X 信号"** -> `wait_input` (机器人内部信号) 或 `wait_external_io_input` (外部设备 IO 信号) 或 `wait_block` (复合条件)。
- **"设置机器人速度为低速/常速"** -> `set_speed` 块，参数为速度百分比。
- **"可选/禁用逻辑"** -> 对应块添加 `disabled="true"`。
- **"流程结束/返回"** -> `return` 块。

### 示例输出 (机器人操作详细流程步骤实例)

## 主程序步骤细化

1. 选择**默认机器人(例如 "dobot_mg400")** (Block Type: `select_robot`)
2. **启动电机(例如 "on")** (Block Type: `set_motor`)
3. 设置**用于流程控制的数值变量 (例如 "N5") 为其初始判断值 (例如 2)** (Block Type: `set_number`)
4. 开始循环 - 循环内操作: (Block Type: `loop`)
5. 条件判断 - IF 条件: **数值变量 (例如 "N5") 等于其初始设定值 (例如 2)** - DO (如果条件为真): (Block Type: `controls_if`)
6. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
7. 等待外部 I/O 输入 (**指定 I/O 编号, 指定引脚, 指定状态 (例如 I/O 编号: 1, 引脚: "0", 状态: "on")**) (Block Type: `wait_external_io_input`) (此块被禁用)
8. 调用子程序 "BRG_Get_BRG" (获取轴承) (Block Type: `procedures_callnoreturn`)
9. 等待复合条件 - 条件: (**指定的复合外部 I/O 条件 (例如 (外部 I/O (I/O 编号 1) 引脚 "3" 等于 逻辑值 真) 与 (外部 I/O (I/O 编号 1) 引脚 "4" 等于 逻辑值 真))**) (Block Type: `wait_block`) (此块被禁用)
10. 调用子程序 "CNV_Get_BH" (从传送带获取轴承座) (Block Type: `procedures_callnoreturn`)
11. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
12. 等待机器人**指定输入引脚达到预设状态 (例如引脚 "12" 为 "on")** (Block Type: `wait_input`)
13. 调用子程序 "RMC_Put_BH&BRG" (将轴承座和轴承放置到右侧加工中心/工位) (Block Type: `procedures_callnoreturn`)
14. 等待机器人**指定输入引脚达到预设状态 (例如引脚 "12" 为 "off")** (Block Type: `wait_input`)
15. 设置机器人**指定输出引脚为预设状态 (例如引脚 "6" 为 "on")** (Block Type: `set_output`)
16. 等待复合条件 - 条件: (**指定的机器人复合 I/O 条件 (例如 (机器人 I/O 引脚 "10" 等于 逻辑值 真) 或 (机器人 I/O 引脚 "11" 等于 逻辑值 真))**) (Block Type: `wait_block`)
17. 调用子程序 "RMC_Get_BH" (从右侧加工中心/工位获取轴承座) (Block Type: `procedures_callnoreturn`)
18. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
19. 调用子程序 "LMC_Put_BH" (将轴承座放置到左侧加工中心/工位) (Block Type: `procedures_callnoreturn`)
20. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
21. 调用子程序 "CNV_Get_PLT" (从传送带获取托盘/板) (Block Type: `procedures_callnoreturn`)
22. 调用子程序 "CNV_Put_PLT" (将托盘/板放置到传送带) (Block Type: `procedures_callnoreturn`)
23. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
24. 调用子程序 "LMC_Get_BH" (从左侧加工中心/工位获取轴承座) (Block Type: `procedures_callnoreturn`)
25. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
26. 调用子程序 "CNV_Put_BH" (将轴承座放置到传送带) (Block Type: `procedures_callnoreturn`)
27. 在**指定定时器变量 (例如 "N483")** 的持续时间内设置外部 I/O 输出 (**指定 I/O 编号, 指定引脚, 指定状态** (例如 I/O 编号: 1, 引脚: "3", 状态: "on")) (Block Type: `set_external_io_output_during`) (此块被禁用)
28. 返回 (Block Type: `return`)

## 子程序步骤细化

1.1. **定义子程序 "BRG_Get_BRG" (获取轴承)** (Block Type: `procedures_defnoreturn`)
1.2. PTP 移动到**轴承抓取区域的预备点 (例如 "P21")** (Block Type: `moveP`)
1.3. PTP 移动到**轴承上方的接近点 (例如 "P22")** (Block Type: `moveP`)
1.4. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.5. PTP 移动到**轴承的精确抓取点 (例如 "P23")** (Block Type: `moveP`)
1.6. 调用子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
1.7. PTP 移动到**轴承抓取后的抬起点 (例如 "P25")** (Block Type: `moveP`)
1.8. PTP 移动到**轴承抓取后的离开点 (例如 "P26")** (Block Type: `moveP`)
1.9. PTP 移动到**轴承抓取流程的结束/返回点 (例如 "P21")** (Block Type: `moveP`)

2.1. **定义子程序 "Open_BH_Crump" (打开轴承座夹具)** (Block Type: `procedures_defnoreturn`)
2.2. 等待**指定的定时器变量 (例如 "N483", 用于操作延时)** (Block Type: `wait_timer`)
2.3. 设置机器人**夹具控制输出引脚 (例如引脚 "1") 为打开状态 (例如 "on")** (Block Type: `set_output`)
2.4. 等待机器人**夹具状态反馈输入引脚 (例如引脚 "0") 为打开完成状态 (例如 "on")** (Block Type: `wait_input`)

3.1. **定义子程序 "CNV_Get_BH" (从传送带获取轴承座)** (Block Type: `procedures_defnoreturn`)
3.2. PTP 移动到**传送带旁轴承座抓取的预备点 (例如 "P31")** (Block Type: `moveP`)
3.3. PTP 移动到**传送带上轴承座上方的接近点 (例如 "P32")** (Block Type: `moveP`)
3.4. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
3.5. PTP 移动到**传送带上轴承座的精确抓取点 (例如 "P33")** (Block Type: `moveP`)
3.6. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
3.7. PTP 移动到**传送带轴承座抓取后的抬起点 (例如 "P32")** (Block Type: `moveP`)
3.8. PTP 移动到**传送带轴承座抓取流程的结束/返回点 (例如 "P31")** (Block Type: `moveP`)

4.1. **定义子程序 "Close_BH_Crump" (关闭轴承座夹具)** (Block Type: `procedures_defnoreturn`)
4.2. 等待**指定的定时器变量 (例如 "N482", 用于操作延时)** (Block Type: `wait_timer`)
4.3. 设置机器人**夹具控制输出引脚 (例如引脚 "1") 为关闭状态 (例如 "off")** (Block Type: `set_output`)
4.4. 等待机器人**夹具状态反馈输入引脚 (例如引脚 "1") 为关闭完成状态 (例如 "on")** (Block Type: `wait_input`)

5.1. **定义子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具)** (Block Type: `procedures_defnoreturn`)
5.2. 等待**指定的定时器变量 (例如 "N482", 用于操作延时)** (Block Type: `wait_timer`)
5.3. 设置机器人**夹具控制输出引脚 (例如引脚 "2") 为打开状态 (例如 "on")** (Block Type: `set_output`)
5.4. 等待机器人**夹具状态反馈输入引脚 (例如引脚 "2") 为打开完成状态 (例如 "on")** (Block Type: `wait_input`)

6.1. **定义子程序 "RMC_Put_BH&BRG" (将轴承座和轴承放置到右侧加工中心/工位)** (Block Type: `procedures_defnoreturn`)
6.2. PTP 移动到**RMC（右加工中心）放置操作的预备点 (例如 "P20")** (Block Type: `moveP`)
6.3. PTP 移动到**RMC 工位附近的接近点 (例如 "P11")** (Block Type: `moveP`)
6.4. PTP 移动到**RMC 轴承座放置位置的上方向点 (例如 "P12")** (Block Type: `moveP`)
6.5. PTP 移动到**RMC 轴承座的精确放置点 (例如 "P14")** (Block Type: `moveP`)
6.6. PTP 移动到**RMC 轴承座放置后的姿态调整/抬起点 (例如 "P15")** (Block Type: `moveP`)
6.7. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
6.8. 设置机器人速度为**低速 (例如 10%, 用于精确放置)** (Block Type: `set_speed`)
6.9. PTP **精确移动**到**RMC 轴承座的放置点 (例如 "P14")** (Block Type: `moveP`)
6.10. 恢复机器人速度为**常速 (例如 100%)** (Block Type: `set_speed`)
6.11. PTP 移动到**RMC 轴承放置位置的上方向点 (例如 "P13")** (Block Type: `moveP`)
6.12. PTP 移动到**RMC 轴承的精确放置点 (例如 "P16")** (Block Type: `moveP`)
6.13. PTP 移动到**RMC 轴承放置后的姿态调整/抬起点 (例如 "P17")** (Block Type: `moveP`)
6.14. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
6.15. 设置机器人速度为**低速 (例如 10%, 用于精确放置)** (Block Type: `set_speed`)
6.16. PTP **精确移动**到**RMC 轴承的放置点 (例如 "P16")** (Block Type: `moveP`)
6.17. 恢复机器人速度为**常速 (例如 100%)** (Block Type: `set_speed`)
6.18. PTP 移动到**RMC 放置操作完成后的抬起点 (例如 "P12")** (Block Type: `moveP`)
6.19. PTP 移动到**RMC 放置操作完成后的离开点 (例如 "P11")** (Block Type: `moveP`)

7.1. **定义子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具)** (Block Type: `procedures_defnoreturn`)
7.2. 等待**指定的定时器变量 (例如 "N482", 用于操作延时)** (Block Type: `wait_timer`)
7.3. 设置机器人**夹具控制输出引脚 (例如引脚 "2") 为关闭状态 (例如 "off")** (Block Type: `set_output`)
7.4. 等待机器人**夹具状态反馈输入引脚 (例如引脚 "3") 为关闭完成状态 (例如 "on")** (Block Type: `wait_input`)

8.1. **定义子程序 "RMC_Get_BH" (从右侧加工中心/工位获取轴承座)** (Block Type: `procedures_defnoreturn`)
8.2. PTP 移动到**RMC 工位附近的接近点 (例如 "P11")** (Block Type: `moveP`)
8.3. PTP 移动到**RMC 已组装件抓取位置的上方点 (例如 "P12")** (Block Type: `moveP`)
8.4. PTP 移动到**RMC 已组装件的精确抓取点 (例如 "P14")** (Block Type: `moveP`)
8.5. PTP 移动到**RMC 已组装件抓取后的姿态调整点 (例如 "P15")** (Block Type: `moveP`)
8.6. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
8.7. PTP 移动到**RMC 已组装件抓取后的抬起点 (例如返回 "P14" 后抬升或直接到 "P12")** (Block Type: `moveP`)
8.8. PTP 移动到**RMC 抓取操作完成后的抬高点 (例如 "P12")** (Block Type: `moveP`)
8.9. PTP 移动到**RMC 抓取操作完成后的离开点 (例如 "P11")** (Block Type: `moveP`)
8.10. PTP 移动到**RMC 抓取流程的结束/返回点 (例如 "P20")** (Block Type: `moveP`)

9.1. **定义子程序 "LMC_Put_BH" (将轴承座放置到左侧加工中心/工位)** (Block Type: `procedures_defnoreturn`)
9.2. PTP 移动到**LMC（左加工中心）放置操作的预备点 (例如 "P41")** (Block Type: `moveP`)
9.3. PTP 移动到**LMC 工位上方的接近点 (例如 "P42")** (Block Type: `moveP`)
9.4. PTP 移动到**LMC 的精确放置点 (例如 "P43")** (Block Type: `moveP`)
9.5. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
9.6. PTP 移动到**LMC 放置后的抬起点 (例如 "P42")** (Block Type: `moveP`)
9.7. PTP 移动到**LMC 放置后的离开点 (例如 "P41")** (Block Type: `moveP`)
9.8. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)

10.1. **定义子程序 "CNV_Get_PLT" (从传送带获取托盘/板)** (Block Type: `procedures_defnoreturn`)
10.2. PTP 移动到**传送带旁托盘抓取的预备点 (例如 "P34")** (Block Type: `moveP`)
10.3. PTP 移动到**传送带上托盘上方的接近点 (例如 "P35")** (Block Type: `moveP`)
10.4. 设置机器人速度为**低速 (例如 10%, 用于精确抓取)** (Block Type: `set_speed`)
10.5. PTP **精确移动**到**传送带上托盘的抓取点 (例如 "P36")** (Block Type: `moveP`)
10.6. 调用子程序 "Close_BRG&PLT_Crump" (关闭操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
10.7. PTP 移动到**传送带托盘抓取后的抬起点 (例如 "P35")** (Block Type: `moveP`)
10.8. 恢复机器人速度为**常速 (例如 100%)** (Block Type: `set_speed`)
10.9. PTP 移动到**传送带托盘抓取流程的结束/返回点 (例如 "P34")** (Block Type: `moveP`)

11.1. **定义子程序 "CNV_Put_PLT" (将托盘/板放置到传送带)** (Block Type: `procedures_defnoreturn`)
11.2. PTP 移动到**传送带托盘放置位置的上方向点 (例如 "P37")** (Block Type: `moveP`)
11.3. PTP 移动到**传送带托盘的精确放置点 (例如 "P38")** (Block Type: `moveP`)
11.4. 调用子程序 "Open_BRG&PLT_Crump" (打开操作轴承和托盘/板的夹具) (Block Type: `procedures_callnoreturn`)
11.5. PTP 移动到**传送带托盘放置后的抬起点 (例如 "P37")** (Block Type: `moveP`)
11.6. PTP 移动到**传送带托盘放置流程的结束/返回点 (例如 "P34")** (Block Type: `moveP`)

12.1. **定义子程序 "LMC_Get_BH" (从左侧加工中心/工位获取轴承座)** (Block Type: `procedures_defnoreturn`)
12.2. PTP 移动到**LMC 抓取操作的预备点 (例如 "P41")** (Block Type: `moveP`)
12.3. PTP 移动到**LMC 工位上方的接近点 (例如 "P42")** (Block Type: `moveP`)
12.4. PTP 移动到**LMC 的精确抓取点 (例如 "P43")** (Block Type: `moveP`)
12.5. 调用子程序 "Close_BH_Crump" (关闭轴承座夹具) (Block Type: `procedures_callnoreturn`)
12.6. PTP 移动到**LMC 抓取后的抬起点 (例如 "P42")** (Block Type: `moveP`)
12.7. PTP 移动到**LMC 抓取后的离开点 (例如 "P41")** (Block Type: `moveP`)

13.1. **定义子程序 "CNV_Put_BH" (将轴承座放置到传送带)** (Block Type: `procedures_defnoreturn`)
13.2. PTP 移动到**传送带上已组装件放置位置的上方向点 (例如 "P39")** (Block Type: `moveP`)
13.3. PTP 移动到**传送带上已组装件的精确放置点 (例如 "P40", 意指放到托盘上)** (Block Type: `moveP`)
13.4. 调用子程序 "Open_BH_Crump" (打开轴承座夹具) (Block Type: `procedures_callnoreturn`)
13.5. PTP 移动到**传送带已组装件放置后的抬起点 (例如 "P39")** (Block Type: `moveP`)
13.6. PTP 移动到**初始/安全点位 (例如 "P1")** (Block Type: `moveP`)
13.7. 返回 (Block Type: `return`)
