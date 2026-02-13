from mcp.server.fastmcp import FastMCP, Context
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from typing import List, Dict, Union, Optional
import json
import logging
import asyncio
import os
import time

# Import our custom classes
try:
    from src.memory_mcp.memory_store import MemoryStore
    from src.memory_mcp.agents.grounder import GroundingAgent
    from src.memory_mcp.agents.monitor import MonitorAgent
    from src.memory_mcp.agents.extractor import ExtractionAgent
    from src.memory_mcp.agents.reflector import ReflectorAgent
    from src.memory_mcp.config import config
except ImportError:
    from memory_mcp.memory_store import MemoryStore
    from memory_mcp.agents.grounder import GroundingAgent
    from memory_mcp.agents.monitor import MonitorAgent
    from memory_mcp.agents.extractor import ExtractionAgent
    from memory_mcp.agents.reflector import ReflectorAgent
    from memory_mcp.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Server
mcp = FastMCP("memory-server")

# Initialize Storage & Agents
memory_store = MemoryStore()
grounding_agent = GroundingAgent(memory_store)
monitor_agent = MonitorAgent()
extraction_agent = ExtractionAgent()
reflector_agent = ReflectorAgent()

# Automation State
MESSAGE_COUNTER = 0

async def run_maintenance_loop():
    """Background loop to periodically run reflection if enabled."""
    # Wait for server to stabilize
    await asyncio.sleep(5)
    
    interval = config.get("reflector.interval_seconds", 1800)
    enabled = config.get("reflector.enable_background_loop", False)
    
    if not enabled:
        logger.info("Background maintenance loop is disabled via config.")
        return

    logger.info(f"Background maintenance loop started. Interval: {interval}s")
    while True:
        try:
            logger.info("Starting scheduled background reflection cycle...")
            await reflector_agent.reflect(memory_store)
            logger.info(f"Background reflection complete. Sleeping for {interval}s")
        except Exception as e:
            logger.error(f"Error in maintenance loop: {e}")
        
        await asyncio.sleep(interval)

# Background task initialization logic can be added here if needed, 
# but FastMCP handles the event loop inside mcp.run().
# For now, we remove the invalid decorator to allow connection.

@mcp.resource("memory://context")
def get_context() -> str:
    """Get summarized semantic memory context."""
    facts = memory_store.get_fact_sheet()
    if not facts:
        return "No structured facts stored yet."
    fact_str = "\n".join([f"- {topic}: {data.get('content') if isinstance(data, dict) else data}" for topic, data in facts.items()])
    return f"--- SEMANTIC MEMORY ---\n{fact_str}"

@mcp.tool()
def store_memory(content: str, importance: float = 0.5) -> str:
    """Store raw episodic memory with importance tracking."""
    meta = {"importance_score": importance, "source": "manual"}
    memory_id = memory_store.add_memory(content, meta)
    return f"Episodic memory stored | ID: {memory_id} | Importance: {importance}"

@mcp.tool()
def update_fact(topic: str, content: str, importance: float = 0.8) -> str:
    """Manually update the semantic fact sheet."""
    memory_store.update_fact_with_metadata(topic, content, importance=importance)
    return f"Fact Sheet updated: {topic}"

@mcp.tool()
async def process_message(message: str, context: Optional[list] = None) -> str:
    """
    Autonomous pipeline: Monitor -> Extract -> Store.
    Automatically handles importance scoring and conflict resolution.
    """
    global MESSAGE_COUNTER
    
    # 1. Classify
    classification = await monitor_agent.classify(message, context)
    if not classification.get("important"):
        return "Message classified as chitchat. No action taken."
    
    # 2. Extract
    extraction = extraction_agent.extract_facts(message, classification.get("category", "fact"), context)
    topic = extraction.get("topic")
    content = extraction.get("content")
    
    # 3. Conflict Resolution & Store
    existing = memory_store.get_fact(topic)
    if existing:
        logger.info(f"Conflict detected for topic: {topic}. Resolving...")
        content = await extraction_agent.resolve_conflict(content, existing.get("content"))
    
    memory_store.update_fact_with_metadata(
        topic=topic,
        content=content,
        entities=extraction.get("entities"),
        category=extraction.get("category"),
        importance=classification.get("importance_score", 0.5)
    )
    
    # 4. Turn-based automation check
    MESSAGE_COUNTER += 1
    maintenance_status = ""
    
    # Get threshold from config
    threshold = config.get("reflector.message_threshold", 20)
    
    if MESSAGE_COUNTER >= threshold:
        logger.info(f"Threshold reached ({MESSAGE_COUNTER}/{threshold}). Triggering turn-based reflection...")
        asyncio.create_task(reflector_agent.reflect(memory_store))
        MESSAGE_COUNTER = 0
        maintenance_status = f" | [Self-Maintenance Triggered (Threshold: {threshold})]"
    
    return f"Knowledge integrated: {topic} | Resolved: {bool(existing)}{maintenance_status}"

@mcp.tool()
async def reflect_and_consolidate() -> str:
    """Run cognitive reflection cycle manually (merge episodic -> semantic, prune old data)."""
    await reflector_agent.reflect(memory_store)
    return "Memory reflection complete. Facts consolidated and database pruned."

@mcp.tool()
def ground_query(query: str, max_facts: int = 5) -> str:
    """Enrich query with hierarchical context retrieval."""
    return grounding_agent.enrich_query(query, max_facts=max_facts)

@mcp.tool()
def get_fact_sheet() -> str:
    """Retrieve full semantic fact sheet in JSON format."""
    return json.dumps(memory_store.get_fact_sheet(), indent=2)

if __name__ == "__main__":
    mcp.run()
