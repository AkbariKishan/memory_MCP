import sys
import os
import shutil
from unittest.mock import MagicMock
import re

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.memory_store import MemoryStore
import src.server as server

def test_deletion_features():
    # 1. Setup a test path for persistence
    test_home = os.path.abspath("./test_home_deletion")
    os.makedirs(test_home, exist_ok=True)
    
    # Mock expanduser
    original_expanduser = os.path.expanduser
    os.path.expanduser = lambda x: x.replace("~", test_home) if x.startswith("~") else x
    
    print(f"Testing deletion with home: {test_home}")
    
    try:
        # Re-init server's memory store
        server.SUMMARY_PATH = os.path.join(test_home, ".memory_mcp", "summary.txt")
        server.memory_store = MemoryStore(path=os.path.join(test_home, ".memory_mcp", "chroma_db"))
        
        # Mock LLM Client
        server.llm_client.condense_memories = MagicMock(return_value="Summary after deletion.")
        
        print("1. Adding memories...")
        server.store_memory("Memory A", "{\"tag\": \"A\"}")
        server.store_memory("Memory B", "{\"tag\": \"B\"}")
        
        print("2. Retrieving memories (checking for IDs)...")
        results = server.retrieve_memory("Memory")
        print(f"   -> Results:\n{results}")
        
        # Extract ID of Memory A
        # Expected format: [ID] Content (Target: Metadata)
        match = re.search(r"\[([a-f0-9\-]+)\] Memory A", results)
        assert match, "Could not find ID for Memory A"
        memory_id_a = match.group(1)
        print(f"   -> Found ID for Memory A: {memory_id_a}")
        
        print("3. Deleting Memory A...")
        result = server.delete_memory(memory_id_a)
        print(f"   -> {result}")
        
        print("4. Verifying deletion...")
        results_after = server.retrieve_memory("Memory")
        assert "Memory A" not in results_after
        assert "Memory B" in results_after
        print("   -> Memory A deleted successfully.")
        
        print("5. Deleting ALL memories...")
        server.delete_all_memories()
        
        print("6. Verifying total wipe...")
        results_final = server.retrieve_memory("Memory")
        assert "No relevant memories found" in results_final or results_final.strip() == ""
        print("   -> All memories deleted.")
        
    finally:
        # Cleanup
        os.path.expanduser = original_expanduser
        pass

if __name__ == "__main__":
    test_deletion_features()
