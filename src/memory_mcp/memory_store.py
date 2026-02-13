import chromadb
from chromadb.utils import embedding_functions
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
import os
import json

class MemoryStore:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            # Default to user's home directory for persistence
            base_dir = os.path.join(os.path.expanduser("~"), ".memory_mcp")
            path = os.path.join(base_dir, "chroma_db")
        else:
            base_dir = os.path.dirname(path)

        os.makedirs(base_dir, exist_ok=True)
            
        self.client = chromadb.PersistentClient(path=path)
        # Use default sentence-transformers model
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="memory",
            embedding_function=self.embedding_fn
        )
        
        # Fact Sheet (Semantic Memory) persistence
        self.fact_sheet_path = os.path.join(base_dir, "fact_sheet.json")
        self.fact_sheet = self._load_fact_sheet()
        self._migrate_fact_sheet()

    def _load_fact_sheet(self) -> Dict:
        if os.path.exists(self.fact_sheet_path):
            try:
                with open(self.fact_sheet_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_fact_sheet(self):
        with open(self.fact_sheet_path, "w", encoding="utf-8") as f:
            json.dump(self.fact_sheet, f, ensure_ascii=False, indent=2)

    def _migrate_fact_sheet(self):
        """Ensure all facts have the new metadata structure"""
        modified = False
        now = datetime.now().isoformat()
        
        for topic, data in list(self.fact_sheet.items()):
            if isinstance(data, str):
                # Convert old string format to structural object
                self.fact_sheet[topic] = {
                    "content": data,
                    "metadata": {
                        "created_at": now,
                        "updated_at": now,
                        "last_accessed": now,
                        "importance_score": 0.5,
                        "category": "unknown",
                        "entities": []
                    }
                }
                modified = True
            elif isinstance(data, dict) and "metadata" in data:
                # Add missing fields to existing dict objects
                meta = data["metadata"]
                if "importance_score" not in meta:
                    meta["importance_score"] = 0.5
                if "created_at" not in meta:
                    meta["created_at"] = meta.get("updated_at", now)
                if "last_accessed" not in meta:
                    meta["last_accessed"] = meta.get("updated_at", now)
                modified = True
        
        if modified:
            self._save_fact_sheet()

    def update_fact(self, topic: str, content: str, metadata: Optional[Dict] = None):
        """Update a fact with optional metadata and cognitive tracking"""
        now = datetime.now().isoformat()
        
        if metadata is None:
            metadata = {}
        
        # Merge existing metadata if topic exists
        existing = self.fact_sheet.get(topic)
        if isinstance(existing, dict) and "metadata" in existing:
            base_meta = existing["metadata"]
            # Preserve created_at
            metadata["created_at"] = base_meta.get("created_at", now)
        else:
            metadata["created_at"] = now

        # Update importance and timestamps
        metadata["updated_at"] = now
        metadata["last_accessed"] = now
        if "importance_score" not in metadata:
            metadata["importance_score"] = 0.5
            
        self.fact_sheet[topic] = {
            "content": content,
            "metadata": metadata
        }
        
        self._save_fact_sheet()
    
    def update_fact_with_metadata(self, topic: str, content: str, entities: List[str] = None, category: str = None, importance: float = 0.5):
        """Update a fact with full metadata from Agents"""
        metadata = {
            "entities": entities or [],
            "category": category,
            "importance_score": importance
        }
        self.update_fact(topic, content, metadata)
    
    def get_fact(self, topic: str) -> Optional[Dict]:
        """Get a fact and update its access timestamp"""
        if topic in self.fact_sheet:
            fact = self.fact_sheet[topic]
            if isinstance(fact, dict) and "metadata" in fact:
                fact["metadata"]["last_accessed"] = datetime.now().isoformat()
                self._save_fact_sheet()
            return fact
        return None

    def get_facts_by_entity(self, entity: str) -> List[Dict]:
        """Retrieve all facts that mention a specific entity (updates access timestamps)"""
        matching_facts = []
        now = datetime.now().isoformat()
        modified = False
        
        for topic, fact_data in self.fact_sheet.items():
            if isinstance(fact_data, dict):
                entities = fact_data.get("metadata", {}).get("entities", [])
                if entity.lower() in [e.lower() for e in entities]:
                    fact_data["metadata"]["last_accessed"] = now
                    modified = True
                    matching_facts.append({
                        "topic": topic,
                        "content": fact_data.get("content", ""),
                        "entities": entities,
                        "category": fact_data.get("metadata", {}).get("category", "unknown"),
                        "importance": fact_data.get("metadata", {}).get("importance_score", 0.5)
                    })
        
        if modified:
            self._save_fact_sheet()
        return matching_facts

    def get_fact_sheet(self) -> Dict:
        return self.fact_sheet

    def add_memory(self, content: str, metadata: Optional[Dict] = None) -> str:
        """Add episodic memory with importance tracking"""
        memory_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        if metadata is None:
            metadata = {}
        
        metadata["created_at"] = now
        metadata["last_accessed"] = now
        if "importance_score" not in metadata:
            metadata["importance_score"] = 0.5
            
        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[memory_id]
        )
        return memory_id

    def search_memory(self, query: str, limit: int = 5) -> List[Dict]:
        """Search episodic memories and update access timestamps"""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        memories = []
        if results["documents"]:
            now = datetime.now().isoformat()
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                mem_id = results["ids"][0][i]
                
                # Update last_accessed in ChromaDB (requires update call)
                meta["last_accessed"] = now
                self.collection.update(ids=[mem_id], metadatas=[meta])
                
                memories.append({
                    "content": doc,
                    "metadata": meta,
                    "id": mem_id
                })
        return memories

    def delete_memory(self, memory_id: str):
        self.collection.delete(ids=[memory_id])

    def delete_all(self):
        ids = self.collection.get()['ids']
        if ids:
            self.collection.delete(ids=ids)
