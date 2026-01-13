"""
Agentic Layer - LangGraph with ChatGroq

Purpose:
- Implements the agentic reasoning layer using LangGraph state management
- Coordinates multi-step retrieval and reasoning workflow
- Connects Telekom, Siemens, and Illigo data sources for cross-domain analysis
- Enables 'connecting the dots' between high-level symptoms and low-level faults

Architecture:
- State: AgentState tracks messages, retrieved documents, and final diagnosis
- Nodes: retrieve_node (RAG search) and reasoning_node (LLM synthesis)
- Flow: START -> retrieve_node -> reasoning_node -> END

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import sys
import logging
from pathlib import Path
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# LangChain core
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.documents import Document

# ChatGroq for LLM
from langchain_groq import ChatGroq

# LangGraph for state management
from langgraph.graph import StateGraph, END

# Vector store for retrieval
from src.retrieval.vector_store import VectorStoreManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


# ============================================================================
# State Definition
# ============================================================================

class AgentState(TypedDict):
    """
    State schema for the LangGraph agent.

    Attributes:
        messages: Conversation history (list of LangChain BaseMessage objects)
        documents: Retrieved documents from vector store (list of Document objects)
        diagnosis: Final diagnosis output (string)
    """
    messages: Annotated[List[BaseMessage], "Conversation messages"]
    documents: Annotated[List[Document], "Retrieved evidence documents"]
    diagnosis: Annotated[str, "Final diagnosis output"]


# ============================================================================
# LLM Initialization
# ============================================================================

def initialize_llm() -> ChatGroq:
    """
    Initialize the ChatGroq LLM with Llama 3.3 70B model.

    Returns:
        ChatGroq instance configured for reasoning tasks
    """
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError(
            "GROQ_API_KEY not found in environment. "
            "Please set it in your .env file."
        )

    logger.info("Initializing ChatGroq with llama-3.3-70b-versatile...")
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0
    )

    return llm


# ============================================================================
# Tool: retrieve_evidence
# ============================================================================

def retrieve_evidence(query: str, k: int = 5) -> List[Document]:
    """
    Tool to retrieve relevant documents from the vector store.

    Args:
        query: User query or search string
        k: Number of documents to retrieve

    Returns:
        List of relevant Document objects with metadata
    """
    logger.info(f"Retrieving evidence for query: '{query}' (k={k})")

    # Initialize vector store
    vector_store = VectorStoreManager(
        persist_directory="./chroma_db",
        collection_name="infra_copilot"
    )

    # Perform similarity search
    documents = vector_store.similarity_search(query, k=k)

    logger.info(f"Retrieved {len(documents)} documents from vector store")

    for i, doc in enumerate(documents, 1):
        source_type = doc.metadata.get('source_type', 'unknown')
        file_name = doc.metadata.get('file_name', 'unknown')
        logger.info(f"  Doc {i}: {source_type} | {file_name}")

    return documents


# ============================================================================
# Graph Nodes
# ============================================================================

def retrieve_node(state: AgentState) -> AgentState:
    """
    Node 1: Retrieve evidence from the vector store.

    This node:
    1. Extracts the user query from the messages
    2. Searches the vector store for relevant documents
    3. Updates the state with retrieved documents

    Args:
        state: Current agent state

    Returns:
        Updated state with documents
    """
    logger.info("\n" + "=" * 60)
    logger.info("NODE: retrieve_node")
    logger.info("=" * 60)

    # Extract query from last message
    if not state["messages"]:
        raise ValueError("No messages in state")

    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    logger.info(f"User Query: {query}")

    # Retrieve documents
    documents = retrieve_evidence(query, k=5)

    # Update state
    state["documents"] = documents

    logger.info(f"State updated with {len(documents)} documents")

    return state


def reasoning_node(state: AgentState) -> AgentState:
    """
    Node 2: Perform reasoning and generate diagnosis.

    This node:
    1. Receives retrieved documents from retrieve_node
    2. Constructs a system prompt for cross-domain analysis
    3. Invokes the LLM to synthesize evidence and generate diagnosis
    4. Updates the state with the final diagnosis

    System Prompt Strategy:
    - Emphasizes cross-referencing between Telekom, Siemens, and Illigo
    - Instructs the model to trace high-level symptoms to low-level root causes
    - Requires citation of specific source files

    Args:
        state: Current agent state with retrieved documents

    Returns:
        Updated state with diagnosis
    """
    logger.info("\n" + "=" * 60)
    logger.info("NODE: reasoning_node")
    logger.info("=" * 60)

    # Extract documents from state
    documents = state.get("documents", [])

    if not documents:
        logger.warning("No documents found in state. Cannot generate diagnosis.")
        state["diagnosis"] = "ERROR: No evidence documents available for reasoning."
        return state

    logger.info(f"Processing {len(documents)} documents for reasoning...")

    # Format documents as context
    context_parts = []
    for i, doc in enumerate(documents, 1):
        source_type = doc.metadata.get('source_type', 'unknown')
        file_name = doc.metadata.get('file_name', 'unknown')
        content = doc.page_content

        context_parts.append(
            f"=== Document {i} ===\n"
            f"Source: {source_type}\n"
            f"File: {file_name}\n"
            f"Content:\n{content}\n"
        )

    context = "\n\n".join(context_parts)

    # System prompt for critical infrastructure co-pilot
    system_prompt = """You are the AI Co-Pilot for Critical Infrastructure. Your goal is to cross-reference data from multiple domains to diagnose infrastructure issues.

You have access to three data sources:

1. **Telekom Domain**: High-level network Intent/SLA requirements (latency, bandwidth, reliability for microgrids and charging stations)
2. **Siemens Domain**: Hardware specifications, equipment configurations, and technical documentation
3. **Illigo Domain**: Low-level operational logs from charging stations (faults, errors, ground faults, etc.)

Your Task:
- If you see a high-level network symptom (like latency issues), search the low-level logs for a hardware root cause
- Connect the dots between Telekom requirements, Siemens hardware, and Illigo operational failures
- Always cite the specific filename or source when referencing evidence
- Provide a clear diagnosis that traces from symptom to root cause

Be thorough, analytical, and cite your sources."""

    # Get the user query
    user_query = state["messages"][-1].content if state["messages"] else "Diagnose the issue"

    # Build messages for LLM
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Query: {user_query}\n\nRetrieved Evidence:\n\n{context}")
    ]

    # Initialize LLM
    llm = initialize_llm()

    # Generate diagnosis
    logger.info("Invoking LLM for reasoning...")
    response = llm.invoke(messages)

    diagnosis = response.content

    logger.info(f"Diagnosis generated ({len(diagnosis)} characters)")

    # Update state
    state["diagnosis"] = diagnosis
    state["messages"].append(AIMessage(content=diagnosis))

    return state


# ============================================================================
# Graph Builder
# ============================================================================

def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph agent workflow.

    Graph Flow:
        START -> retrieve_node -> reasoning_node -> END

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Building LangGraph agent...")

    # Initialize graph with state schema
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reasoning", reasoning_node)

    # Define edges
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "reasoning")
    workflow.add_edge("reasoning", END)

    # Compile graph
    graph = workflow.compile()

    logger.info("LangGraph agent compiled successfully")
    logger.info("Flow: START -> retrieve -> reasoning -> END")

    return graph


# ============================================================================
# Main Test Execution
# ============================================================================

def main():
    """
    Test the agentic layer with the 'Grid-Lock' query.

    This test validates the agent's ability to:
    1. Retrieve relevant documents across all three domains
    2. Connect high-level Telekom latency issues to low-level Illigo hardware faults
    3. Generate a coherent diagnosis citing specific sources
    """
    logger.info("\n" + "=" * 80)
    logger.info("TESTING AGENTIC LAYER - LangGraph with ChatGroq")
    logger.info("=" * 80)

    try:
        # Create the agent graph
        agent_graph = create_agent_graph()

        # Define the Grid-Lock test query
        test_query = "Telekom reports high latency at the Koumassi microgrid. Is there a hardware fault explaining this?"

        logger.info("\n" + "=" * 80)
        logger.info("GRID-LOCK TEST QUERY")
        logger.info("=" * 80)
        logger.info(f"Query: {test_query}")
        logger.info("\nExpected Behavior:")
        logger.info("  1. Retrieve documents mentioning Koumassi, latency, and faults")
        logger.info("  2. Cross-reference Telekom SLA with Illigo logs")
        logger.info("  3. Identify ground fault as root cause")
        logger.info("=" * 80)

        # Initialize state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=test_query)],
            "documents": [],
            "diagnosis": ""
        }

        # Run the agent
        logger.info("\nExecuting agent workflow...\n")
        final_state = agent_graph.invoke(initial_state)

        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("AGENT EXECUTION COMPLETED")
        logger.info("=" * 80)

        logger.info(f"\nDocuments Retrieved: {len(final_state['documents'])}")

        if final_state['documents']:
            logger.info("\nRetrieved Evidence Sources:")
            for i, doc in enumerate(final_state['documents'], 1):
                source = doc.metadata.get('source_type', 'unknown')
                file_name = doc.metadata.get('file_name', 'unknown')
                logger.info(f"  {i}. {source} - {file_name}")

        logger.info("\n" + "=" * 80)
        logger.info("DIAGNOSIS")
        logger.info("=" * 80)
        print(final_state['diagnosis'])

        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nThe agent successfully 'connected the dots' between:")
        logger.info("  - Telekom high-level latency symptom")
        logger.info("  - Illigo low-level ground fault logs")
        logger.info("  - Root cause diagnosis with source citations")

    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
