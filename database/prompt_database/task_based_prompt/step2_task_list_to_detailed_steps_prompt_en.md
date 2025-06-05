# Robot Process Generation Prompt - Stage 2: Task List to Detailed Process Steps

## Objective

This Prompt aims to guide you in generating a detailed process plan based on a structured **Task List** (output from Stage 1). This plan must include clear descriptions of a main process and multiple sub-processes (derived from the tasks in the Task List), along with textual explanations of their respective process steps and core logic. The critical goal is to ensure every described step **strictly corresponds to an available robot control block** and its capabilities.

## Input Materials

1.  **Structured Task List (JSON or similar format)**: Output from Stage 1. This list contains tasks with attributes like `name`, `type`, `target`, `sub_tasks`, and `description`.
2.  **Available Robot Control Blocks (Detailed Specification)**: A comprehensive list of available robot control blocks, including:
    - Block names (e.g., `moveP`, `set_motor`, `wait_input`, `procedures_callnoreturn`, `set_speed`).
    - Parameters for each block.
    - Capabilities and limitations of each block.
    - Precautions for using each block.
    - Dependency requirements (e.g., "select robot" before movement).

## Generation Guidelines and Requirements

Please follow these guidelines to generate a detailed process description from the Task List:

### 0. Robot Control Block Compliance (CRITICAL REQUIREMENT)

**MANDATORY BLOCK MAPPING**: Every step in your process description MUST strictly correspond to available robot control blocks.

- **Block Type Mapping**: For each step you describe, you MUST identify and explicitly mention the specific robot control block(s) that will implement it (e.g., "(Block Type: `moveP`)").
- **Capability Limitations**: DO NOT describe any functionality or step that cannot be achieved with the provided robot control blocks.
- **Parameterization**: When a block takes parameters (e.g., target point for `moveP`, speed value for `set_speed`), ensure the description implies or explicitly states what these parameters would be. Refer to point names (e.g., "P_Home", "P21") as used in the example.
- **Precaution Compliance**: Pay strict attention to the precautions and limitations mentioned for each block type.
- **Dependency Requirements**: Ensure proper sequence and dependencies. For example, a robot selection (e.g., `select_robot`) must precede movement commands, and motor activation (e.g., `set_motor`) must occur before motion.

**Example Step with Block Reference**:

- Description: "Robot moves to initial/safe point (e.g., 'P_Home')"
- Block Type: `moveP` or `moveL` (Choose the most appropriate based on context, or list options if genuinely ambiguous and permissible by block definitions)
- Precautions: Must define robot with "select robot" first, and turn ON servo power with "set motor" before using.

### 1. Translating Tasks to Sub-programs and Main Program

- **Task to Sub-program Mapping**: Each task from the input Task List (especially those of type "GraspTask", "PlaceTask", "OpenClampTask", "CloseClampTask", and other identified sub-task types) should generally be translated into a corresponding sub-program in the detailed process description.
  The `name` from the task list should be used for the sub-program name.
- **Main Task to Main Program Logic**: The task identified as "MainTask" will form the basis of the main program logic. Its `sub_tasks` array will define the sequence of sub-program calls in the main program.
- **Sub-program Naming**: Use the `name` attribute from the Task List for sub-program names. Maintain consistency with abbreviations (e.g., `BRG`, `PLT`, `CNV`, `RMC`, `LMC`, `BH`, `Clamp`).
- **Sub-program Function from Task Description**: The `description` and `target` from the task list entry should guide the detailed functional description of the sub-program.

### 2. Detailing Steps within Sub-programs

- **Core Logic Elaboration**: For each sub-program, elaborate its core logic into a sequence of precise steps. Each step must be implementable by one or more robot control blocks.
- **Movement Commands**: Detail movement sequences (e.g., approach, precise positioning, departure). Specify target points using symbolic names (e.g., "P_Home", "P21_Approach_BRG", "P22_Grasp_BRG"). It is assumed these points will be defined elsewhere but should be referenced logically here.
  - Example: "Move to bearing pick-up standby point (e.g., "P21") (Block Type: `moveP`)"
- **Clamp Operations**: Calls to clamp operations (Open/Close) should be mapped to `procedures_callnoreturn` if the clamp logic itself is defined as a separate sub-program (as per the Task List).
  - Example: "Call sub-program Open_BRG&PLT_Clamp (Block Type: `procedures_callnoreturn`)"
- **Speed Control**: Incorporate speed adjustments where necessary for precision or efficiency, explicitly mentioning the block.
  - Example: "Set speed to 10 for precise placement (Block Type: `set_speed`)"
- **Waiting/Synchronization**: Include steps for waiting for sensor inputs, external IOs, or timers, mapping them to appropriate blocks (`wait_input`, `wait_external_io_input`, `wait_timer`).

### 3. Main Program Construction

- **Initialization**: Describe main program initialization steps (robot selection, motor start, variable initialization), each mapped to a block.
  - Example: "Select robot model (e.g., "dobot_mg400"). (Block Type: `select_robot`)"
  - Example: "Start robot motors. (Block Type: `set_motor`)"
- **Control Flow**: Implement the main control flow (loops, conditionals) using corresponding blocks (`loop`, `controls_if`).
- **Sub-program Orchestration**: Detail how the main program calls the defined sub-programs in sequence, as indicated by the `sub_tasks` of the "MainTask" entry in the Task List.
  - Example: "Call sub-program `BRG_Get_BRG`. (Block Type: `procedures_callnoreturn`)"
- **State Transitions and Safety**: Incorporate movements to safe/transition points between major operations.
- **Error Handling (Optional)**: If the Task List implies error handling or alternative paths, describe these with corresponding block logic.

### 4. Modularization and Reuse (Reflecting Task List Structure)

- The modularization (e.g., clamp operations as separate sub-programs) should already be reflected in the input Task List structure. This stage is about faithfully implementing that structure with block-level details.
- If the Task List specified reusable tasks, ensure their corresponding sub-programs are called multiple times as needed, rather than redefining the logic.

## Output Format

The output should be a Markdown document, similar in structure to the original example, containing:

I. **Main Program Process Description**: Detailed steps with block type references.
II. **Sub-programs and Their Functional Descriptions**: For each sub-program:
_ Name (from Task List).
_ Function (derived from Task List description/target).
_ Clamps involved (if applicable, from Task List target or context).
_ Core Logic: A sequence of detailed steps, each with an explicit **(Block Type: `block_name`)** annotation.
III. **Modularization and Reuse Explanation**: Briefly explain how the generated plan reflects the modularity and reuse intended by the Task List (this might be less about new design and more about confirming the implementation of the Stage 1 design).

## Example Fewshot (Illustrative - Assumes Task List Input)

**(Assuming an input Task List that would lead to the following. The actual input Task List for this stage is not shown here but is implied)**

### Example Output (Detailed Process Description Plan - Based on Task List)

I. Main Program Process Description

    - Select robot model (e.g., "dobot_mg400"). (Block Type: `select_robot`)
    - Start robot motors. (Block Type: `set_motor`)
    - Initialize necessary process control variables (e.g., `start_condition = 2`). (Block Type: `set_number`)
    - Robot moves to **initial/safe point (e.g., "P_Home")**. (Block Type: `moveP`)
    - Main Loop start (Block Type: `loop`)
    - Check condition: `start_condition = 2`. (Block Type: `controls_if`)
    - Call sub-program `BRG_Get_BRG`. (Block Type: `procedures_callnoreturn`)
    - Call sub-program `Get_BH_InitialPos`. (Block Type: `procedures_callnoreturn`)
    - ... (rest of main program logic, calling other sub-programs as per MainTask from Task List)
    - Return to start of loop (Block Type: `return`)

II. Sub-programs and Their Functional Descriptions

1.  **`BRG_Get_BRG` (Derived from a Task List entry for getting a bearing)**:

    - Function: The robot retrieves a bearing from a specified initial position.
    - Clamp Involved: `BRG&PLT_Clamp`.
    - Core Logic:
      - Move to bearing pick-up standby point (e.g., "P21") (Block Type: `moveP`)
      - Move above bearing for pick-up (e.g., "P22") (Block Type: `moveP`)
      - Call sub-program `Open_BRG&PLT_Clamp` (Block Type: `procedures_callnoreturn`)
      - Descend to bearing precise grasping point (e.g., "P23") (Block Type: `moveP`)
      - Call sub-program `Close_BRG&PLT_Clamp` (Block Type: `procedures_callnoreturn`)
      - Ascend with bearing (e.g., "P25") (Block Type: `moveP`)
      - Move to bearing pick-up departure point (e.g., "P26") (Block Type: `moveP`)
      - Return to bearing pick-up standby point (e.g., "P21") (Block Type: `moveP`)

2.  **`Open_BRG&PLT_Clamp` (Derived from a Task List entry for opening this clamp)**:

    - Function: Controls the robot end-effector to open the clamp used for holding bearings or pallets.
    - Core Logic:
      - Wait for a predefined delay for clamp operation (e.g., timer "N482") (Block Type: `wait_timer`)
      - Send signal to open bearing/pallet clamp (e.g., set output pin 2 to on) (Block Type: `set_output`)
      - Wait for feedback confirming bearing/pallet clamp is open (e.g., wait for input pin 2 to be on) (Block Type: `wait_input`)

    (... and so on for all other sub-programs derived from the Task List ...)

III. Modularization and Reuse Explanation

- The generated process plan implements the modular structure defined in the input Task List. Clamp operations like `Open_BRG&PLT_Clamp` are defined as separate sub-programs and called by higher-level tasks such as `BRG_Get_BRG`, ensuring reuse and adherence to the task decomposition from Stage 1.
