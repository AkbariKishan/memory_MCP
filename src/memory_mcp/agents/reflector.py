import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import google.generativeai as genai
import requests

try:
    from src.memory_mcp.config import config
    from src.memory_mcp.memory_store import MemoryStore
except ImportError:
    from config import config
    from memory_store import MemoryStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReflectorAgent:
    """
    Agent responsible for memory consolidation and maintenance.
    Transforms episodic memories into semantic facts and prunes the database.
    """
    
    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or config.get("monitor.provider", "google")
        self.model_name = model or config.get("monitor.model", "gemini-flash-latest")
        self.ollama_url = config.get("ollama.url", "http://localhost:11434")
        
        if self.provider == "google":
            api_key = config.google_api_key
            if api_key:
                genai.configure(api_key=api_key)
                self.google_model = genai.GenerativeModel(self.model_name)
        
    def _build_consolidation_prompt(self, memories: List[Dict]) -> str:
        memory_text = "\n".join([f"- [{m.get('id')}] (Importance: {m.get('metadata', {}).get('importance_score', 0.5)}) {m.get('content')}" for m in memories])
        
        prompt = f"""You are a Memory Consolidation Agent. Your task is to extract stable, long-term facts from a set of recent episodic memories.

MEMORIES:
{memory_text}

TASK:
1. Identify stable facts, preferences, or technical details mentioned across these memories.
2. Group related items into a single, clean 'Semantic Fact'.
3. Assign an importance score (0.0 to 1.0) and a category.
4. If a memory is just context or temporary, ignore it.

Return ONLY a JSON list of facts to add to the Fact Sheet:
[
  {{
    "topic": "User Tech Stack",
    "content": "User primarily works with React, FastAPI, and PostgreSQL.",
    "importance": 0.8,
    "category": "project",
    "source_ids": ["uuid1", "uuid2"]
  }}
]"""
        return prompt

    async def reflect(self, store: MemoryStore):
        """Perform a reflection cycle: consolidate and prune"""
        logger.info("Starting memory reflection cycle...")
        
        # 1. Fetch recent or high-importance episodic memories
        # For simplicity in this version, we fetch a sample or items without 'consolidated' flag
        # (ChromaDB doesn't support complex filters well on all versions, so we fetch and filter locally)
        all_memories = store.collection.get()
        ids = all_memories['ids']
        metadatas = all_memories['metadatas']
        documents = all_memories['documents']
        
        candidates = []
        for i in range(len(ids)):
            meta = metadatas[i]
            # Only consolidate items that are high importance or haven't been processed
            if not meta.get("consolidated") and meta.get("importance_score", 0) > 0.4:
                candidates.append({
                    "id": ids[i],
                    "content": documents[i],
                    "metadata": meta
                })
        
        if len(candidates) >= 3:
            logger.info(f"Consolidating {len(candidates)} memory candidates...")
            facts = await self._consolidate(candidates)
            
            for fact in facts:
                store.update_fact_with_metadata(
                    topic=fact['topic'],
                    content=fact['content'],
                    importance=fact['importance'],
                    category=fact['category']
                )
                # Mark source memories as consolidated
                for src_id in fact.get('source_ids', []):
                    # We can either delete or tag them
                    # Tagging is safer for traceability
                    meta = store.collection.get(ids=[src_id])['metadatas'][0]
                    meta["consolidated"] = True
                    store.collection.update(ids=[src_id], metadatas=[meta])
                    
        # 2. Pruning: Remove low importance memories older than 30 days
        self._prune(store, ids, metadatas)
        
        logger.info("Reflection cycle complete.")

    async def _consolidate(self, memories: List[Dict]) -> List[Dict]:
        """Call LLM to consolidate memories"""
        prompt = self._build_consolidation_prompt(memories)
        
        try:
            if self.provider == "google":
                response = self.google_model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                return json.loads(response.text)
            else:
                # Ollama fallback
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
                res = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=60)
                if res.status_code == 200:
                    return json.loads(res.json().get('response', '[]'))
        except Exception as e:
            logger.error(f"Consolidation error: {e}")
            
        return []

    def _prune(self, store: MemoryStore, ids: List[str], metadatas: List[Dict]):
        """Remove outdated, low-importance memories"""
        now = datetime.now()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        
        to_delete = []
        for i in range(len(ids)):
            meta = metadatas[i]
            importance = meta.get("importance_score", 0.5)
            created_at = meta.get("created_at", "")
            
            # Delete if low importance and old OR if already consolidated and very old
            if importance < 0.3 and created_at < thirty_days_ago:
                to_delete.append(ids[i])
            elif meta.get("consolidated") and created_at < thirty_days_ago:
                to_delete.append(ids[i])
                
        if to_delete:
            logger.info(f"Pruning {len(to_delete)} old/low-value memories.")
            store.collection.delete(ids=to_delete)
