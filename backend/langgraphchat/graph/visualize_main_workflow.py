from IPython.display import Image, display
# Import the function to create the graph
from backend.langgraphchat.graph.workflow_graph import compile_workflow_graph
from langchain_core.language_models import BaseChatModel # For type hinting and dummy model
from langchain_core.outputs import ChatResult, ChatGeneration # For dummy model
import logging

# 获取日志记录器 - 这对于查看 compile_workflow_graph 内部的日志可能有用
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # 基本配置，以便看到日志

# Create a dummy LLM for graph instantiation
# This is often sufficient for visualization as the graph structure itself is what we want to see.
class DummyChatModel(BaseChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Dummy implementation
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="dummy_response"))]) # Ensure AIMessage for planner
    def _llm_type(self):
        return "dummy_chat_model"

# Instantiate the dummy LLM
dummy_llm = DummyChatModel()

# Create the graph instance using the imported function and dummy LLM
# Pass an empty list for custom_tools to avoid reliance on actual tool implementations for visualization
try:
    # Pass custom_tools=[] to ensure it doesn't try to load default flow_tools,
    # which might have other dependencies not needed for simple visualization.
    # The compile_workflow_graph function handles an empty tool list.
    graph = compile_workflow_graph(llm=dummy_llm, custom_tools=[])
    logger.info("Successfully created graph instance from workflow_graph.py")
except Exception as e:
    logger.error(f"Error creating graph instance from workflow_graph.py: {e}", exc_info=True)
    logger.info("Falling back to the example graph for demonstration.")
    # Example graph creation for demonstration if the main graph fails to load
    from langgraph.graph import StateGraph, END
    from typing import TypedDict, Annotated
    from langgraph.graph.message import add_messages
    from langchain_core.messages import AIMessage

    class ExampleState(TypedDict):
        messages: Annotated[list, add_messages]

    builder = StateGraph(ExampleState)

    def example_node1(state: ExampleState):
        logger.info("Executing example_node1")
        return {"messages": [AIMessage(content="Message from example_node1")]}

    def example_node2(state: ExampleState):
        logger.info("Executing example_node2")
        return {"messages": [AIMessage(content="Message from example_node2")]}

    builder.add_node("example_node_A", example_node1)
    builder.add_node("example_node_B", example_node2)
    builder.add_edge("example_node_A", "example_node_B")
    builder.add_edge("example_node_B", END)
    builder.set_entry_point("example_node_A")
    graph = builder.compile()
    logger.info("Using example graph for visualization.")


def visualize_langgraph(graph_to_visualize, output_filename="main_workflow_visualization.png"):
    """
    Visualizes a LangGraph graph and saves it as a PNG file.

    Args:
        graph_to_visualize: The LangGraph instance to visualize.
        output_filename (str): The name of the output PNG file.
    """
    if graph_to_visualize is None:
        logger.error("Graph to visualize is None. Cannot proceed.")
        return

    try:
        # Ensure the graph object has the get_graph method and it can draw
        if hasattr(graph_to_visualize, 'get_graph') and hasattr(graph_to_visualize.get_graph(), 'draw_mermaid_png'):
            image_bytes = graph_to_visualize.get_graph().draw_mermaid_png()
            with open(output_filename, "wb") as f:
                f.write(image_bytes)
            logger.info(f"Graph visualization saved to {output_filename}")
            
            # If in an IPython environment, display the image
            try:
                display(Image(image_bytes))
            except NameError:
                logger.info("IPython display not available. Image saved to file.")
        else:
            logger.error("The provided graph object cannot be visualized with draw_mermaid_png().")
            
    except Exception as e:
        logger.error(f"Error during visualization: {e}", exc_info=True)
        logger.info("Please ensure you have the necessary dependencies for Mermaid visualization installed.")
        logger.info("You might need to install playwright and pygraphviz:")
        logger.info("  pip install playwright pygraphviz")
        logger.info("  playwright install --with-deps")

if __name__ == "__main__":
    if 'graph' in locals() and graph is not None:
        visualize_langgraph(graph, "main_workflow_visualization.png")
    else:
        logger.error("Error: 'graph' instance was not successfully created or found.")
        logger.error("Ensure 'compile_workflow_graph' from 'workflow_graph.py' can be called or the example graph is used.") 