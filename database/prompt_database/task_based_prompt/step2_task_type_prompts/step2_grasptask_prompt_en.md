# Robot Process Generation - Stage 2: Detailed Steps for GraspTask

## Objective

A GraspTask defines a sequence of actions specifically for picking up an object from a source location using an end-effector (e.g., gripper, multi-finger clamp, suction cup). It typically involves approaching the object, positioning the end-effector, activating it to secure the object, and then retracting.

This prompt guides you to generate detailed process steps for a **GraspTask**. A GraspTask involves the robot moving to a location, picking up an object using an end-effector (e.g., clamp/gripper), and then potentially moving to a departure point. Your goal is to convert the high-level description of a GraspTask into a sequence of precise, executable steps, where **each step strictly corresponds to an available robot control block**.

## Input for this Task Type (Provided by the system)

You will receive:

1.  **Task Information**: A JSON-like structure containing the `name`, `type` ("GraspTask"), `sub_tasks` (e.g., specific clamp operations like "Open_Clamp_X", "Close_Clamp_Y"), and `description` of the GraspTask.
2.  **Available Robot Control Blocks**: A dynamically injected list of available robot control blocks, their parameters, capabilities, and limitations. **This is your primary reference for step generation.**

## General Generation Guidelines (MANDATORY)

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to the **Available Robot Control Blocks** (this list will be injected by the system below this section, before the "Example Fewshot" section).

- **Block Type Mapping**: For each step you describe, you MUST identify and explicitly mention the specific robot control block(s) that will implement it (e.g., "(Block Type: `moveP`)").
- **Capability Limitations**: DO NOT describe any functionality or step that cannot be achieved with the provided robot control blocks.
- **Parameterization**: When a block takes parameters (e.g., target point for `moveP`, speed value for `set_speed`, I/O pin numbers), your description must clearly imply or explicitly state what these parameters would be. Use symbolic names for points (e.g., "P21", "P22_Approach") and variables as appropriate.
- **Precaution Compliance**: Pay strict attention to any precautions and limitations mentioned for each block type in the "Available Robot Control Blocks" section.
- **Dependency Requirements**: Ensure proper sequence. For example, motors should be on before movement.

### 1. GraspTask Specific Instructions

- **Sub-program Definition**: Typically, a GraspTask is defined as a sub-program. Start with a `procedures_defnoreturn` block (e.g., "**Define sub-program \"Get_PLT_From_Source\" (Grasp pallet from source)** (Block Type: `procedures_defnoreturn`)").

- **Movement Sequence & Path Planning (Critical for Safety & Success)**:

  - Paths (approach, grasp, retract) must be carefully planned to be clear of obstacles.
  - Move to a standby or initial approach point. This is often a safe point before committing to the grasp sequence. (e.g., "PTP move to **standby point for pallet source area (e.g., \"P51\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.
  - Move to an approach point closer to the object, ensuring clear passage. (e.g., "PTP move to **approach point above pallet source (e.g., \"P52\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.

- **Pre-Grasp End-Effector Setup (Mandatory)**:

  - **Crucially, the clamp/gripper must be opened BEFORE the final approach to the object.** If an "Open Clamp" sub-task is listed in the input `sub_tasks` (e.g., `Open_BRG_PLT_Clamp`), call it using `procedures_callnoreturn`. (e.g., "Call sub-program \"Open_BRG_PLT_Clamp\" (Open clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)"). Ensure the correct end-effector sub-program is called.

- **Final Approach & Grasping Action**:

  - **Speed Control for Precision**: Reduce robot speed (`set_speed`) for the final approach and grasp movement to ensure accuracy and prevent damage to the object or robot. (e.g., "Set robot speed to **low speed (e.g., 10%, for precise grasping)** (Block Type: `set_speed`)").
  - **Precise Positioning**: Move the end-effector to the precise grasping point relative to the object. This is critical. (e.g., "PTP **precisely move** to **pallet grasping point at source (e.g., \"P53\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.
  - **Secure the Object**: If a "Close Clamp" sub-task is listed in the input `sub_tasks` (e.g., `Close_BRG_PLT_Clamp`), call it using `procedures_callnoreturn` to secure the object. (e.g., "Call sub-program \"Close_BRG_PLT_Clamp\" (Close clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)"). Ensure the correct end-effector sub-program is called.
  - **Grasp Confirmation (Optional but Recommended)**: Include `wait_timer` for the clamp to fully actuate or `wait_input` if sensors are available to verify grasp success.

- **Post-Grasp Sequence**:

  - **Restore Speed**: Restore normal robot speed using `set_speed` if it was previously reduced. (e.g., "Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)").
  - **Lift/Retract**: Lift the object to a clear point to avoid collisions during departure. (e.g., "PTP move to **lift point after pallet grasping (e.g., \"P52\")** (Block Type: `moveP`)").
  - **Departure**: Move to a departure or retreat point. (e.g., "PTP move to **departure point after pallet grasping (e.g., \"P51\")** (Block Type: `moveP`)").

- **Return**: End the sub-program with a `return` block if it was defined with `procedures_defnoreturn` (e.g., "Return (Block Type: `return`)").

### 2. Output Format

Your output for this GraspTask should be **ONLY a JSON array of strings**. Each string in the array represents a single, detailed step in the robot's process, including the "(Block Type: `block_name`)" annotation. Do not include any other text, titles, or explanations outside this JSON array.

---

## **(System will inject "Available Robot Control Blocks" here)**

## Example Fewshot: GraspTask

### Input Task Definition (Example)

```json
{
  "name": "Get_PLT_From_Source",
  "type": "GraspTask",
  "sub_tasks": ["Open_BRG_PLT_Clamp", "Close_BRG_PLT_Clamp"],
  "description": "Grasp an empty pallet (PLT) from its source location."
}
```

### Your Expected Output (JSON Array of Detailed Steps)

```json
[
  "1. **Define sub-program "Get_PLT_From_Source" (Grasp pallet from source)** (Block Type: `procedures_defnoreturn`)",
  "2. PTP move to **standby point for pallet source area (e.g., "P51")** (Block Type: `moveP`)",
  "3. PTP move to **approach point above pallet source (e.g., "P52")** (Block Type: `moveP`)",
  "4. Call sub-program "Open_BRG_PLT_Clamp" (Open clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)",
  "5. Set robot speed to **low speed (e.g., 10%, for precise grasping)** (Block Type: `set_speed`)",
  "6. PTP **precisely move** to **pallet grasping point at source (e.g., "P53")** (Block Type: `moveP`)",
  "7. Call sub-program "Close_BRG_PLT_Clamp" (Close clamp for operating bearings and pallets/boards) (Block Type: `procedures_callnoreturn`)",
  "8. Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)",
  "9. PTP move to **lift point after pallet grasping (e.g., "P52")** (Block Type: `moveP`)",
  "10. PTP move to **departure point after pallet grasping (e.g., "P51")** (Block Type: `moveP`)",
  "11. Return (Block Type: `return`)"
]
```
