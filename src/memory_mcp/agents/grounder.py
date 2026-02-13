"""
Grounding Agent - Retrieves relevant context before chatbot responses
Uses semantic search and fact retrieval to enrich queries with relevant information
"""
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GroundingAgent:
    """
    Agent that retrieves relevant facts and memories to ground chatbot responses.
    This agent runs before the main chatbot LLM to inject relevant context.
    """
    
    def __init__(self, memory_store):
        """
        Initialize the Grounding Agent.
        
        Args:
            memory_store: MemoryStore instance for accessing facts and memories
        """
        self.memory_store = memory_store
        
    def retrieve_relevant_facts(self, query: str, max_facts: int = 5) -> List[Dict]:
        """
        Retrieve facts relevant to the query.
        
        Args:
            query: The user's query or message
            max_facts: Maximum number of facts to retrieve
            
        Returns:
            List of relevant facts with their metadata
        """
        relevant_facts = []
        
        # Get all facts from fact sheet
        fact_sheet = self.memory_store.get_fact_sheet()
        
        # Simple relevance scoring based on keyword matching
        # In production, you'd use semantic similarity
        query_lower = query.lower()
        
        for topic, fact_data in fact_sheet.items():
            if isinstance(fact_data, dict):
                content = fact_data.get("content", "")
                entities = fact_data.get("metadata", {}).get("entities", [])
                category = fact_data.get("metadata", {}).get("category", "unknown")
                
                # Check if query mentions any entities or topic
                relevance_score = 0
                
                # Topic match
                if any(word in topic.lower() for word in query_lower.split()):
                    relevance_score += 2
                
                # Entity match
                for entity in entities:
                    if entity.lower() in query_lower:
                        relevance_score += 3
                
                # Content match
                if any(word in content.lower() for word in query_lower.split() if len(word) > 3):
                    relevance_score += 1
                
                if relevance_score > 0:
                    relevant_facts.append({
                        "topic": topic,
                        "content": content,
                        "entities": entities,
                        "category": category,
                        "relevance": relevance_score
                    })
            else:
                # Handle old format (simple string)
                if any(word in fact_data.lower() for word in query_lower.split() if len(word) > 3):
                    relevant_facts.append({
                        "topic": topic,
                        "content": fact_data,
                        "entities": [],
                        "category": "unknown",
                        "relevance": 1
                    })
        
        # Sort by relevance and return top N
        relevant_facts.sort(key=lambda x: x["relevance"], reverse=True)
        return relevant_facts[:max_facts]
    
    def retrieve_semantic_memories(self, query: str, limit: int = 3) -> List[Dict]:
        """
        Retrieve semantically similar memories from vector database.
        
        Args:
            query: The user's query
            limit: Maximum number of memories to retrieve
            
        Returns:
            List of relevant memories
        """
        try:
            memories = self.memory_store.search_memory(query, limit)
            return memories
        except Exception as e:
            logger.error(f"Error retrieving semantic memories: {e}")
            return []
    
    def enrich_query(self, query: str, max_facts: int = 5, include_memories: bool = True) -> str:
        """
        Enrich a query with relevant context from the memory system.
        
        Args:
            query: The original user query
            max_facts: Maximum number of facts to include
            include_memories: Whether to include semantic memories
            
        Returns:
            Enriched query with context injection
        """
        # Retrieve relevant facts
        facts = self.retrieve_relevant_facts(query, max_facts)
        
        # Build context string
        context_parts = []
        
        if facts:
            fact_strings = []
            for fact in facts:
                topic = fact.get("topic", "Unknown")
                content = fact.get("content", "")
                fact_strings.append(f"- {topic}: {content}")
            
            context_parts.append("Based on what I know about you:\n" + "\n".join(fact_strings))
        
        # Optionally include semantic memories
        if include_memories:
            memories = self.retrieve_semantic_memories(query, limit=2)
            if memories:
                memory_strings = []
                for mem in memories:
                    content = mem.get("content", "")
                    if content and content not in [f.get("content", "") for f in facts]:
                        memory_strings.append(f"- {content}")
                
                if memory_strings:
                    context_parts.append("Relevant past context:\n" + "\n".join(memory_strings))
        
        # Build enriched query
        if context_parts:
            enriched = "\n\n".join(context_parts) + f"\n\nUser query: {query}"
            logger.info(f"Enriched query with {len(facts)} facts and context")
            return enriched
        else:
            logger.info("No relevant context found, using original query")
            return query
    
    def should_ground(self, query: str, threshold: int = 1) -> bool:
        """
        Determine if grounding is beneficial for this query.
        
        Args:
            query: The user's query
            threshold: Minimum number of relevant facts to trigger grounding
            
        Returns:
            True if grounding should be applied
        """
        facts = self.retrieve_relevant_facts(query, max_facts=1)
        return len(facts) >= threshold
