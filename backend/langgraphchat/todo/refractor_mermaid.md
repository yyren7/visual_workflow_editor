# mermaid

graph TD
A(start) --> B(user_input_node);
B --> C{agent_planner_node};

    C -- "Action Plan: Tool Calls AND NOT Feedback Needed" --> D[tool_executor_node];
    C -- "Feedback Needed" --> G[output_formatter_node];
    C -- "Task Complete (e.g., to generate final code)" --> F[code_generator_node];
    C -- "Task Complete (e.g., to show final sequence)" --> G;

    D -- "ReAct: Tool Executed, Agent Rethinks" --> C;
    D -- "Direct Tool Call: Update Sequence" --> E[sequence_updater_node];

    E -- "Continue Planning" --> C;
    E -- "Generate Code After Update" --> F;
    E -- "Show Updated Sequence to User" --> G;

    F --> G;

    G -- "Feedback Needed, Awaiting User Input" --> B;
    G -- "Task Segment Complete / End" --> H((END / Await New Input));

    subgraph "State Update & Tooling"
        D
        E
    end

    subgraph "User Interaction & Output"
        B
        G
    end

    subgraph "Core Logic & Generation"
        C
        F
    end

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#lightgrey,stroke:#333,stroke-width:2px
    style C fill:#lightblue,stroke:#333,stroke-width:4px,font-weight:bold
    style D fill:#orange,stroke:#333,stroke-width:2px
    style E fill:#yellow,stroke:#333,stroke-width:2px
    style F fill:#lightgreen,stroke:#333,stroke-width:2px
    style G fill:#lightgrey,stroke:#333,stroke-width:2px
    style H fill:#grey,stroke:#333,stroke-width:2px
