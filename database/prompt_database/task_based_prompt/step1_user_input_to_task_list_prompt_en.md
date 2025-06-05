# Robot Process Generation Prompt - Stage 1: User Input to Task List

## Objective

This Prompt aims to guide you in transforming a user's natural language robot task description (typically in Markdown format) into a structured **Task List**. This Task List will serve as an intermediate representation, outlining the main task and its constituent sub-tasks with their types, targets, and hierarchical relationships. This structured list will then be parsed and used as input for Stage 2, where detailed process steps are generated. The process should ideally support streaming generation of the task list, followed by a parsing step to ensure structural correctness.

## Input Materials

1.  **User Robot Task Description (.md or text)**: Contains natural language descriptions of the overall task the robot is expected to complete, sub-tasks, and objects of operation.
2.  **Task Type Descriptions (Provided Separately)**: Definitions and characteristics of different task types (e.g., Main Task, Grasp Task, Place Task, Open Clamp Task, Close Clamp Task).
3.  **Allowed Block Types (Provided Separately)**: A list and description of robot control blocks that can be ultimately used to implement the tasks. While not directly used for block mapping in this stage, awareness of these limitations helps in defining feasible tasks.

## Generation Guidelines and Requirements for Task List

Please follow these guidelines to generate a structured Task List:

### 1. Task Identification and Decomposition

    - Analyze the user's input to identify the primary goal (Main Task).
    - Break down the main task into a sequence of logical sub-tasks.
    - Identify operations related to effectors like clamps (Open Clamp, Close Clamp).

### 2. Task List Structure

    - The output should be a list of tasks.
    - Each task in the list should have the following attributes:
        - **`name`**: A concise and descriptive name for the task (e.g., `Get_Bearing_From_Rack`, `Open_Gripper_A`). Abbreviations used in the original prompt (e.g., BRG, PLT, CNV) should be preserved or logically inferred if beneficial for clarity and conciseness.
        - **`type`**: The category of the task. Must be one of the predefined task types (e.g., "MainTask", "GraspTask", "PlaceTask", "OpenClampTask", "CloseClampTask", "SubTask_Sequential", "SubTask_Parallel").
        - **`target`**: The primary object or location the task operates on or relates to (e.g., "Bearing", "Position_A", "Gripper_A").
        - **`sub_tasks`**: A list of names of other tasks that are nested within or executed as part of this task. For simple tasks, this can be empty.
        - **`description`**: (Optional) A brief natural language description of the task's purpose.

### 3. Generating the Task List

    - Process the user input sequentially.
    - As tasks are identified, generate their corresponding entries in the list.
    - Strive for a streaming-friendly generation process where task entries can be outputted as they are determined.
    - Ensure the order of tasks in the list reflects the intended execution sequence.

### 4. Parsing and Structuring

    - After the initial (potentially streamed) generation, the Task List should be parseable into a well-defined data structure (e.g., a list of objects/dictionaries).
    - This structured data will be the direct input for Stage 2.

### Example Task List Snippet (Conceptual)

```
[
  {
    "name": "Main_Assembly_Process",
    "type": "MainTask",
    "target": "Final_Product",
    "sub_tasks": ["Get_Bearing_BRG", "Get_Housing_BH", "Assemble_Parts_In_RMC", ...],
    "description": "Main process for assembling and handling parts."
  },
  {
    "name": "Get_Bearing_BRG",
    "type": "GraspTask",
    "target": "Bearing",
    "sub_tasks": ["Open_BRG_PLT_Clamp", "Move_To_Bearing_P23", "Close_BRG_PLT_Clamp", "Move_To_Safe_P21"],
    "description": "Retrieve a bearing from its initial position."
  },
  {
    "name": "Open_BRG_PLT_Clamp",
    "type": "OpenClampTask",
    "target": "BRG&PLT_Clamp",
    "sub_tasks": [],
    "description": "Open the clamp for bearings and pallets."
  },
  // ... more tasks
]
```

The primary goal of this stage is to create a clear, structured, and machine-readable inventory of tasks derived from the user's description, paving the way for detailed step generation in the next stage.
