# Memory MCP Server
# Memory MCP - Advanced Memory Agent

A **Model Context Protocol (MCP) server** that provides long-term memory capabilities for AI chatbots using an autonomous three-agent architecture.

## Features

### 🤖 Three-Agent Architecture
- **Monitor Agent** (Llama 3.2 3B): Real-time message classification
- **Extraction Agent** (Llama 3.1 8B): Structured fact extraction
- **Grounding Agent**: Context injection before responses

### 💾 Dual Storage System
- **Structured Fact Sheet**: Human-readable JSON for static knowledge
- **Vector Database**: ChromaDB for semantic search of conversations

### 🔒 100% Local & Private
- All processing happens on your machine
- No external API calls required
- Data stored in `~/.memory_mcp/`

## How It Works

```
User Message → Monitor Agent → Extraction Agent → MemoryStore
                    ↓                                    ↓
              (Filter chitchat)              (Store with metadata)
                                                         ↓
User Query → Grounding Agent → Retrieve Facts → Enrich Context → Chatbot
```

## Installation

### Prerequisites
1. **Ollama** installed and running
2. **Python 3.10+**

### Setup

```bash
# 1. Install Ollama (if not already installed)
# macOS:
brew install ollama

# 2. Pull required models
ollama pull llama3.2:3b
ollama pull llama3.1:8b

# 3. Clone and install
git clone https://github.com/yourusername/memory_MCP.git
cd memory_MCP
pip install -e .

# 4. Test the installation
python3 test_full_pipeline.py
```

## Configuration

### Claude Desktop Setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "src.memory_mcp.server"],
      "cwd": "/PATH/TO/memory_MCP"
    }
  }
}
```

### Agent Configuration

Edit `config.yaml` to customize behavior:

```yaml
monitor:
  model: "llama3.2:3b"
  confidence_threshold: 0.6
  
extraction:
  model: "llama3.1:8b"
  
grounding:
  mode: "auto"  # auto | on_demand | disabled
  max_facts: 5
```

## Usage

### Available Tools

#### 1. `store_memory`
Store a memory in the vector database for semantic search.

```python
store_memory(content="We discussed implementing a REST API using FastAPI")
```

#### 2. `retrieve_memory`
Search for relevant memories semantically.

```python
retrieve_memory(query="What did we talk about regarding APIs?", limit=3)
```

#### 3. `update_fact`
Update the structured fact sheet (used by Extraction Agent automatically).

```python
update_fact(topic="Tech Stack", content="Uses FastAPI and PostgreSQL")
```

#### 4. `ground_query`
**NEW**: Enrich a query with relevant context before sending to chatbot.

```python
ground_query(query="What tech stack should I use?", max_facts=5)
# Returns: "Based on what I know about you:\n- Tech Stack: Uses FastAPI and PostgreSQL\n\nUser query: What tech stack should I use?"
```

#### 5. `get_fact_sheet`
Retrieve the entire structured fact sheet.

```python
get_fact_sheet()
```

### Available Resources

#### `memory://context`
Read the current fact sheet context.

#### `memory://fact-sheet`
Access the raw fact sheet data.

## Architecture

### Monitor Agent
- **Model**: Llama 3.2 3B (2GB, fast)
- **Purpose**: Classify messages as important or chitchat
- **Accuracy**: 100% on test cases
- **Latency**: ~1-2 seconds per message

### Extraction Agent
- **Model**: Llama 3.1 8B (4.9GB, accurate)
- **Purpose**: Extract structured facts (topic, content, entities)
- **Output**: JSON with metadata
- **Latency**: ~3-5 seconds per extraction

### Grounding Agent
- **Model**: Reuses main chatbot LLM (no extra model)
- **Purpose**: Retrieve and inject relevant facts
- **Methods**: Keyword matching + semantic search
- **Latency**: <100ms

## Project Structure

```
memory_MCP/
├── src/memory_mcp/
│   ├── server.py              # MCP server with tools
│   ├── memory_store.py        # Storage layer
│   └── agents/
│       ├── monitor.py         # Message classification
│       ├── extractor.py       # Fact extraction
│       └── grounder.py        # Context retrieval
├── config.yaml                # Agent configuration
├── test_monitor_agent.py      # Unit tests
├── test_extraction_agent.py   # Unit tests
├── test_grounding_agent.py    # Unit tests
└── test_full_pipeline.py      # Integration test
```

## Testing

```bash
# Test individual agents
python3 test_monitor_agent.py
python3 test_extraction_agent.py
python3 test_grounding_agent.py

# Test full pipeline
python3 test_full_pipeline.py
```

## How to Use with Claude Desktop

1. **Automatic Mode** (Recommended):
   - The Monitor and Extraction agents run automatically in the background
   - Facts are extracted and stored without manual intervention
   - Use `ground_query` before asking questions to inject relevant context

2. **Manual Mode**:
   - Use `store_memory` to manually save important information
   - Use `update_fact` to manually update the fact sheet
   - Use `retrieve_memory` for semantic search

## Comparison with Mem0

| Feature | Mem0 | Memory MCP |
|---------|------|------------|
| Architecture | Knowledge Graph | Fact Sheet + Vector DB |
| Processing | Background Cloud | Local Real-time |
| Privacy | SaaS (Cloud) | 100% Local |
| Cost | Subscription | Free (Local LLMs) |
| Control | Black Box | White Box (Editable JSON) |
| Best For | Multi-user Systems | Personal Projects |

## License

MIT

## Contributing

Contributions welcome! Please open an issue or PR.
├── tests/
│   └── test_memory.py       # Unit tests
├── README.md                # Documentation
```

## Utility & How it works

The **Memory MCP** acts as a long-term bridge for LLMs. Claude (the "Brain") usually forgets everything after a session. This server (the "Library") provides:

1.  **Categorized Context (Fact-Sheet)**: Instead of reading raw chat logs, Claude maintains a clean JSON map of "what is certain." This is used to ground every new conversation.
2.  **Semantic Retrieval**: When an exact fact isn't found, the server uses vector embeddings to find "similar" things you've mentioned in the past.
3.  **Local Control**: Everything is stored in `~/.memory_mcp/`. You can edit `fact_sheet.json` manually if you ever need to "hard-code" or correct Claude's memory.

---

### Data Location
Your information is stored locally at:
`~/.memory_mcp/`
