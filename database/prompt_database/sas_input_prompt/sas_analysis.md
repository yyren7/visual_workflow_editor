中文描述 (原始对照组):
该 XML 文件定义了一个名为 "SwingArm" (根据文件路径推断) 的机器人或自动化系统的任务流程。该流程主要包括以下几个方面：
初始化与事件处理：启动线程，连接外部 I/O 设备 (DIO000)，并设置了多个事件。这些事件基于自定义标志位 (如 F481, F482) 或外部 I/O 信号 (如引脚 12 的状态) 来控制外部输出 (如引脚 13, 14 的开关) 或触发机器人停止。
子程序定义：定义了一系列可重用的子程序（procedures），用于执行特定的操作序列，例如：
BRG_Get_BRG: 从轴承供给处获取轴承。
CNV_Get_BH: 从传送带获取轴套。
Open_BH_Crump / Close_BH_Crump: 打开/关闭轴套夹爪。
Open_BRG&PLT_Crump / Close_BRG&PLT_Crump: 打开/关闭轴承和托盘夹爪。
RMC_Put_BH&BRG: 将轴套和轴承放置到旋转加工中心。
RMC_Get_BH: 从旋转加工中心获取轴套。
LMC_Put_BH: 将轴套放置到线性加工中心。
CNV_Get_PLT: 从传送带获取托盘。
CNV_Put_PLT: 将托盘放置到传送带。
LMC_Get_BH: 从线性加工中心获取轴套。
CNV_Put_BH: 将轴套放置到传送带。
主控制流程：
选择名为 "fairino_FR" 的机器人并启动电机。
设置一个循环，在循环中根据变量 N5 的值 (初始为 2) 执行一系列操作。
主要操作包括：机器人移动到预设点位 (P1, P11-P17, P20-P26, P31-P43 等)，调用上述定义的子程序完成取放料任务，等待外部 I/O 信号或内部条件满足，控制机器人夹爪的开合，以及设置机器人速度。
这个流程涉及到在不同工位（如轴承供给、传送带、旋转加工中心 RMC、线性加工中心 LMC）之间搬运轴承(BRG)、轴套(BH)和托盘(PLT)。
总的来说，该文件描述了一个复杂的自动化装配或物料搬运任务，机器人通过精确的移动和 I/O 控制，在多个工位之间协调完成一系列取放操作。

中文描述 (优化版 - 明确 Blockly 块类型):
该 XML 文件定义了一个名为 "SwingArm" (根据文件路径推断) 的机器人或自动化系统的任务流程。该流程主要通过特定的 Blockly XML 块类型实现，具体包括以下几个方面：

初始化与事件处理：
使用 `start_thread` 块启动一个并行线程（通常条件设置为始终为真，例如使用 `logic_boolean` 块设为 TRUE）。
在该线程的 `DO` 语句内，首先使用 `connect_external_io` 块连接到名为 "DIO000" 的外部 I/O 设备（例如，io_no: 1）。
接着，使用多个 `create_event` 块来定义事件驱动的逻辑：

- 对于外部输出控制（如控制引脚 13, 14 的开关）：在 `create_event` 块的 `EVENT` 语句内，使用 `set_external_io_output_upon` 块。其条件通常由 `logic_custom_flag` 块（如 F481, F482）提供，指定 `io_no`, `output_pin_name`, `out_state` 和 `trigger_condition`。
- 对于机器人停止：在 `create_event` 块的 `EVENT` 语句内，使用 `stop_robot_upon` 块。其条件可以由 `logic_compare` 块（比较 `external_io` 读取的引脚状态和 `logic_boolean` 值）构成。

子程序定义：
使用 `procedures_defnoreturn` 块定义一系列可重用的子程序（例如，通过 `NAME` 字段指定名称）。子程序内部的 `STACK` 语句包含一系列操作块：

- `BRG_Get_BRG`: 从轴承供给处获取轴承。内部可能包含多个 `moveP` 块用于机器人移动，以及通过 `procedures_callnoreturn` 调用夹爪控制子程序。
- `CNV_Get_BH`: 从传送带获取轴套。类似地，包含 `moveP` 移动和夹爪操作调用。
- `Open_BH_Crump` / `Close_BH_Crump`: 打开/关闭轴套夹爪。这类子程序通常使用机器人本体 I/O 进行控制，例如通过 `set_output` 块（指定 `output_pin_name` 和 `out_state`）来操作夹爪，并配合 `wait_input` 块等待夹爪传感器信号，可能还会使用 `wait_timer` 块进行延时。 **注意：应使用 `set_output` 操作机器人 I/O，而非 `set_external_io_output_during` 或 `set_external_io_output_upon`。**
- `Open_BRG&PLT_Crump` / `Close_BRG&PLT_Crump`: 打开/关闭轴承和托盘夹爪。实现方式与轴套夹爪类似，使用 `set_output`, `wait_input`, `wait_timer`。
- `RMC_Put_BH&BRG`: 将轴套和轴承放置到旋转加工中心。包含 `moveP` 移动和夹爪操作调用。
- `RMC_Get_BH`: 从旋转加工中心获取轴套。包含 `moveP` 移动和夹爪操作调用。
- `LMC_Put_BH`: 将轴套放置到线性加工中心。包含 `moveP` 移动和夹爪操作调用。
- `CNV_Get_PLT`: 从传送带获取托盘。包含 `moveP` 移动和夹爪操作调用。
- `CNV_Put_PLT`: 将托盘放置到传送带。包含 `moveP` 移动和夹爪操作调用。
- `LMC_Get_BH`: 从线性加工中心获取轴套。包含 `moveP` 移动和夹爪操作调用。
- `CNV_Put_BH`: 将轴套放置到传送带。包含 `moveP` 移动和夹爪操作调用。

主控制流程：
首先，使用 `select_robot` 块选择名为 "fairino_FR" 的机器人。
然后，使用 `set_motor` 块将伺服电机状态设置为 "on"。
使用 `set_number` 块（配合 `math_number` 块提供数值）将变量 N5 的初始值设置为 2。
使用 `loop` 块构建主循环。在循环的 `DO` 语句内：

- 可以使用 `controls_if` 块进行条件判断，其条件可能由 `logic_compare`（例如比较 `math_custom_number` 类型的变量 N5 和 `math_number` 常量）构成。
- 机器人移动：必须使用 `moveP` 块（而不是 `moveL`）进行点位移动到预设点位 (P1, P11-P17, P20-P26, P31-P43 等)，并确保提供所有必要的运动控制参数（如 `point_name_list`, `control_x` 等）。
- 调用子程序：使用 `procedures_callnoreturn` 块调用已定义的子程序来完成取放料等任务。
- 等待条件：
  - 使用 `wait_external_io_input` 块等待外部 I/O 信号。
  - 使用 `wait_input` 块等待机器人 I/O 信号。
  - 使用 `wait_block` 块（其条件通常由 `logic_operation` 或 `logic_compare` 等逻辑块构成）等待内部条件满足。
- 机器人夹爪控制：使用 `set_output` 块（指定 `output_pin_name` 和 `out_state`）控制机器人夹爪的开合。
- 速度设置：可使用 `set_speed` 块设定机器人运行速度。
  此流程涉及到在不同工位（如轴承供给、传送带、旋转加工中心 RMC、线性加工中心 LMC）之间通过 `moveP` 搬运轴承(BRG)、轴套(BH)和托盘(PLT)。
  循环的继续由 `loop` 块自身管理，子程序或特定逻辑段的结束可能使用 `return` 块（例如，在 `CNV_Put_BH` 子程序的末尾，返回到调用它的主流程或上一级循环）。

总的来说，该文件描述了一个复杂的自动化装配或物料搬运任务，机器人通过精确的 `moveP` 移动和基于特定 Blockly 块（如 `set_output`, `wait_input`, `set_external_io_output_upon` 等）的 I/O 控制，在多个工位之间协调完成一系列取放操作。
English Description:
This XML file defines a task flow for a robot or automated system, likely named "SwingArm" (inferred from the file path). The flow primarily involves the following aspects:
Initialization and Event Handling: It starts a thread, connects to an external I/O device (DIO000), and sets up multiple events. These events control external outputs (e.g., switching pins 13, 14 ON/OFF) or trigger a robot stop based on custom flags (e.g., F481, F482) or external I/O signals (e.g., state of pin 12).
Subroutine Definitions: A series of reusable subroutines (procedures) are defined to perform specific operational sequences, such as:
BRG_Get_BRG: Get a bearing from the bearing supply.
CNV_Get_BH: Get a bushing from the conveyor.
Open_BH_Crump / Close_BH_Crump: Open/Close the bushing clamp.
Open_BRG&PLT_Crump / Close_BRG&PLT_Crump: Open/Close the bearing and pallet clamp.
RMC_Put_BH&BRG: Place the bushing and bearing onto the Rotary Machining Center.
RMC_Get_BH: Get the bushing from the Rotary Machining Center.
LMC_Put_BH: Place the bushing onto the Linear Machining Center.
CNV_Get_PLT: Get a pallet from the conveyor.
CNV_Put_PLT: Place a pallet onto the conveyor.
LMC_Get_BH: Get the bushing from the Linear Machining Center.
CNV_Put_BH: Place the bushing onto the conveyor.
Main Control Flow:
Selects a robot named "fairino_FR" and turns on its motor.
Sets up a loop that executes a series of operations based on the value of a variable N5 (initially 2).
The main operations include: moving the robot to predefined points (P1, P11-P17, P20-P26, P31-P43, etc.), calling the subroutines defined above to complete pick-and-place tasks, waiting for external I/O signals or internal conditions to be met, controlling the opening and closing of the robot's gripper, and setting robot speed.
This flow involves transporting bearings (BRG), bushings (BH), and pallets (PLT) between different stations (e.g., bearing supply, conveyor, Rotary Machining Center RMC, Linear Machining Center LMC).
In summary, the file describes a complex automated assembly or material handling task where the robot, through precise movements and I/O control, coordinates a series of pick-and-place operations between multiple stations.
日本語説明：
この XML ファイルは、ファイルパスから推測するに「SwingArm」という名前のロボットまたは自動化システムのタスクフローを定義しています。このフローは主に以下の側面を含んでいます。
初期化とイベント処理：スレッドを開始し、外部 I/O デバイス（DIO000）に接続し、複数のイベントを設定します。これらのイベントは、カスタムフラグ（例：F481、F482）や外部 I/O 信号（例：ピン 12 の状態）に基づいて外部出力（例：ピン 13、14 のオン/オフ）を制御したり、ロボットの停止をトリガーしたりします。
サブルーチン定義：特定の操作シーケンスを実行するための一連の再利用可能なサブルーチン（プロシージャ）が定義されています。例：
BRG_Get_BRG：ベアリング供給装置からベアリングを取得。
CNV_Get_BH：コンベアからブッシングを取得。
Open_BH_Crump / Close_BH_Crump：ブッシング用クランプを開く/閉じる。
Open_BRG&PLT_Crump / Close_BRG&PLT_Crump：ベアリングおよびパレット用クランプを開く/閉じる。
RMC_Put_BH&BRG：ブッシングとベアリングを回転マシニングセンタに配置。
RMC_Get_BH：回転マシニングセンタからブッシングを取得。
LMC_Put_BH：ブッシングをリニアマシニングセンタに配置。
CNV_Get_PLT：コンベアからパレットを取得。
CNV_Put_PLT：パレットをコンベアに配置。
LMC_Get_BH：リニアマシニングセンタからブッシングを取得。
CNV_Put_BH：ブッシングをコンベアに配置。
メイン制御フロー：
「fairino_FR」という名前のロボットを選択し、モーターをオンにします。
変数 N5 の値（初期値 2）に基づいて一連の操作を実行するループを設定します。
主な操作には、ロボットを所定の位置（P1、P11-P17、P20-P26、P31-P43 など）に移動させること、上記のサブルーチンを呼び出してピックアンドプレース作業を完了させること、外部 I/O 信号または内部条件が満たされるのを待つこと、ロボットグリッパーの開閉を制御すること、ロボットの速度を設定することが含まれます。
このフローは、ベアリング（BRG）、ブッシング（BH）、パレット（PLT）を異なるステーション（例：ベアリング供給、コンベア、回転マシニングセンタ RMC、リニアマシニングセンタ LMC）間で搬送することを含みます。
要約すると、このファイルは複雑な自動組立またはマテリアルハンドリングタスクを記述しており、ロボットが精密な動作と I/O 制御を通じて、複数のステーション間で一連のピックアンドプレース操作を連携して実行します。

中文 ver2：
请根据以下机器人操作流程的 XML 结构，生成一份详细的、步骤化的自然语言描述。确保严格按照 XML 中块的类型和顺序进行描述，并准确反映所有参数和逻辑关系。

**全局流程与并行任务:**

1.  **启动并行线程 (Block Type: `start_thread`, id: `o8p1r=wifD!`X8`A;EdA`)**

    - 启动条件: 逻辑值为 TRUE (Block Type: `logic_boolean`)
    - 并行执行的操作:
      - 连接外部 I/O 设备 (Block Type: `connect_external_io`, id: `CK|P-=h:/X4bS_z#nsfO`)
        - 设备名称: "DIO000"
        - 外部设备制造商: "contec"
        - I/O 编号: 1

2.  **创建事件 1 (Block Type: `create_event`, id: `CiCQZWpGTtG^Ce#tBlkc`)**

    - 事件内容:
      - 当条件满足时设置外部 I/O 输出 (Block Type: `set_external_io_output_upon`, id: `ZwtPi4?(mHi#;cMAH@tb`)
        - I/O 编号: 1
        - 输出引脚名称: "14"
        - 输出状态: "on"
        - 触发条件类型: "steady"
        - 条件: 自定义标志 "F481" 为 TRUE (Block Type: `logic_custom_flag`)
      - (紧接着上一个操作) 当条件满足时设置外部 I/O 输出 (Block Type: `set_external_io_output_upon`, id: `GEgj|79{NC3r)m0Nid)]`)
        - I/O 编号: 1
        - 输出引脚名称: "14"
        - 输出状态: "off"
        - 触发条件类型: "steady"
        - 条件: 自定义标志 "F482" 为 TRUE (Block Type: `logic_custom_flag`)

3.  **创建事件 2 (Block Type: `create_event`, id: `b~f6mm{BhMf$-9DJ%^5#`)**

    - 事件内容:
      - 当条件满足时设置外部 I/O 输出 (Block Type: `set_external_io_output_upon`, id: `1W]h7;W_Be=FE4z)*??H`)
        - I/O 编号: 1
        - 输出引脚名称: "13"
        - 输出状态: "on"
        - 触发条件类型: "steady"
        - 条件: 自定义标志 "F482" 为 TRUE (Block Type: `logic_custom_flag`)
      - (紧接着上一个操作) 当条件满足时设置外部 I/O 输出 (Block Type: `set_external_io_output_upon`, id: `h+8Ncgw!IPm^ur?!)U$*`)
        - I/O 编号: 1
        - 输出引脚名称: "13"
        - 输出状态: "off"
        - 触发条件类型: "steady"
        - 条件: 自定义标志 "F481" 为 TRUE (Block Type: `logic_custom_flag`)

4.  **创建事件 3 (Block Type: `create_event`, id: `l93,dxV]`3I9%6JS(6[L`)**
    - 事件内容:
      - 当条件满足时停止机器人 (Block Type: `stop_robot_upon`, id: `jkw-BGrJdQTsNm2!wi%%`)
        - 触发条件类型: "rising" (当条件从 FALSE 变为 TRUE 时触发)
        - 条件: 外部 I/O (Block Type: `external_io`, id: `C5nr,-sOn7@$Fu!+5~?E`) 的输入引脚 "12" (I/O 编号 1) 的值等于逻辑值 FALSE (Block Type: `logic_compare`, OP: EQ)

**子程序定义:**

5.  **定义子程序 "BRG_Get_BRG" (Block Type: `procedures_defnoreturn`, id: `3w@`e,Srk|Z{nSNG]@.I`)**

    - 步骤 1: PTP 移动到点 "P21" (Block Type: `moveP`, id: `,2yH^ICxw|iVz)N%XM%7`)
    - 步骤 2: PTP 移动到点 "P22" (Block Type: `moveP`, id: `:N%r^Sx(H}TGn7)H$@N{`)
    - 步骤 3: 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`, id: `UGHu(Y@|2=E67^AK;blk`)
    - 步骤 4: PTP 移动到点 "P23" (Block Type: `moveP`, id: `~YPJ(06ieyn-)g0=IdOj`)
    - 步骤 5: 调用子程序 "Close_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`, id: `*m^;f!\`L5{$Z|qORpmtf`)
    - 步骤 6: PTP 移动到点 "P25" (Block Type: `moveP`, id: `~1O\`jZbP_f1Lv22q~b@/`)
    - 步骤 7: PTP 移动到点 "P26" (Block Type: `moveP`, id: `wyLO(YBp6(bm!c8fmtBE`)
    - 步骤 8: PTP 移动到点 "P21" (Block Type: `moveP`, id: `Ari[F]q,?%alYGOE\`Ysf`)

6.  **定义子程序 "CNV_Get_BH" (Block Type: `procedures_defnoreturn`, id: `vxh86EiGnsh*.NKo;q[Z`)**

    - 步骤 1: PTP 移动到点 "P31" (Block Type: `moveP`, id: `Z)s0a+%k36Y!kcaY$MaG`)
    - 步骤 2: PTP 移动到点 "P32" (Block Type: `moveP`, id: `jMh[%@.*[bGt#%SkxG?`)
    - 步骤 3: 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `[SOKxNOt*=%$i^ppK-CG`)
    - 步骤 4: PTP 移动到点 "P33" (Block Type: `moveP`, id: `9\`Vy3whL)|%~^?|\*v9YN`)
    - 步骤 5: 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `FOYjh4RYiVby41Y4uG;~`)
    - 步骤 6: PTP 移动到点 "P32" (Block Type: `moveP`, id: `$F=K/_x8e67-Ix/B$A-6`)
    - 步骤 7: PTP 移动到点 "P31" (Block Type: `moveP`, id: `$,5\`tkZJB4+gO!@j,RnQ`)

7.  **定义子程序 "Open_BH_Crump" (Block Type: `procedures_defnoreturn`, id: `iPd-7$RSaQv!N};D/l5I`)**

    - 步骤 1: 等待定时器变量 "N483" (Block Type: `wait_timer`, id: `+6]%NgxiX#VC)aRm|hvn`)
    - 步骤 2: 设置机器人输出引脚 "1" 为 "on" (Block Type: `set_output`, id: `{~Ky-,SwbW$s[t,tPx.g`)
    - 步骤 3: 等待机器人输入引脚 "0" 状态为 "on" (Block Type: `wait_input`, id: `P,T]ydU/\`vmVRXHX\`h2A`)

8.  **定义子程序 "Close_BH_Crump" (Block Type: `procedures_defnoreturn`, id: `zKEOxm?POaH50o[sLS:Q`)**

    - 步骤 1: 等待定时器变量 "N482" (Block Type: `wait_timer`, id: `DkU^0=yTs17W.$[I|meX`)
    - 步骤 2: 设置机器人输出引脚 "1" 为 "off" (Block Type: `set_output`, id: `.RY:j3BWY4PDyEkt~:P,`)
    - 步骤 3: 等待机器人输入引脚 "1" 状态为 "on" (Block Type: `wait_input`, id: `pyl90xYJik?l?r!;|QAR`)

9.  **定义子程序 "RMC_Put_BH&BRG" (Block Type: `procedures_defnoreturn`, id: `l8#=FTE.:)$vK~iH;|$x`)**

    - 步骤 1: PTP 移动到点 "P20" (Block Type: `moveP`, id: `9[N1}9OS18.r|h{JCKca`)
    - 步骤 2: PTP 移动到点 "P11" (Block Type: `moveP`, id: `l53*ZVh%[fONdV-knC$h`)
    - 步骤 3: PTP 移动到点 "P12" (Block Type: `moveP`, id: `E\`v(EHfktZ,~/1/axHpI`)
    - 步骤 4: PTP 移动到点 "P14" (Block Type: `moveP`, id: `fIwNIr1];5yl$5WghJSF`)
    - 步骤 5: PTP 移动到点 "P15" (Block Type: `moveP`, id: `vHP~Sg.WP\`c?[L?^EZs\*`)
    - 步骤 6: 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `U4zwapSQwOn}T7cJuYnA`)
    - 步骤 7: 设置机器人速度为 10% (Block Type: `set_speed`, id: `cNJhwBYpSZ-NuUT*UI)u`)
    - 步骤 8: PTP 移动到点 "P14" (Block Type: `moveP`, id: `?AcK!_[}gjYeR/9rb%d7`)
    - 步骤 9: 设置机器人速度为 100% (Block Type: `set_speed`, id: `V[jVfb;\`#y7p?Pt52J{6`)
    - 步骤 10: PTP 移动到点 "P13" (Block Type: `moveP`, id: `F-;evPHBoWFcRd~[s-o-`)
    - 步骤 11: PTP 移动到点 "P16" (Block Type: `moveP`, id: `)9a(7]y_~$V6D?V-Q\`Et`)
    - 步骤 12: PTP 移动到点 "P17" (Block Type: `moveP`, id: `;L!TX1O2Uj8ij,!Bx*%`)
    - 步骤 13: 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`, id: `8oG*R}l}{I4G8?gl11\`i`)
    - 步骤 14: 设置机器人速度为 10% (Block Type: `set_speed`, id: `a8PEjyb+zHzOkMQ!YUC/`)
    - 步骤 15: PTP 移动到点 "P16" (Block Type: `moveP`, id: `I6L*ZoClH;PPlW%d4JF2`)
    - 步骤 16: 设置机器人速度为 100% (Block Type: `set_speed`, id: `{qN14Mwvuq,#d$r\`A+;;`)
    - 步骤 17: PTP 移动到点 "P12" (Block Type: `moveP`, id: `` }`:|{Nb~Dh{Nd7.D?bQ_ ``)
    - 步骤 18: PTP 移动到点 "P11" (Block Type: `moveP`, id: `Hf({kAVpqMmwxhP2fTfy`)

10. **定义子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_defnoreturn`, id: `cZc{w-$Y6Z5,=^UG1o/M`)**

    - 步骤 1: 等待定时器变量 "N482" (Block Type: `wait_timer`, id: `!1n|;]GgalOgUeZ=+fVN`)
    - 步骤 2: 设置机器人输出引脚 "2" 为 "on" (Block Type: `set_output`, id: `O/xp*9_RBp?!Go2T@uNZ`)
    - 步骤 3: 等待机器人输入引脚 "2" 状态为 "on" (Block Type: `wait_input`, id: `Kh4G^X%OePdx#28@8PZ%`)

11. **定义子程序 "Close_BRG&PLT_Crump" (Block Type: `procedures_defnoreturn`, id: `z3xF#vz1/X%=*9X=XIY(`)**

    - 步骤 1: 等待定时器变量 "N482" (Block Type: `wait_timer`, id: `ssulib)|ven79CL-(i,@`)
    - 步骤 2: 设置机器人输出引脚 "2" 为 "off" (Block Type: `set_output`, id: `*.h,uAR}[|v.}.O*J#@)`)
    - 步骤 3: 等待机器人输入引脚 "3" 状态为 "on" (Block Type: `wait_input`, id: `]Cz_2$8*wVw]o+tn=oXl`)

12. **定义子程序 "RMC_Get_BH" (Block Type: `procedures_defnoreturn`, id: `[lxq/b\`})^Ak9Ua@9gm{`)**

    - 步骤 1: PTP 移动到点 "P11" (Block Type: `moveP`, id: `T5QW!$#!*FtV%r:q_B*J`)
    - 步骤 2: PTP 移动到点 "P12" (Block Type: `moveP`, id: `9U.sp{E5L$]_+w=WsOkF`)
    - 步骤 3: PTP 移动到点 "P14" (Block Type: `moveP`, id: `b-oqrMGat1)+2+Ma]OS@`)
    - 步骤 4: PTP 移动到点 "P15" (Block Type: `moveP`, id: `9Y#i.!Isz}JM~FEZ6urD`)
    - 步骤 5: 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `Hl%!a|d/0x)JfnnbQ6ZG`)
    - 步骤 6: PTP 移动到点 "P14" (Block Type: `moveP`, id: `JkUz1-P@~dU!nIf)+XfH`)
    - 步骤 7: PTP 移动到点 "P12" (Block Type: `moveP`, id: `r-ew_.63NG@_fplihLuy`)
    - 步骤 8: PTP 移动到点 "P11" (Block Type: `moveP`, id: `nzQNo)7kw!xyW1KgIAbw`)
    - 步骤 9: PTP 移动到点 "P20" (Block Type: `moveP`, id: `,A^mPv$Mx!aKrii{_*vJ`)

13. **定义子程序 "LMC_Put_BH" (Block Type: `procedures_defnoreturn`, id: `OIHZS:{biEQi:4[fwyrj`)**

    - 步骤 1: PTP 移动到点 "P41" (Block Type: `moveP`, id: `]E!]nxX:@G.!YG]DU+6|`)
    - 步骤 2: PTP 移动到点 "P42" (Block Type: `moveP`, id: `S\`\_{t-Z%ii-3:L9E@TUV`)
    - 步骤 3: PTP 移动到点 "P43" (Block Type: `moveP`, id: `DbFn_|f4SCz3_|MG\`Kl]`)
    - 步骤 4: 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `Ic1PsIHqa=je8SVi}Dj=`)
    - 步骤 5: PTP 移动到点 "P42" (Block Type: `moveP`, id: `5oj_.Xy)/atu%1R/(~t$`)
    - 步骤 6: PTP 移动到点 "P41" (Block Type: `moveP`, id: `R#bskPM^Jabkf8H)^M:[`)
    - 步骤 7: PTP 移动到点 "P1" (Block Type: `moveP`, id: `Ayy9}:^kR}Nt/-qeG_D2`)

14. **定义子程序 "CNV_Get_PLT" (Block Type: `procedures_defnoreturn`, id: `6i%E*CkWU#^g{s~6k*D?`)**

    - 步骤 1: PTP 移动到点 "P34" (Block Type: `moveP`, id: `Ct0+l]@N_?.6Bdb^pyRd`)
    - 步骤 2: PTP 移动到点 "P35" (Block Type: `moveP`, id: `HuHHh.g=yj=AChGfc?Sk`)
    - 步骤 3: 设置机器人速度为 10% (Block Type: `set_speed`, id: `w{vX+k]1RH8Y7],5nMt@`)
    - 步骤 4: PTP 移动到点 "P36" (Block Type: `moveP`, id: `,*hCh,G$cq!F0ys_K4+M`)
    - 步骤 5: 调用子程序 "Close*BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`, id: `F*~,}Be|w{4t.%+y*1C*`)
    - 步骤 6: PTP 移动到点 "P35" (Block Type: `moveP`, id: `_!C?@|Cv=.*4Y4-CIkjy`)
    - 步骤 7: 设置机器人速度为 100% (Block Type: `set_speed`, id: `]RG9gxdVNJ%E!Xjex2WV`)
    - 步骤 8: PTP 移动到点 "P34" (Block Type: `moveP`, id: `wY099b-\`gihCZ7esA=D!`)

15. **定义子程序 "CNV_Put_PLT" (Block Type: `procedures_defnoreturn`, id: `xg7?gsc}+_pc$Sd2N(^C`)**

    - 步骤 1: PTP 移动到点 "P37" (Block Type: `moveP`, id: `VPr;ECbwY0RmN@,B$5tA`)
    - 步骤 2: PTP 移动到点 "P38" (Block Type: `moveP`, id: `Y*8*K^VNIyQb?hzDV)N\``)
    - 步骤 3: 调用子程序 "Open_BRG&PLT_Crump" (Block Type: `procedures_callnoreturn`, id: `5w]?;3!j]!Q/pWv#@A{j`)
    - 步骤 4: PTP 移动到点 "P37" (Block Type: `moveP`, id: `{jB42JY)xs|GEs.)3s#4`)
    - 步骤 5: PTP 移动到点 "P34" (Block Type: `moveP`, id: `z$C~y~i[+@i}jFe0a]xJ`)

16. **定义子程序 "LMC_Get_BH" (Block Type: `procedures_defnoreturn`, id: `{zrm\`lxBUY,WP7[f0tWy`)**

    - 步骤 1: PTP 移动到点 "P41" (Block Type: `moveP`, id: `A?03^M;-lNCelp$XKSIR`)
    - 步骤 2: PTP 移动到点 "P42" (Block Type: `moveP`, id: `M?;/{Qk20A\`,rZJ;;O,t`)
    - 步骤 3: PTP 移动到点 "P43" (Block Type: `moveP`, id: `KCl4d=)piyhbxtnJz7@F`)
    - 步骤 4: 调用子程序 "Close_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `7L9lP8#l5P.t]kUb(yh[`)
    - 步骤 5: PTP 移动到点 "P42" (Block Type: `moveP`, id: `BD;e05q}Ov/C.:,To(K.`)
    - 步骤 6: PTP 移动到点 "P41" (Block Type: `moveP`, id: `7oT/75[x=jqDLMV#w$d#`)

17. **定义子程序 "CNV_Put_BH" (Block Type: `procedures_defnoreturn`, id: `E/(twAoEMoNYdiB3hT.H`)**
    - 步骤 1: PTP 移动到点 "P39" (Block Type: `moveP`, id: `Nu!4a3cij*@=M|(TCEwQ`)
    - 步骤 2: PTP 移动到点 "P40" (Block Type: `moveP`, id: `` \`O#@Fo8hVkpgnfr79#?4 ``)
    - 步骤 3: 调用子程序 "Open_BH_Crump" (Block Type: `procedures_callnoreturn`, id: `rp@3LI%3S#wr]whCDVIE`)
    - 步骤 4: PTP 移动到点 "P39" (Block Type: `moveP`, id: `` \`9whTG@mol7EG^eWCtwT ``)
    - 步骤 5: PTP 移动到点 "P1" (Block Type: `moveP`, id: `P9b:7gqG;~V$-Z}b4|y\``)
    - 步骤 6: 返回 (Block Type: `return`, id: `2X/ath)9n0C(D6{VV1@[`)

**主程序执行流程:**

18. **选择机器人 (Block Type: `select_robot`, id: `D6U$]#o_;j,x(n|?ylyD`)**

    - 机器人名称: "fairino_FR"

19. **(紧随选择机器人之后) 设置电机状态 (Block Type: `set_motor`, id: `ngRpm(+*uK945Pg(1l:8`)**

    - 状态: "on"

20. **(紧随设置电机之后) 设置数值变量 (Block Type: `set_number`, id: `vmH6XO6E5lg^7Bq]N:w5`)**

    - 变量名: "N5"
    - 值: 2 (Block Type: `math_number`)

21. **(紧随设置数值变量之后) 开始循环 (Block Type: `loop`, id: `x+b^92,WZV.#^_Hn]!px`)**
    - 循环内操作:
      - **条件判断 (Block Type: `controls_if`, id: `0.0,I|n!aVww@7hPx5!Z`)**
        - IF 条件: 数值变量 "N5" (Block Type: `math_custom_number`) 等于 2 (Block Type: `logic_compare`, OP: EQ)
        - DO (如果条件为真):
          - 步骤 1: PTP 移动到点 "P1" (Block Type: `moveP`, id: `Fuw8mB)+GBA:-%*Tc=@u`)
          - 步骤 2: (此块被禁用) 等待外部 I/O 输入 (Block Type: `wait_external_io_input`, id: `Yp,)dd}S52oxNt[7czTI`)
            - I/O 编号: 1
            - 输入引脚名称: "0"
            - 等待状态: "on"
          - 步骤 3: 调用子程序 "BRG*Get_BRG" (Block Type: `procedures_callnoreturn`, id: `h6#*}XWK!/rEwKnvN)3C`)
          - 步骤 4: 等待复合条件 (Block Type: `wait_block`, id: `w1%y*-CPV:eRxf|m_~l]`)
            - 条件: (外部 I/O 引脚 "3" (I/O 编号 1) 等于 TRUE) AND (外部 I/O 引脚 "4" (I/O 编号 1) 等于 TRUE) (Block Types: `logic_operation`, `logic_compare`, `external_io`, `logic_boolean`)
          - 步骤 5: 调用子程序 "CNV_Get_BH" (Block Type: `procedures_callnoreturn`, id: `W5iKI\`Z!~lv)CUul^HV0`)
          - 步骤 6: PTP 移动到点 "P1" (Block Type: `moveP`, id: `eAXq[sd+6k]\`U@o/=F^@`)
          - 步骤 7: 等待机器人输入引脚 "12" 状态为 "on" (Block Type: `wait_input`, id: `ay[Kp/EH^giDQyF.nhln`)
          - 步骤 8: 调用子程序 "RMC_Put_BH&BRG" (Block Type: `procedures_callnoreturn`, id: `RS.peU(J$5=UG8bKCwMn`)
          - 步骤 9: 等待机器人输入引脚 "12" 状态为 "off" (Block Type: `wait_input`, id: `|kI+7+[!SH\`f_wZzZcr?`)
          - 步骤 10: 设置机器人输出引脚 "6" 为 "on" (Block Type: `set_output`, id: `|^!-WfyJ!b~4#?2~MB[C`)
          - 步骤 11: 等待复合条件 (Block Type: `wait_block`, id: `.[XX;\`607h3W2mPSY%M;`)
            - 条件: (机器人 I/O 引脚 "10" 等于 TRUE) OR (机器人 I/O 引脚 "11" 等于 TRUE) (Block Types: `logic_operation`, `logic_compare`, `robot_io`, `logic_boolean`)
          - 步骤 12: 调用子程序 "RMC_Get_BH" (Block Type: `procedures_callnoreturn`, id: `Fs(a-V5(yj7L_Xo80.!a`)
          - 步骤 13: PTP 移动到点 "P1" (Block Type: `moveP`, id: `_+VXDY,BROZ$u:l*N{%G`)
          - 步骤 14: 调用子程序 "LMC*Put_BH" (Block Type: `procedures_callnoreturn`, id: `5*+DBY4;9Jx-ONO$,5\*`)
          - 步骤 15: PTP 移动到点 "P1" (Block Type: `moveP`, id: `D(q6TC.4X*FmT]3%bkBT`)
          - 步骤 16: 调用子程序 "CNV_Get_PLT" (Block Type: `procedures_callnoreturn`, id: `:+g-p{|zjq2aOYt(Ux^U`)
          - 步骤 17: 调用子程序 "CNV_Put_PLT" (Block Type: `procedures_callnoreturn`, id: `cf[O/wIjWEV||/[44}j]`)
          - 步骤 18: PTP 移动到点 "P1" (Block Type: `moveP`, id: `Tqyo%0mQ\`Li/#l5CcZ+L`)
          - 步骤 19: 调用子程序 "LMC_Get_BH" (Block Type: `procedures_callnoreturn`, id: `u[n,erHG#MLa,vot9\`UQ`)
          - 步骤 20: PTP 移动到点 "P1" (Block Type: `moveP`, id: `aDTlHWh0R.D52-;;J2k)`)
          - 步骤 21: 调用子程序 "CNV*Put_BH" (Block Type: `procedures_callnoreturn`, id: `6y2!ac@!L.C;;*%n,c9,`)
          - 步骤 22: 在变量 "N483" 的持续时间内设置外部 I/O 输出 (Block Type: `set_external_io_output_during`, id: `F}V,]YOU7G7YzgXl$/Jx`)
            - I/O 编号: 1
            - 输出引脚名称: "3"
            - 输出状态: "on"
          - 步骤 23: 返回 (Block Type: `return`, id: `8]BU~D/D(-JF~dSmfhKy`)
