from IPython.display import Image, display
# Import the function to create the graph
from backend.langgraphchat.graph.nodes.robot_flow_planner.graph_builder import create_robot_flow_graph
from langchain_core.language_models import BaseChatModel # For type hinting and dummy model
from langchain_core.outputs import ChatResult, ChatGeneration # For dummy model

# Create a dummy LLM for graph instantiation if a real one isn't easily available
# This is often sufficient for visualization as the graph structure itself is what we want to see.
class DummyChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Dummy implementation
        return ChatResult(generations=[ChatGeneration(message="dummy_response")])
    def _llm_type(self):
        return "dummy_chat_model"

# Instantiate the dummy LLM
dummy_llm = DummyChatModel()

# Create the graph instance using the imported function and dummy LLM
# This assumes create_robot_flow_graph does not require a fully functional LLM for basic compilation for visualization
try:
    graph = create_robot_flow_graph(llm=dummy_llm)
    print("Successfully created graph instance from graph_builder.py")
except Exception as e:
    print(f"Error creating graph instance from graph_builder.py: {e}")
    print("Falling back to the example graph for demonstration.")
    # Пример создания простого графа для демонстрации, если основной граф не загрузился
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Annotated
    from langgraph.graph.message import add_messages

    class ExampleState(TypedDict):
        messages: Annotated[list, add_messages]

    builder = StateGraph(ExampleState)

    def node1(state: ExampleState):
        print("Executing example_node1")
        return {"messages": ["Message from example_node1"]}

    def node2(state: ExampleState):
        print("Executing example_node2")
        return {"messages": ["Message from example_node2"]}

    builder.add_node("example_node_A", node1)
    builder.add_node("example_node_B", node2)
    builder.add_edge("example_node_A", "example_node_B")
    builder.add_edge("example_node_B", END)
    builder.set_entry_point("example_node_A")
    graph = builder.compile()
    print("Using example graph.")
# Конец примера графа

def visualize_langgraph(graph_to_visualize, output_filename="langgraph_visualization.png"):
    """
    Visualizes a LangGraph graph and saves it as a PNG file.

    Args:
        graph_to_visualize: The LangGraph instance to visualize.
        output_filename (str): The name of the output PNG file.
    """
    if graph_to_visualize is None:
        print("Graph to visualize is None. Cannot proceed.")
        return

    try:
        # Attempt to get a more detailed graph view using xray=1
        # This might reveal subgraphs or more internal structure.
        image_bytes = graph_to_visualize.get_graph(xray=1).draw_mermaid_png()
        with open(output_filename, "wb") as f:
            f.write(image_bytes)
        print(f"Graph visualization saved to {output_filename}")
        
        # If in an IPython environment, display the image
        try:
            display(Image(image_bytes))
        except NameError:
            print("IPython display not available. Image saved to file.")
            
    except Exception as e:
        print(f"Error during visualization: {e}")
        print("Please ensure you have the necessary dependencies for Mermaid visualization installed.")
        print("You might need to install playwright and pygraphviz:")
        print("  pip install playwright pygraphviz")
        print("  playwright install --with-deps")

if __name__ == "__main__":
    if 'graph' in locals() or 'graph' in globals() and graph is not None:
        visualize_langgraph(graph, "robot_flow_planner_visualization.png")
    else:
        print("Error: 'graph' instance was not successfully created or found.")
        print("Ensure 'create_robot_flow_graph' from 'graph_builder.py' can be called or the example graph is used.") 