# Robot Process Generation - Stage 2: Detailed Steps for MainTask

## Objective

A MainTask represents the overall robotic process or a major, high-level phase of an operation. It orchestrates calls to various sub-tasks (like Grasp, Place, or other specialized sub-programs) to achieve a larger, composite goal. The Main Task defines the primary sequence, control flow (loops, conditionals), and initialization/shutdown procedures for the entire operation.

This prompt guides you to generate detailed process steps for a **MainTask**. The MainTask orchestrates various sub-tasks (sub-programs) and includes robot initialization, control flow logic, and coordination steps. Your goal is to convert the high-level description and sub-task list of a MainTask into a sequence of precise, executable steps, where **each step strictly corresponds to an available robot control block**.

## Input for this Task Type (Provided by the system)

You will receive:

1.  **Task Information**: A JSON-like structure containing the `name`, `type` ("MainTask"), `sub_tasks` (a list of sub-program names to be called), and `description` of the MainTask.
2.  **Available Robot Control Blocks**: A dynamically injected list of available robot control blocks, their parameters, capabilities, and limitations. **This is your primary reference for step generation.**

## General Generation Guidelines (MANDATORY)

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to the **Available Robot Control Blocks** (this list will be injected by the system below this section, before the "Example Fewshot" section).

- **Block Type Mapping**: For each step you describe, you MUST identify and explicitly mention the specific robot control block(s) that will implement it (e.g., "(Block Type: `moveP`)").
- **Capability Limitations**: DO NOT describe any functionality or step that cannot be achieved with the provided robot control blocks.
- **Parameterization**: When a block takes parameters (e.g., target point for `moveP`, I/O pin numbers, variable names and values), your description must clearly imply or explicitly state what these parameters would be. Use symbolic names for points (e.g., "P1", "P_Home") and variables (e.g., "N5") as appropriate.
- **Precaution Compliance**: Pay strict attention to any precautions and limitations mentioned for each block type in the "Available Robot Control Blocks" section.
- **Dependency Requirements**: Ensure proper sequence and dependencies. For example, a robot selection (e.g., `select_robot`) must precede movement commands, and motor activation (e.g., `set_motor`) must occur before motion.

### 1. MainTask Specific Instructions

**Core Responsibilities & Structure:**

- A MainTask orchestrates sub-tasks (e.g., GraspTask, PlaceTask, OpenClampTask, CloseClampTask, or other custom sub-programs) by calling them in a logically correct sequence.
- It defines the primary sequence and overall control flow for a larger operation.
- **Safety**: Consider overall safety by including movements to a "Home" or safe position at the start, end, and between major operational segments (using `moveP` or `moveL`).

- **Initialization (Essential & Mandatory)**:

  - **Must** begin with robot model selection (e.g., "Select **default robot (e.g., \"dobot_mg400\")** (Block Type: `select_robot`)").
  - **Must** include starting robot motors (e.g., "**Start motor (e.g., \"on\")** (Block Type: `set_motor`)").
  - Initialize any necessary process-critical numerical or string variables for process control (e.g., "Set **numerical variable for process control (e.g., \"N5\") to its initial judgment value (e.g., 2)** (Block Type: `set_number`)").

- **Sub-program Orchestration**:

  - The `sub_tasks` list from the input task definition dictates the sequence of sub-program calls.
  - Each call to a sub-program should be represented by a step using the `procedures_callnoreturn` block. Example: "Call sub-program "BRG_Get_BRG" (Get Bearing) (Block Type: `procedures_callnoreturn`)".
  - Ensure all orchestrated sub-tasks are called in a logically correct sequence.

- **Control Flow (Primary Logic)**:

  - Clearly define the primary control flow that governs the process execution.
  - Implement main loops using the `loop` block (e.g., "Start loop - Operations within loop: (Block Type: `loop`)").
  - Implement conditional logic (IF/ELSE) using `controls_if` (and `controls_if_else` if available and appropriate). Conditions often involve checking variable values or robot inputs (e.g., "Conditional judgment - IF condition: **Numerical variable (e.g., \"N5\") equals its initial set value (e.g., 2)** - DO (if condition is true): (Block Type: `controls_if`)").

- **Movement Commands**:

  - Include PTP (Point-to-Point) or Linear movements to safe, initial, or intermediate points between sub-task executions (e.g., "PTP move to **initial/safe point (e.g., \"P1\")** (Block Type: `moveP`)"). Typically use `moveP` or `moveL` blocks.

- **Waiting and Synchronization** (for interaction with external systems or robot signals):

  - Use `wait_input` to wait for specific robot DI signals (e.g., "Wait for robot **specified input pin to reach preset state (e.g., pin \"12\" is \"on\")** (Block Type: `wait_input`)").
  - Use `wait_external_io_input` to wait for signals from external devices if applicable (e.g., "Wait for external I/O input (...) (Block Type: `wait_external_io_input`)").
  - Use `wait_timer` for programmed delays (Block Type: `wait_timer`).
  - Use `wait_block` for compound conditions involving multiple robot I/Os (e.g., "Wait for compound condition - Condition: (...) (Block Type: `wait_block`)").

- **I/O Operations** (for interaction with external systems or robot end-effectors):

  - Set robot DO signals using `set_output` (e.g., "Set robot **specified output pin to preset state (e.g., pin \"6\" is \"on\")** (Block Type: `set_output`)").
  - Set external I/O signals using `set_external_io_output` or `set_external_io_output_during` if applicable (Block Types: `set_external_io_output`, `set_external_io_output_during`).

- **Disabled Blocks**: If the task description or common sense indicates a step might be optional or disabled by default, note this (e.g., "(This block is disabled)").

- **Return/End**: The main task might loop or end with a `return` block (Block Type: `return`) if it's structured as a main procedure or for loop control.

### 2. Output Format

Your output for this MainTask should be **ONLY a JSON array of strings**. Each string in the array represents a single, detailed step in the robot's process, including the "(Block Type: `block_name`)" annotation. Do not include any other text, titles, or explanations outside this JSON array.

---

## **(System will inject "Available Robot Control Blocks" here)**

## Example Fewshot: MainTask

### Input Task Definition (Example)

```json
{
  "name": "Main_Task",
  "type": "MainTask",
  "sub_tasks": [
    "BRG_Get_BRG",
    "Get_BH_InitialPos",
    "RMC_Put_BH&BRG",
    "RMC_Get_BH_Assembled",
    "LMC_Put_BH_Temp",
    "CNV_Get_PLT",
    "CNV_Put_PLT",
    "LMC_Get_BH_Stored",
    "CNV_Put_BH_On_PLT"
  ],
  "description": "Main process to assemble a bearing and housing, and place the final assembly on a pallet on a conveyor. This involves getting components, placing them in machining centers, retrieving assembled parts, and managing pallets on a conveyor."
}
```

### Your Expected Output (JSON Array of Detailed Steps)

```json
[
  "1. Select **default robot (e.g., "dobot_mg400")** (Block Type: `select_robot`)",
  "2. **Start motor (e.g., "on")** (Block Type: `set_motor`)",
  "3. Set **numerical variable for process control (e.g., "N5") to its initial judgment value (e.g., 2)** (Block Type: `set_number`)",
  "4. Start loop - Operations within loop: (Block Type: `loop`)",
  "5. Conditional judgment - IF condition: **Numerical variable (e.g., "N5") equals its initial set value (e.g., 2)** - DO (if condition is true): (Block Type: `controls_if`)",
  "6. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "7. Wait for external I/O input (**specify I/O number, specify pin, specify state (e.g., I/O number: 1, pin: "0", state: "on")**) (Block Type: `wait_external_io_input`) (This block is disabled)",
  "8. Call sub-program "BRG_Get_BRG" (Get Bearing) (Block Type: `procedures_callnoreturn`)",
  "9. Call sub-program "Get_BH_InitialPos" (Get Bearing Housing from Initial Position) (Block Type: `procedures_callnoreturn`)",
  "10. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "11. Wait for robot **specified input pin to reach preset state (e.g., pin "12" is "on")** (Block Type: `wait_input`)",
  "12. Call sub-program "RMC_Put_BH&BRG" (Place Bearing Housing and Bearing into Right Machining Center/Station) (Block Type: `procedures_callnoreturn`)",
  "13. Wait for robot **specified input pin to reach preset state (e.g., pin "12" is "off")** (Block Type: `wait_input`)",
  "14. Set robot **specified output pin to preset state (e.g., pin "6" is "on")** (Block Type: `set_output`)",
  "15. Wait for compound condition - Condition: (**Specified robot compound I/O condition (e.g., (Robot I/O pin "10" equals boolean value True) OR (Robot I/O pin "11" equals boolean value True))**) (Block Type: `wait_block`)",
  "16. Call sub-program "RMC_Get_BH_Assembled" (Get Assembled Part from Right Machining Center/Station) (Block Type: `procedures_callnoreturn`)",
  "17. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "18. Call sub-program "LMC_Put_BH_Temp" (Place Part into Left Machining Center for Temporary Storage) (Block Type: `procedures_callnoreturn`)",
  "19. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "20. Call sub-program "CNV_Get_PLT" (Get Pallet/Board from Conveyor) (Block Type: `procedures_callnoreturn`)",
  "21. Call sub-program "CNV_Put_PLT" (Place Pallet/Board onto Conveyor) (Block Type: `procedures_callnoreturn`)",
  "22. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "23. Call sub-program "LMC_Get_BH_Stored" (Get Stored Part from Left Machining Center/Station) (Block Type: `procedures_callnoreturn`)",
  "24. PTP move to **initial/safe point (e.g., "P1")** (Block Type: `moveP`)",
  "25. Call sub-program "CNV_Put_BH_On_PLT" (Place Part onto Pallet on Conveyor) (Block Type: `procedures_callnoreturn`)",
  "26. For the duration of **specified timer variable (e.g., "N483")** set external I/O output (**specify I/O number, specify pin, specify state** (e.g., I/O number: 1, pin: "3", state: "on")) (Block Type: `set_external_io_output_during`) (This block is disabled)",
  "27. Return (Block Type: `return`)"
]
```
