import chromadb
from chromadb.utils import embedding_functions
import uuid
from typing import List, Dict, Optional

import os

class MemoryStore:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            # Default to user's home directory for persistence
            base_dir = os.path.join(os.path.expanduser("~"), ".memory_mcp")
            path = os.path.join(base_dir, "chroma_db")
        else:
            # If custom path is provided, derive base_dir from it
            # Assuming path ends with 'chroma_db' or similar, we might want buffer next to it
            base_dir = os.path.dirname(path)

        os.makedirs(base_dir, exist_ok=True)
            
        self.client = chromadb.PersistentClient(path=path)
        # Use default sentence-transformers model (all-MiniLM-L6-v2)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="memory",
            embedding_function=self.embedding_fn
        )
        
        # Fact Sheet persistence
        self.fact_sheet_path = os.path.join(base_dir, "fact_sheet.json")
        self.fact_sheet = self._load_fact_sheet()

    def _load_fact_sheet(self) -> Dict:
        if os.path.exists(self.fact_sheet_path):
            try:
                import json
                with open(self.fact_sheet_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_fact_sheet(self):
        import json
        with open(self.fact_sheet_path, "w", encoding="utf-8") as f:
            json.dump(self.fact_sheet, f, ensure_ascii=False, indent=2)

    def update_fact(self, topic: str, content: str, metadata: Optional[Dict] = None):
        """Update a fact with optional metadata (entities, timestamps, etc.)"""
        from datetime import datetime
        
        if metadata is None:
            metadata = {}
        
        # Add timestamp
        metadata["updated_at"] = datetime.now().isoformat()
        
        # Store as structured object if metadata provided
        if metadata:
            self.fact_sheet[topic] = {
                "content": content,
                "metadata": metadata
            }
        else:
            # Backward compatibility: store as simple string
            self.fact_sheet[topic] = content
        
        self._save_fact_sheet()
    
    def update_fact_with_metadata(self, topic: str, content: str, entities: List[str] = None, category: str = None):
        """Update a fact with full metadata from Extraction Agent"""
        metadata = {
            "entities": entities or [],
            "category": category
        }
        self.update_fact(topic, content, metadata)
    
    def get_facts_by_entity(self, entity: str) -> List[Dict]:
        """Retrieve all facts that mention a specific entity"""
        matching_facts = []
        
        for topic, fact_data in self.fact_sheet.items():
            # Handle both old (string) and new (dict) format
            if isinstance(fact_data, dict):
                entities = fact_data.get("metadata", {}).get("entities", [])
                if entity.lower() in [e.lower() for e in entities]:
                    matching_facts.append({
                        "topic": topic,
                        "content": fact_data.get("content", ""),
                        "entities": entities,
                        "category": fact_data.get("metadata", {}).get("category", "unknown")
                    })
        
        return matching_facts

    def get_fact_sheet(self) -> Dict:
        return self.fact_sheet

    def add_memory(self, content: str, metadata: Optional[Dict] = None) -> str:
        memory_id = str(uuid.uuid4())
        self.collection.add(
            documents=[content],
            metadatas=[metadata or {}],
            ids=[memory_id]
        )
        return memory_id

    def search_memory(self, query: str, limit: int = 5) -> List[Dict]:
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        memories = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "id": results["ids"][0][i]
                })
        return memories

    def delete_memory(self, memory_id: str):
        self.collection.delete(ids=[memory_id])

    def delete_all(self):
        # We can't delete the collection easily if we want to keep using it without re-init
        # So we delete all items
        ids = self.collection.get()['ids']
        if ids:
            self.collection.delete(ids=ids)
