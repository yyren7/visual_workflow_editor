# Robot Process Generation - Stage 2: Detailed Steps for PlaceTask

## Objective

A PlaceTask defines a sequence of actions for placing an object, currently held by an end-effector, at a target destination. It involves approaching the destination, positioning the object, and then deactivating the end-effector to release the object.

This prompt guides you to generate detailed process steps for a **PlaceTask**. A PlaceTask involves the robot, typically holding an object, moving to a target location and releasing the object (e.g., using a clamp/gripper). Your goal is to convert the high-level description of a PlaceTask into a sequence of precise, executable steps, where **each step strictly corresponds to an available robot control block**.

## Input for this Task Type (Provided by the system)

You will receive:

1.  **Task Information**: A JSON-like structure containing the `name`, `type` ("PlaceTask"), `sub_tasks` (e.g., specific clamp operations like "Open_Clamp_X"), and `description` of the PlaceTask.
2.  **Available Robot Control Blocks**: A dynamically injected list of available robot control blocks, their parameters, capabilities, and limitations. **This is your primary reference for step generation.**

## General Generation Guidelines (MANDATORY)

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to the **Available Robot Control Blocks** (this list will be injected by the system below this section, before the "Example Fewshot" section).

- **Block Type Mapping**: For each step you describe, you MUST identify and explicitly mention the specific robot control block(s) that will implement it (e.g., "(Block Type: `moveP`)").
- **Capability Limitations**: DO NOT describe any functionality or step that cannot be achieved with the provided robot control blocks.
- **Parameterization**: When a block takes parameters (e.g., target point for `moveP`, speed value for `set_speed`), your description must clearly imply or explicitly state what these parameters would be. Use symbolic names for points (e.g., "P12", "P14_Place") and variables as appropriate.
- **Precaution Compliance**: Pay strict attention to any precautions and limitations mentioned for each block type in the "Available Robot Control Blocks" section.
- **Dependency Requirements**: Ensure proper sequence. For example, motors should be on before movement.

### 1. PlaceTask Specific Instructions

- **Sub-program Definition**: Typically, a PlaceTask is defined as a sub-program. Start with a `procedures_defnoreturn` block (e.g., "Define sub-program \"Place_BH_In_RMC\" (Place Bearing Housing in Right Machining Center) (Block Type: `procedures_defnoreturn`)").

- **Pre-Placement Considerations & Movement Sequence (Critical for Safety & Success)**:

  - Ensure the target location is clear and ready to receive the object.
  - Approach, placement, and retract paths must be clear of obstacles.
  - Move to a standby or initial approach point for the placement area. (e.g., "PTP move to **standby point for RMC placement operation (e.g., \"P20\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.
  - Move to an approach point above or near the target placement location. (e.g., "PTP move to **point above RMC bearing housing placement location (e.g., \"P12\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.

- **Final Placement & Release Action**:

  - **Speed Control for Precision**: Reduce robot speed (`set_speed`) for the final approach and placement movement to ensure accuracy and prevent damage. (e.g., "Set robot speed to **low speed (e.g., 20%)** for precise placement (Block Type: `set_speed`)").
  - **Precise Positioning**: Move the object to the precise placement point at the target location. This is critical before release. (e.g., "PTP move to **precise placement point of RMC bearing housing (e.g., \"P14\")** (Block Type: `moveP`)"). Use `moveP` or `moveL`.
  - **Release the Object (Mandatory)**: If an "Open Clamp" sub-task is listed in the input `sub_tasks` (e.g., `Open_BH_Asm_Clamp`), call it using `procedures_callnoreturn` to release the object. (e.g., "Call sub-program \"Open_BH_Asm_Clamp\" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)"). This step _must_ occur to release the object.
  - **Placement Confirmation (Optional but Recommended)**: Include any necessary `wait_timer` for the object to settle or for the clamp to fully open. Verify placement success or effector release if sensors are available (e.g., `wait_input`).

- **Movement Sequence (Post-Place)**:

  - **Lift/Retract**: Lift the end-effector to a clear point after releasing the object. (e.g., "PTP move to **lift point after RMC bearing housing placement (e.g., \"P12\")** (Block Type: `moveP`)").
  - **Restore Speed**: Restore normal robot speed using `set_speed` if it was previously reduced. (e.g., "Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)").
  - **Departure**: Move to a departure or retreat point. (e.g., "PTP move to **departure point after RMC placement operation (e.g., \"P11\")** (Block Type: `moveP`)").

- **Return**: End the sub-program with a `return` block if it was defined with `procedures_defnoreturn` (e.g., "Return (Block Type: `return`)").

### 2. Output Format

Your output for this PlaceTask should be **ONLY a JSON array of strings**. Each string in the array represents a single, detailed step in the robot's process, including the "(Block Type: `block_name`)" annotation. Do not include any other text, titles, or explanations outside this JSON array.

---

## **(System will inject "Available Robot Control Blocks" here)**

## Example Fewshot: PlaceTask

### Input Task Definition (Example)

```json
{
  "name": "Place_BH_In_RMC",
  "type": "PlaceTask",
  "sub_tasks": ["Open_BH_Asm_Clamp"],
  "description": "Place the bearing housing (BH) into the right machining center (RMC)."
}
```

### Your Expected Output (JSON Array of Detailed Steps)

```json
[
  "1. Define sub-program "Place_BH_In_RMC" (Place Bearing Housing in Right Machining Center) (Block Type: `procedures_defnoreturn`)",
  "2. PTP move to **standby point for RMC placement operation (e.g., "P20")** (Block Type: `moveP`)",
  "3. PTP move to **point above RMC bearing housing placement location (e.g., "P12")** (Block Type: `moveP`)",
  "4. Set robot speed to **low speed (e.g., 20%)** for precise placement (Block Type: `set_speed`)",
  "5. PTP move to **precise placement point of RMC bearing housing (e.g., "P14")** (Block Type: `moveP`)",
  "6. Call sub-program "Open_BH_Asm_Clamp" (Open Bearing Housing Clamp) (Block Type: `procedures_callnoreturn`)",
  "7. PTP move to **lift point after RMC bearing housing placement (e.g., "P12")** (Block Type: `moveP`)",
  "8. Restore robot speed to **normal speed (e.g., 100%)** (Block Type: `set_speed`)",
  "9. PTP move to **departure point after RMC placement operation (e.g., "P11")** (Block Type: `moveP`)",
  "10. Return (Block Type: `return`)"
]
```
