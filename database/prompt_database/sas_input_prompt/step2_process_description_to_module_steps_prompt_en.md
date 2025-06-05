# Robot Process Generation Prompt - Stage 2: Detailed Process Description to Module Steps

## Objective

- This Prompt aims to guide you in converting a **single main process** or a **single sub-process** description from the "Detailed Process Description Plan" (generated in the previous stage) into specific, executable robot program module steps (usually in XML format or a similar Blockly-exported structured format).
- The goal is to accurately map the provided **single** detailed textual process plan into a robot operation sequence containing specific instructions, points, parameters, and control logic.
- **Important Feature: This Prompt is designed for concurrent processing. Each time it is called, it will only generate module steps for the one main process description or one sub-process description provided as input.**

## Input Materials

1.  **Detailed Process Description Plan for a Single Main Process or Single Sub-Process (Text/Markdown)**: Contains a detailed textual description of the function, core logic steps, interaction points, etc., of that main program or sub-program.

## Generation Guidelines and Requirements

Please follow these guidelines to generate specific module steps based on the provided "Detailed Process Description Plan":

### 1. Convert Descriptive Steps into Specific Instructions

- **Action Instruction Mapping**: Accurately map operations like "move to", "grasp", "place", "open clamp", "close clamp", "wait for signal", etc., from the description to specific instructions in the robot's instruction set (e.g., `moveP`, `set_output`, `wait_input`, `procedures_callnoreturn`).
- **Point Definition and Usage**: Assign specific point codes (e.g., `P1`, `P21`, `P22`, `P23`) to key locations mentioned in the description (such as standby points, approach points, precise grasping/placing points, departure points, safe points), and use these points correctly in `moveP` and other instructions. Ensure consistency and logicality of points within sub-programs and the main program.
- **Parameter Setting**:
  - **Speed**: Use the `set_speed` instruction to adjust robot speed at appropriate times based on precision requirements mentioned in the description (e.g., "precise movement", "low speed") (e.g., reduce speed before precise operation, restore normal speed after completion).
  - **I/O Pins**: Specify specific I/O numbers and pin numbers for clamp control (`set_output`), sensor feedback (`wait_input`), and external device interaction (`wait_external_io_input`, `set_external_io_output_during`).
  - **Variables**: Assign clear names and initial values to variables used in process control (e.g., loop counters, variables in `controls_if` conditions) (`set_number`).
  - **Timers**: Specify timer variables and delay durations for operation delays (`wait_timer`).

### 2. Construct Main Program and Sub-program Structures

Please construct the corresponding structure based on whether the input is a main process description or a sub-process description:

- **If the input is a main process description, generate the main program structure**:
  - **Initialization Block**: Start with instructions like `select_robot`, `set_motor`, `set_number` (initialize variables).
  - **Control Flow Block**: Use `loop` to implement the main loop, and `controls_if` to implement conditional execution logic.
  - **Sub-program Calls**: Use `procedures_callnoreturn` to sequentially call the sub-programs planned in the detailed description plan.
  - **Transition and Safety Movements**: Insert `moveP` instructions to move to safe points or transition points between sub-program calls or after key steps.
  - **Synchronization and Interaction Block**: Based on the description, insert blocks like `wait_input`, `wait_external_io_input`, `wait_block`, `set_output`, `set_external_io_output_during`, and correctly configure their parameters (pins, states, conditions).
  - **End Block**: End the main program logic with a `return` block.
- **If the input is a sub-process description, generate the sub-program structure**:
  - **Definition Block**: The sub-program starts with `procedures_defnoreturn` and includes its name.
  - **Operation Sequence**: Internally contains a series of instructions like `moveP`, `procedures_callnoreturn` (calling other atomic sub-programs like clamp control), `set_speed`, `wait_timer`, etc., to implement the functions defined in the description plan.
  - **Parameterized Calls**: Ensure that calls to shared modules like clamps within the sub-program are correct.
  - **End Block**: The sub-program usually ends with `return` or simply completes execution.

### 3. Implement Modularization and Reuse

- **Atomic Operation Encapsulation**: Clamp opening/closing, etc., should be implemented as independent, parameterized sub-programs (e.g., `Open_BH_Crump`, `Close_BRG&PLT_Crump`) and called via `procedures_callnoreturn` in other sub-programs.
- **Standardized Movement Sequences**: For material grasping/placing, strictly follow the "approach point -> precise point -> execute action -> departure point -> safe point" pattern from the description and convert it into a specific `moveP` instruction sequence.

### 4. Special Case Handling

- **Disabled Blocks (`disabled="true"`)**: For "optional/disabled logic" mentioned in the description plan or steps that are temporarily not to be executed during debugging (especially external IO interactions), add the `disabled="true"` attribute to the corresponding generated block.
- **Error Handling**: If the description plan mentions error handling logic, it needs to be converted into corresponding conditional judgments and alternative path steps. (This is not detailed in this example, but needs to be considered in actual applications).

In summary, you need to accurately translate the provided **single** detailed textual process plan (whether it is a main process or a sub-process) into a structured list of steps that the robot can interpret and execute, ensuring that all actions, parameters, points, control flows, and module calls are correctly reflected.

## Example Fewshot

**Note: The following fewshot example, to comprehensively demonstrate the conversion process from a complex business description to complete modular steps, provides a complete task description including a main process and multiple sub-processes, along with all their corresponding module steps. In actual concurrent calls to this Prompt, the input will be the decomposed single main process description or single sub-process description, and the output will also be the module steps corresponding to that single process.**

### Example Task Input (Detailed Process Description Plan)

[
{
"section_title": "I. Main Program Process Description",
"content": "- Select robot model (e.g., \"dobot_mg400\").\n - Start robot motors.\n - Initialize necessary process control variables (e.g., `start_condition = 2`).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Main Loop start\n - Loop condition: `start_condition = 2` (or an infinite loop for continuous operation).\n - **(Optional/Disabled Logic)** Wait for external start signal (e.g., external IO input `Start_Signal_IN`).\n - Call sub-program `BRG_Get_BRG` (Get Bearing).\n - Call sub-program `Get_BH_InitialPos` (Get Bearing Housing from Initial Position).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Wait for signal that machining center (RMC) is ready (`RMC_Ready_IN`).\n - Call sub-program `RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into RMC).\n - Wait for RMC machining complete signal (`RMC_Done_IN`).\n - Send signal to notify RMC that part has been taken or is ready to be taken (`RMC_PartTaken_OUT`).\n - Wait for RMC confirmation signal (`RMC_Confirm_IN`).\n - Call sub-program `RMC_Get_BH_Assembled` (Get Assembled Part from RMC).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Call sub-program `LMC_Put_BH_Temp` (Place Part into LMC for Temporary Storage).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Call sub-program `CNV_Get_PLT` (Get Pallet from Conveyor).\n - Call sub-program `CNV_Put_PLT` (Place Pallet onto Conveyor).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Call sub-program `LMC_Get_BH_Stored` (Get Stored Part from LMC).\n - Robot moves to **initial/safe point (e.g., \"P_Home\")**.\n - Call sub-program `CNV_Put_BH_On_PLT` (Place Part onto Pallet on Conveyor).\n - **(Optional/Disabled Logic)** Send task complete signal to external system (`Task_Complete_OUT`).\n - Return to start of loop"
},
{
"section_title": "II. Sub-programs and Their Functional Descriptions",
"sub_sections": [
{
"item_number": "1",
"title": "**`BRG_Get_BRG` (Get Bearing)**:",
"content": "- Function: The robot retrieves a bearing from a specified initial position (e.g., material rack).\n - Core Logic: Move to bearing standby point -> Move above bearing -> Open bearing clamp -> Descend to bearing precise grasping point -> Close bearing clamp -> Ascend -> Move to departure point -> Return to safe/initial point.\n - Clamp Involved: `BRG&PLT_Crump` (clamp for operating bearings and pallets)."
},
{
"item_number": "2",
"title": "**`Get_BH_InitialPos` (Get Bearing Housing from Initial Position)**:",
"content": "- Function: The robot retrieves a bearing housing from a specified initial position.\n - Core Logic: Move to bearing housing standby point -> Move above bearing housing -> Open bearing housing clamp -> Descend to bearing housing precise grasping point -> Close bearing housing clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BH_Crump` (clamp for operating bearing housings)."
},
{
"item_number": "3",
"title": "**`RMC_Put_BH&BRG` (Place Bearing Housing and Bearing into Right Machining Center)**:",
"content": "- Function: The robot sequentially places the previously retrieved bearing housing and bearing into the designated station of the right machining center (RMC).\n - Core Logic:\n - Move to RMC standby point.\n - Place Bearing Housing: Move above RMC bearing housing placement point -> Precisely move to placement point -> Open bearing housing clamp -> Ascend.\n - Place Bearing: Move above RMC bearing placement point -> Precisely move to placement point -> Open bearing clamp -> Ascend.\n - Move to RMC departure point.\n - Clamps Involved: `BH_Crump`, `BRG&PLT_Crump`.\n - Note: Speed may need to be reduced during placement to ensure accuracy."
},
{
"item_number": "4",
"title": "**`RMC_Get_BH_Assembled` (Get Assembled Part from Right Machining Center)**:",
"content": "- Function: The robot retrieves the assembled (or processed) bearing housing from the right machining center (RMC) (at this point, it may already be assembled with the bearing).\n - Core Logic: Move to RMC standby point -> Move above assembled part -> Open bearing housing clamp (if previously open, this step is to prepare for grasping) -> Descend to precise grasping point -> Close bearing housing clamp -> Ascend -> Move to departure point.\n - Clamp Involved: `BH_Crump`."
},
{
"item_number": "5",
"title": "**`LMC_Put_BH_Temp` (Place Part into Left Machining Center for Temporary Storage)**:",
"content": "- Function: The robot places the part retrieved from RMC into the left machining center (LMC) for temporary storage or subsequent processing.\n - Core Logic: Move to LMC standby point -> Move above LMC placement point -> Precisely move to placement point -> Open bearing housing clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BH_Crump`."
},
{
"item_number": "6",
"title": "**`CNV_Get_PLT` (Get Pallet from Conveyor)**:",
"content": "- Function: The robot retrieves an empty pallet from a specified location (possibly another area of the conveyor).\n - Core Logic: Move to pallet standby point -> Move above pallet -> (Possibly low speed) Precisely move to grasping point -> Close pallet clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BRG&PLT_Crump`."
},
{
"item_number": "7",
"title": "**`CNV_Put_PLT` (Place Pallet onto Conveyor)**:",
"content": "- Function: The robot places the retrieved empty pallet onto the designated station of the conveyor.\n - Core Logic: Move above conveyor pallet placement point -> Precisely move to placement point -> Open pallet clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BRG&PLT_Crump`."
},
{
"item_number": "8",
"title": "**`LMC_Get_BH_Stored` (Get Stored Part from Left Machining Center)**:",
"content": "- Function: The robot retrieves the previously stored part from the left machining center (LMC).\n - Core Logic: Move to LMC standby point -> Move above part -> Precisely move to grasping point -> Close bearing housing clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BH_Crump`."
},
{
"item_number": "9",
"title": "**`CNV_Put_BH_On_PLT` (Place Part onto Pallet on Conveyor)**:",
"content": "- Function: The robot accurately places the part retrieved from LMC into the pre-placed pallet on the conveyor.\n - Core Logic: Move above conveyor pallet (with loaded part) -> Precisely move to designated placement point within pallet -> Open bearing housing clamp -> Ascend -> Return to safe/initial point.\n - Clamp Involved: `BH_Crump`."
},
{
"item_number": "10",
"title": "**`Open_BH_Crump` (Open Bearing Housing Clamp)**:",
"content": "- Function: Controls the robot end-effector to open the clamp used for holding the bearing housing.\n - Core Logic: Send open signal, wait for clamp in-position feedback."
},
{
"item_number": "11",
"title": "**`Close_BH_Crump` (Close Bearing Housing Clamp)**:",
"content": "- Function: Controls the robot end-effector to close the clamp used for holding the bearing housing.\n - Core Logic: Send close signal, wait for clamp in-position feedback."
},
{
"item_number": "12",
"title": "**`Open_BRG&PLT_Crump` (Open Bearing/Pallet Clamp)**:",
"content": "- Function: Controls the robot end-effector to open the clamp used for holding bearings or pallets.\n - Core Logic: Send open signal, wait for clamp in-position feedback."
},
{
"item_number": "13",
"title": "**`Close_BRG&PLT_Crump` (Close Bearing/Pallet Clamp)**:",
"content": "- Function: Controls the robot end-effector to close the clamp used for holding bearings or pallets.\n - Core Logic: Send close signal, wait for clamp in-position feedback."
}
]
},
{
"section_title": "III. Modularization and Reuse Explanation",
"content": "- **Clamp Operations**: `Open/Close_BH_Crump` and `Open/Close_BRG&PLT_Crump` are designed as independent, reusable sub-programs. They encapsulate the specific control logic for each clamp type and are called by various material handling sub-programs (`BRG_Get_BRG`, `Get_BH_InitialPos`, `RMC_Put_BH&BRG`, etc.). This promotes consistency and simplifies maintenance.\n- **Standard Movement Sequences**: Most pick and place sub-programs (`BRG_Get_BRG`, `Get_BH_InitialPos`, `CNV_Get_PLT`, etc.) follow a common \"approach target -> precise positioning -> execute action (grasp/release) -> depart target -> return to safe position\" movement pattern. This logic can be abstracted and reused, potentially through parameterized functions for different target locations.\n- **Speed Control**: For operations requiring high precision or delicate handling (e.g., `RMC_Put_BH&BRG`, `CNV_Get_PLT`), the core logic explicitly mentions the need for reduced speed during critical phases. This can be implemented via a parameter or a dedicated low-speed movement function.\n- **External Interaction and Synchronization**: The main process incorporates multiple points for synchronization with external devices (RMC, LMC, conveyor). This is achieved by waiting for specific input signals (`RMC_Ready_IN`, `RMC_Done_IN`) and sending output signals (`RMC_PartTaken_OUT`, `Task_Complete_OUT`). This modular approach ensures robust interaction with the surrounding environment.\n- **Optional Logic**: Features like waiting for an external start signal or sending a task complete signal are marked as optional. This allows for flexible deployment, where these features can be enabled or disabled based on the specific system integration requirements without altering the core process flow."
}
]

### Example Generation Thought Process (Brief)

When converting the above descriptive main process and sub-processes into module steps, the following mapping relationships are primarily followed:

- **Main program description initialization** -> `select_robot`, `set_motor`, `set_number` blocks.
- **Main program description loop/condition** -> `loop`, `controls_if` blocks.
- **"Call sub-program X" in main program and sub-program descriptions** -> `procedures_callnoreturn` block, its parameter being the sub-program name X.
- **"Function:..." and "Core Logic:..." in sub-program descriptions** -> `procedures_defnoreturn` block, its parameter being the sub-program name, internally containing the instruction sequence implementing the core logic.
- **"Move to Y point"** -> `moveP` block, parameter being point Y (e.g., "P1", "P21"). Points need to be fictionalized based on context logic or selected from an existing library.
- **Clamp operations like "Open/Close Z clamp"** -> Call the corresponding clamp control sub-program, e.g., `Open_BH_Crump`, which internally contains `set_output` (control clamp) and `wait_input` (wait for clamp sensor feedback).
- **"Wait for X signal"** -> `wait_input` (robot internal signal) or `wait_external_io_input` (external device IO signal) or `wait_block` (compound condition).
- **"Set robot speed to low/normal speed"** -> `set_speed` block, parameter being speed percentage.
- **"Optional/Disabled logic"** -> Add `disabled="true"` to the corresponding block.
- **"Process end/return"** -> `return` block.

### Example Output (Robot Operation Detailed Process Steps Instance)

## Main Program Steps Refinement

1. Select **default robot (e.g., "dobot_mg400")** (Block Type: `select_robot`)
2. **Start motor (e.g., "on")** (Block Type: `set_motor`)
3. Set **numerical variable for process control (e.g., "N5") to its initial judgment value (e.g., 2)** (Block Type: `set_number`)
4. Start loop - Operations within loop: (Block Type: `loop`)
5. Conditional judgment - IF condition: **Numerical variable (e.g., "N5") equals its initial set value (e.g., 2)** - DO (if condition is true): (Block Type: `controls_if`)
6. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
7. Wait for external I/O input (**specify I/O number, specify pin, specify state (e.g., I/O number: 1, pin: "0", state: "on")**) (Block Type: `wait_external_io_input`) (This block is disabled)
8. Call sub-program "BRG_Get_BRG" (Get Bearing) (Block Type: `procedures_callnoreturn`)
9. Wait for compound condition - Condition: (**Specified compound external I/O condition (e.g., (External I/O (I/O number 1) pin "3" equals boolean value True) AND (External I/O (I/O number 1) pin "4" equals boolean value True))**) (Block Type: `wait_block`) (This block is disabled)
10. Call sub-program "CNV_Get_BH" (Get Bearing Housing from Conveyor) (Block Type: `procedures_callnoreturn`)
11. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
12. Wait for robot **specified input pin to reach preset state (e.g., pin "12" is "on")** (Block Type: `wait_input`)
13. Call sub-program "RMC_Put_BH&BRG" (Place Bearing Housing and Bearing into Right Machining Center/Station) (Block Type: `procedures_callnoreturn`)
14. Wait for robot **specified input pin to reach preset state (e.g., pin "12" is "off")** (Block Type: `wait_input`)
15. Set robot **specified output pin to preset state (e.g., pin "6" is "on")** (Block Type: `set_output`)
16. Wait for compound condition - Condition: (**Specified robot compound I/O condition (e.g., (Robot I/O pin "10" equals boolean value True) OR (Robot I/O pin "11" equals boolean value True))**) (Block Type: `wait_block`)
17. Call sub-program "RMC_Get_BH" (Get Bearing Housing from Right Machining Center/Station) (Block Type: `procedures_callnoreturn`)
18. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
19. Call sub-program "LMC_Put_BH" (Place Bearing Housing into Left Machining Center/Station) (Block Type: `procedures_callnoreturn`)
20. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
21. Call sub-program "CNV_Get_PLT" (Get Pallet/Board from Conveyor) (Block Type: `procedures_callnoreturn`)
22. Call sub-program "CNV_Put_PLT" (Place Pallet/Board onto Conveyor) (Block Type: `procedures_callnoreturn`)
23. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
24. Call sub-program "LMC_Get_BH" (Get Bearing Housing from Left Machining Center/Station) (Block Type: `procedures_callnoreturn`)
25. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
26. Call sub-program "CNV_Put_BH" (Place Bearing Housing onto Conveyor) (Block Type: `procedures_callnoreturn`)
27. For the duration of **specified timer variable (e.g., "N483")** set external I/O output (**specify I/O number, specify pin, specify state** (e.g., I/O number: 1, pin: "3", state: "on")) (Block Type: `set_external_io_output_during`) (This block is disabled)
28. Return (Block Type: `return`)

## Sub-program Steps Refinement

1.1. **Define sub-program "BRG_Get_BRG" (Get Bearing)** (Block Type: `procedures_defnoreturn`)
1.2. PTP move to **standby point for bearing grasping area (e.g., "P21")** (Block Type: `moveP`)
1.3. PTP move to **approach point above bearing (e.g., "P22")** (Block Type: `moveP`)
1.4. Call sub-program "Open_BRG&PLT_Crump" (Open clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)
1.5. PTP move to **precise grasping point of bearing (e.g., "P23")** (Block Type: `moveP`)
1.6. Call sub-program "Close_BRG&PLT_Crump" (Close clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)
1.7. PTP move to **lift point after bearing grasping (e.g., "P25")** (Block Type: `moveP`)
1.8. PTP move to **departure point after bearing grasping (e.g., "P26")** (Block Type: `moveP`)
1.9. PTP move to **end/return point of bearing grasping process (e.g., "P21")** (Block Type: `moveP`)

2.1. **Define sub-program "Open_BH_Crump" (Open Bearing Housing Clamp)** (Block Type: `procedures_defnoreturn`)
2.2. Wait for **specified timer variable (e.g., "N483", for operation delay)** (Block Type: `wait_timer`)
2.3. Set robot **clamp control output pin (e.g., pin "1") to open state (e.g., "on")** (Block Type: `set_output`)
2.4. Wait for robot **clamp status feedback input pin (e.g., pin "0") to be in open complete state (e.g., "on")** (Block Type: `wait_input`)

3.1. **Define sub-program "CNV_Get_BH" (Get Bearing Housing from Conveyor)** (Block Type: `procedures_defnoreturn`)
3.2. PTP move to **standby point for bearing housing grasping near conveyor (e.g., "P31")** (Block Type: `moveP`)
3.3. PTP move to **approach point above bearing housing on conveyor (e.g., "P32")** (Block Type: `moveP`)
3.4. Call sub-program "Open_BH_Crump" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
3.5. PTP move to **precise grasping point of bearing housing on conveyor (e.g., "P33")** (Block Type: `moveP`)
3.6. Call sub-program "Close_BH_Crump" (Close Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
3.7. PTP move to **lift point after conveyor bearing housing grasping (e.g., "P32")** (Block Type: `moveP`)
3.8. PTP move to **end/return point of conveyor bearing housing grasping process (e.g., "P31")** (Block Type: `moveP`)

4.1. **Define sub-program "Close_BH_Crump" (Close Bearing Housing Clamp)** (Block Type: `procedures_defnoreturn`)
4.2. Wait for **specified timer variable (e.g., "N482", for operation delay)** (Block Type: `wait_timer`)
4.3. Set robot **clamp control output pin (e.g., pin "1") to close state (e.g., "off")** (Block Type: `set_output`)
4.4. Wait for robot **clamp status feedback input pin (e.g., pin "1") to be in close complete state (e.g., "on")** (Block Type: `wait_input`)

5.1. **Define sub-program "Open_BRG&PLT_Crump" (Open clamp for operating bearings and pallets/boards)** (Block Type: `procedures_defnoreturn`)
5.2. Wait for **specified timer variable (e.g., "N482", for operation delay)** (Block Type: `wait_timer`)
5.3. Set robot **clamp control output pin (e.g., pin "2") to open state (e.g., "on")** (Block Type: `set_output`)
5.4. Wait for robot **clamp status feedback input pin (e.g., pin "2") to be in open complete state (e.g., "on")** (Block Type: `wait_input`)

6.1. **Define sub-program "RMC_Put_BH&BRG" (Place Bearing Housing and Bearing into Right Machining Center/Station)** (Block Type: `procedures_defnoreturn`)
6.2. PTP move to **standby point for RMC (Right Machining Center) placement operation (e.g., "P20")** (Block Type: `moveP`)
6.3. PTP move to **approach point near RMC station (e.g., "P11")** (Block Type: `moveP`)
6.4. PTP move to **point above RMC bearing housing placement location (e.g., "P12")** (Block Type: `moveP`)
6.5. PTP move to **precise placement point of RMC bearing housing (e.g., "P14")** (Block Type: `moveP`)
6.6. PTP move to **posture adjustment/lift point after RMC bearing housing placement (e.g., "P15")** (Block Type: `moveP`)
6.7. Call sub-program "Open_BH_Crump" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
6.8. Set robot speed to **low speed (e.g., 10%, for precise placement)** (Block Type: `set_speed`)
6.9. PTP **precisely move** to **RMC bearing housing placement point (e.g., "P14")** (Block Type: `moveP`)
6.10. Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)
6.11. PTP move to **point above RMC bearing placement location (e.g., "P13")** (Block Type: `moveP`)
6.12. PTP move to **precise placement point of RMC bearing (e.g., "P16")** (Block Type: `moveP`)
6.13. PTP move to **posture adjustment/lift point after RMC bearing placement (e.g., "P17")** (Block Type: `moveP`)
6.14. Call sub-program "Open_BRG&PLT_Crump" (Open clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)
6.15. Set robot speed to **low speed (e.g., 10%, for precise placement)** (Block Type: `set_speed`)
6.16. PTP **precisely move** to **RMC bearing placement point (e.g., "P16")** (Block Type: `moveP`)
6.17. Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)
6.18. PTP move to **lift point after RMC placement operation completion (e.g., "P12")** (Block Type: `moveP`)
6.19. PTP move to **departure point after RMC placement operation completion (e.g., "P11")** (Block Type: `moveP`)

7.1. **Define sub-program "Close_BRG&PLT_Crump" (Close clamp for operating bearings and pallets/boards)** (Block Type: `procedures_defnoreturn`)
7.2. Wait for **specified timer variable (e.g., "N482", for operation delay)** (Block Type: `wait_timer`)
7.3. Set robot **clamp control output pin (e.g., pin "2") to close state (e.g., "off")** (Block Type: `set_output`)
7.4. Wait for robot **clamp status feedback input pin (e.g., pin "3") to be in close complete state (e.g., "on")** (Block Type: `wait_input`)

8.1. **Define sub-program "RMC_Get_BH" (Get Bearing Housing from Right Machining Center/Station)** (Block Type: `procedures_defnoreturn`)
8.2. PTP move to **approach point near RMC station (e.g., "P11")** (Block Type: `moveP`)
8.3. PTP move to **point above RMC assembled part grasping location (e.g., "P12")** (Block Type: `moveP`)
8.4. PTP move to **precise grasping point of RMC assembled part (e.g., "P14")** (Block Type: `moveP`)
8.5. PTP move to **posture adjustment point after RMC assembled part grasping (e.g., "P15")** (Block Type: `moveP`)
8.6. Call sub-program "Close_BH_Crump" (Close Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
8.7. PTP move to **lift point after RMC assembled part grasping (e.g., return to "P14" then lift, or directly to "P12")** (Block Type: `moveP`)
8.8. PTP move to **raised point after RMC grasping operation completion (e.g., "P12")** (Block Type: `moveP`)
8.9. PTP move to **departure point after RMC grasping operation completion (e.g., "P11")** (Block Type: `moveP`)
8.10. PTP move to **end/return point of RMC grasping process (e.g., "P20")** (Block Type: `moveP`)

9.1. **Define sub-program "LMC_Put_BH" (Place Bearing Housing into Left Machining Center/Station)** (Block Type: `procedures_defnoreturn`)
9.2. PTP move to **standby point for LMC (Left Machining Center) placement operation (e.g., "P41")** (Block Type: `moveP`)
9.3. PTP move to **approach point above LMC station (e.g., "P42")** (Block Type: `moveP`)
9.4. PTP move to **precise placement point of LMC (e.g., "P43")** (Block Type: `moveP`)
9.5. Call sub-program "Open_BH_Crump" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
9.6. PTP move to **lift point after LMC placement (e.g., "P42")** (Block Type: `moveP`)
9.7. PTP move to **departure point after LMC placement (e.g., "P41")** (Block Type: `moveP`)
9.8. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)

10.1. **Define sub-program "CNV_Get_PLT" (Get Pallet/Board from Conveyor)** (Block Type: `procedures_defnoreturn`)
10.2. PTP move to **standby point for pallet grasping near conveyor (e.g., "P34")** (Block Type: `moveP`)
10.3. PTP move to **approach point above pallet on conveyor (e.g., "P35")** (Block Type: `moveP`)
10.4. Set robot speed to **low speed (e.g., 10%, for precise grasping)** (Block Type: `set_speed`)
10.5. PTP **precisely move** to **pallet grasping point on conveyor (e.g., "P36")** (Block Type: `moveP`)
10.6. Call sub-program "Close_BRG&PLT_Crump" (Close clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)
10.7. PTP move to **lift point after conveyor pallet grasping (e.g., "P35")** (Block Type: `moveP`)
10.8. Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)
10.9. PTP move to **end/return point of conveyor pallet grasping process (e.g., "P34")** (Block Type: `moveP`)

11.1. **Define sub-program "CNV_Put_PLT" (Place Pallet/Board onto Conveyor)** (Block Type: `procedures_defnoreturn`)
11.2. PTP move to **point above conveyor pallet placement location (e.g., "P37")** (Block Type: `moveP`)
11.3. PTP move to **precise placement point of conveyor pallet (e.g., "P38")** (Block Type: `moveP`)
11.4. Call sub-program "Open_BRG&PLT_Crump" (Open clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)
11.5. PTP move to **lift point after conveyor pallet placement (e.g., "P37")** (Block Type: `moveP`)
11.6. PTP move to **end/return point of conveyor pallet placement process (e.g., "P34")** (Block Type: `moveP`)

12.1. **Define sub-program "LMC_Get_BH" (Get Bearing Housing from Left Machining Center/Station)** (Block Type: `procedures_defnoreturn`)
12.2. PTP move to **standby point for LMC grasping operation (e.g., "P41")** (Block Type: `moveP`)
12.3. PTP move to **approach point above LMC station (e.g., "P42")** (Block Type: `moveP`)
12.4. PTP move to **precise grasping point of LMC (e.g., "P43")** (Block Type: `moveP`)
12.5. Call sub-program "Close_BH_Crump" (Close Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
12.6. PTP move to **lift point after LMC grasping (e.g., "P42")** (Block Type: `moveP`)
12.7. PTP move to **departure point after LMC grasping (e.g., "P41")** (Block Type: `moveP`)

13.1. **Define sub-program "CNV_Put_BH" (Place Bearing Housing onto Conveyor)** (Block Type: `procedures_defnoreturn`)
13.2. PTP move to **point above assembled part placement location on conveyor (e.g., "P39")** (Block Type: `moveP`)
13.3. PTP move to **precise placement point of assembled part on conveyor (e.g., "P40", meaning onto the pallet)** (Block Type: `moveP`)
13.4. Call sub-program "Open_BH_Crump" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)
13.5. PTP move to **lift point after assembled part placement on conveyor (e.g., "P39")** (Block Type: `moveP`)
13.6. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)
13.7. Return (Block Type: `return`)
