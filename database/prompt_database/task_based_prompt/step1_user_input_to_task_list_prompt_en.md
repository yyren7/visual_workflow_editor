# Robot Process Generation Prompt - Stage 1: User Input to Task List

## Objective

This Prompt aims to guide you in transforming a user's natural language robot task description (typically in Markdown format) into a structured **Task List**. This Task List will serve as an intermediate representation, outlining the main task and its constituent sub-tasks with their types, targets, and hierarchical relationships. This structured list will then be parsed and used as input for Stage 2, where detailed process steps are generated. The process should ideally support streaming generation of the task list, followed by a parsing step to ensure structural correctness.

## Contextual Information for Task List Generation

You will be provided with the following information to help you generate the Task List from the User Robot Task Description:

### 1. Task Type Descriptions

This section contains definitions and characteristics of different task types you must use when classifying tasks.

{{TASK_TYPE_DESCRIPTIONS}}

### 2. Allowed Block Types (for context and feasibility assessment)

This section lists underlying robot control blocks and their descriptions. While you are not mapping directly to these blocks in this stage, awareness of their capabilities is crucial for defining feasible and implementable tasks. The tasks you define should ultimately be implementable using combinations of these blocks.

{{ALLOWED_BLOCK_TYPES}}

---

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
        - **`sub_tasks`**: A list of names of other tasks that are nested within or executed as part of this task. For simple tasks, this can be empty.
        - **`description`**: A brief natural language description of the task's purpose.

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
    "sub_tasks": ["Get_Bearing_BRG", "Get_Housing_BH", ...],
    "description": "Main process for assembling and handling parts."
  },
  {
    "name": "Get_Bearing_BRG",
    "type": "GraspTask",
    "sub_tasks": ["Open_BRG_PLT_Clamp", "Close_BRG_PLT_Clamp"],
    "description": "Retrieve a bearing from its initial position."
  },
  {
    "name": "Open_BRG_PLT_Clamp",
    "type": "OpenClampTask",
    "sub_tasks": [],
    "description": "Open the clamp for bearings and pallets."
  },
  // ... more tasks
]
```

The primary goal of this stage is to create a clear, structured, and machine-readable inventory of tasks derived from the user's description, paving the way for detailed step generation in the next stage.
