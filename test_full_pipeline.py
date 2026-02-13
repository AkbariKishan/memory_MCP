"""
Integration test for Monitor → Extraction → MemoryStore pipeline
"""
from src.memory_mcp.agents.monitor import MonitorAgentSync
from src.memory_mcp.agents.extractor import ExtractionAgent
from src.memory_mcp.memory_store import MemoryStore
import os
import shutil

def test_full_pipeline():
    """Test the complete fact extraction and storage pipeline"""
    
    # Setup test directory
    test_dir = os.path.join(os.path.expanduser("~"), ".memory_mcp_test_pipeline")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    # Initialize agents and storage
    monitor = MonitorAgentSync()
    extractor = ExtractionAgent()
    memory = MemoryStore(path=os.path.join(test_dir, "chroma_db"))
    
    # Test messages
    test_messages = [
        "I prefer dark mode in all my applications",
        "Hello, how are you?",  # Should be filtered
        "This project uses FastAPI and PostgreSQL",
        "My name is Sarah and I work as a data scientist",
        "Thanks!",  # Should be filtered
        "I always use Python 3.11 for new projects",
    ]
    
    print("=== Full Pipeline Test ===\n")
    
    for message in test_messages:
        print(f"Processing: \"{message}\"")
        
        # Step 1: Monitor classifies
        classification = monitor.classify(message)
        important = classification.get("important", False)
        category = classification.get("category", "unknown")
        
        print(f"  Classification: important={important}, category={category}")
        
        if important:
            # Step 2: Extract facts
            extraction = extractor.extract_facts(message, category)
            topic = extraction.get("topic", "General")
            content = extraction.get("content", message)
            entities = extraction.get("entities", [])
            
            print(f"  Extracted: topic=\"{topic}\", entities={entities}")
            
            # Step 3: Store in memory
            memory.update_fact_with_metadata(topic, content, entities, category)
            print(f"  ✓ Stored in memory")
        else:
            print(f"  ✗ Filtered out (not important)")
        
        print()
    
    # Verify stored facts
    print("=== Stored Facts ===\n")
    fact_sheet = memory.get_fact_sheet()
    
    for topic, fact_data in fact_sheet.items():
        if isinstance(fact_data, dict):
            content = fact_data.get("content", "")
            entities = fact_data.get("metadata", {}).get("entities", [])
            print(f"Topic: {topic}")
            print(f"  Content: {content}")
            print(f"  Entities: {entities}")
        else:
            print(f"Topic: {topic}")
            print(f"  Content: {fact_data}")
        print()
    
    # Test entity-based retrieval
    print("=== Entity-Based Retrieval ===\n")
    sarah_facts = memory.get_facts_by_entity("Sarah")
    print(f"Facts mentioning 'Sarah': {len(sarah_facts)}")
    for fact in sarah_facts:
        print(f"  - {fact['topic']}: {fact['content']}")
    
    python_facts = memory.get_facts_by_entity("Python 3.11")
    print(f"\nFacts mentioning 'Python 3.11': {len(python_facts)}")
    for fact in python_facts:
        print(f"  - {fact['topic']}: {fact['content']}")
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_full_pipeline()
