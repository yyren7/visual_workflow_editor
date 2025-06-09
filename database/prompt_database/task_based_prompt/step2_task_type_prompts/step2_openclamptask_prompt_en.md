# Robot Process Generation - Stage 2: Detailed Steps for OpenClampTask

## Objective

An OpenClampTask is a specific, often atomic, action to open a designated clamp, gripper, or other end-effector. This task is usually called as a sub-step within a Grasp Task (before approaching an object to prepare for grasping) or a Place Task (to release an object).

This prompt guides you to generate detailed process steps for an **OpenClampTask**. An OpenClampTask involves actuating a robot's end-effector (clamp/gripper) to its open state. This is often a sub-component of larger Grasp or Place tasks. Your goal is to convert the high-level description of an OpenClampTask into a sequence of precise, executable steps, where **each step strictly corresponds to an available robot control block**.

## Input for this Task Type (Provided by the system)

You will receive:

1.  **Task Information**: A JSON-like structure containing the `name`, `type` ("OpenClampTask"), `sub_tasks` (usually empty for this specific task type, as it's a primitive action), and `description` of the OpenClampTask.
2.  **Available Robot Control Blocks**: A dynamically injected list of available robot control blocks, their parameters, capabilities, and limitations. **This is your primary reference for step generation.**

## General Generation Guidelines (MANDATORY)

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to the **Available Robot Control Blocks** (this list will be injected by the system below this section, before the "Example Fewshot" section).

- **Block Type Mapping**: For each step you describe, you MUST identify and explicitly mention the specific robot control block(s) that will implement it (e.g., "(Block Type: `set_output`)").
- **Capability Limitations**: DO NOT describe any functionality or step that cannot be achieved with the provided robot control blocks.
- **Parameterization**: When a block takes parameters (e.g., output pin number and state for `set_output`, timer variable for `wait_timer`), your description must clearly imply or explicitly state what these parameters would be. Use specific pin numbers (e.g., "pin 2") and variable names (e.g., "N482") as appropriate.
- **Precaution Compliance**: Pay strict attention to any precautions and limitations mentioned for each block type in the "Available Robot Control Blocks" section.

### 1. OpenClampTask Specific Instructions

- **Sub-program Definition**: An OpenClampTask is typically defined as a sub-program. Start with a `procedures_defnoreturn` block (e.g., "Define sub-program \"Open_BRG_PLT_Clamp\" (Open clamp for operating bearings and pallets) (Block Type: `procedures_defnoreturn`)").

  - Ensure this task is called at the correct point in a larger sequence (e.g., before final approach in Grasp, at placement point in Place).

- **Operational Delay (Optional but often necessary)**: If a delay is required for the mechanical action of opening the clamp, use `wait_timer` with a specified timer variable (e.g., "Wait for specified timer variable (e.g., \"N482\", for operation delay) (Block Type: `wait_timer`)").

- **Actuation Command (Core Action)**: Use `set_output` to send the electrical signal to open the clamp.

  - This involves specifying the correct output pin and the state that corresponds to 'open' (e.g., "on" or "high").
  - Example: "Set robot clamp control output pin (e.g., pin \"2\") to open state (e.g., \"on\") (Block Type: `set_output`)".
  - If the robot has multiple effectors, ensure the correct clamp/effector is being addressed.

- **Feedback Confirmation (Recommended for reliability)**: Use `wait_input` to wait for a sensor signal confirming the clamp has reached its fully open state.

  - This involves specifying the correct input pin and the state that confirms 'open' (e.g., "on" or "high").
  - Example: "Wait for robot clamp status feedback input pin (e.g., pin \"2\") to be in open complete state (e.g., \"on\") (Block Type: `wait_input`)".

- **Return**: End the sub-program with a `return` block (e.g., "Return (Block Type: `return`)").

### 2. Output Format

Your output for this OpenClampTask should be **ONLY a JSON array of strings**. Each string in the array represents a single, detailed step in the robot's process, including the "(Block Type: `block_name`)" annotation. Do not include any other text, titles, or explanations outside this JSON array.

---

## **(System will inject "Available Robot Control Blocks" here)**

## Example Fewshot: OpenClampTask

### Input Task Definition (Example)

```json
{
  "name": "Open_BRG_PLT_Clamp",
  "type": "OpenClampTask",
  "sub_tasks": [],
  "description": "Open the clamp used for the bearing (BRG) and pallet (PLT)."
}
```

### Your Expected Output (JSON Array of Detailed Steps)

```json
[
  "1. Define sub-program "Open_BRG_PLT_Clamp" (Open clamp for operating bearings and pallets) (Block Type: `procedures_defnoreturn`)",
  "2. Wait for specified timer variable (e.g., "N482", for operation delay) (Block Type: `wait_timer`)",
  "3. Set robot clamp control output pin (e.g., pin "2") to open state (e.g., "on") (Block Type: `set_output`)",
  "4. Wait for robot clamp status feedback input pin (e.g., pin "2") to be in open complete state (e.g., "on") (Block Type: `wait_input`)",
  "5. Return (Block Type: `return`)"
]
```
