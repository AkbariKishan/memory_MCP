from mcp.server.fastmcp import FastMCP, Context
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from typing import List, Dict, Union
import json
import logging
import asyncio

# Import our custom classes (assuming relative import works with PYTHONPATH setup or installed pkg)
# For simplicity, let's assume we run this from project root
try:
    from src.memory_store import MemoryStore
    from src.agents.grounder import GroundingAgent
except ImportError:
    # Try local import if running directly
    from memory_store import MemoryStore
    from agents.grounder import GroundingAgent


import os

# Initialize Server
mcp = FastMCP("memory-server")

# Initialize Storage
# Use default path (handled in MemoryStore class)
memory_store = MemoryStore()

# Initialize Grounding Agent
grounding_agent = GroundingAgent(memory_store)

@mcp.resource("memory://context")
def get_context() -> str:
    """
    Get the current structured fact sheet context.
    The LLM can read this to understand the current state and preferences of the user.
    """
    facts = memory_store.get_fact_sheet()
    
    fact_str = "No structured facts stored yet."
    if facts:
        fact_str = "\n".join([f"- {topic}: {content}" for topic, content in facts.items()])
    
    return f"--- STRUCTURED FACT SHEET ---\n{fact_str}"

@mcp.resource("memory://fact-sheet")
def get_fact_sheet_resource() -> str:
    """
    Get the structured Fact Sheet which contains categorized information.
    """
    facts = memory_store.get_fact_sheet()
    if not facts:
        return "Fact sheet is currently empty."
    return "\n".join([f"- {topic}: {content}" for topic, content in facts.items()])

@mcp.tool()
def store_memory(content: str, metadata: str = "{}") -> str:
    """
    Store a new memory in the vector database.
    
    Args:
        content: The text content of the memory to store.
        metadata: Optional JSON string of metadata (e.g., {"source": "chat", "timestamp": "..."}).
    """
    try:
        meta_dict = json.loads(metadata)
    except json.JSONDecodeError:
        meta_dict = {"raw_metadata": metadata}
        
    memory_id = memory_store.add_memory(content, meta_dict)
    return f"Memory stored successfully with ID: {memory_id}"

@mcp.tool()
def retrieve_memory(query: str, limit: int = 5) -> str:
    """
    Retrieve relevant memories based on a semantic query.
    
    Args:
        query: The search query to find relevant memories.
        limit: The maximum number of memories to return (default 5).
    """
    results = memory_store.search_memory(query, limit)
    
    if not results:
        return "No relevant memories found."
        
    formatted_results = []
    for doc in results:
        # Include ID for deletion purposes
        formatted_results.append(f"[{doc['id']}] {doc['content']} (Target: {doc['metadata']})")
        
    return "\n".join(formatted_results)

@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """
    Delete a specific memory by its ID.
    
    Args:
        memory_id: The UUID of the memory to delete.
    """
    try:
        memory_store.delete_memory(memory_id)
        return f"Memory with ID {memory_id} deleted successfully."
    except Exception as e:
        return f"Failed to delete memory: {str(e)}"

@mcp.tool()
def delete_all_memories() -> str:
    """
    Delete ALL memories. Use with caution.
    """
    try:
        memory_store.delete_all()
        return "All memories have been deleted."
    except Exception as e:
        return f"Failed to delete all memories: {str(e)}"

@mcp.tool()
def update_fact(topic: str, content: str) -> str:
    """
    Update the structured Fact Sheet with new or revised information.
    Use this to store static knowledge about the user, project, or environment.
    
    Args:
        topic: The category or subject of the fact (e.g., 'User Preferences', 'Tech Stack').
        content: The detailed information to store for this topic.
    """
    memory_store.update_fact(topic, content)
    return f"Fact sheet updated for topic: {topic}"

@mcp.tool()
def ground_query(query: str, max_facts: int = 5) -> str:
    """
    Enrich a query with relevant context from the memory system.
    Use this before sending a query to the chatbot to inject relevant facts.
    
    Args:
        query: The user's query
        max_facts: Maximum number of facts to include (default 5)
    """
    try:
        enriched_query = grounding_agent.enrich_query(query, max_facts=max_facts)
        return enriched_query
    except Exception as e:
        return f"Error grounding query: {str(e)}. Using original query: {query}"

@mcp.tool()
def get_fact_sheet() -> str:
    """
    Retrieve the entire structured Fact Sheet.
    """
    facts = memory_store.get_fact_sheet()
    if not facts:
        return "Fact sheet is currently empty."
    return json.dumps(facts, indent=2)

if __name__ == "__main__":
    mcp.run()
