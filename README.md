# Memory MCP Server

A privacy-focused, local long-term memory layer for Claude and other MCP clients. It uses vector storage for semantic search and a structured "Fact-Sheet" to maintain a consistent profile of your projects and preferences.

## Key Features

- **🛡️ 100% Local & Private**: All data is stored in `~/.memory_mcp/`. No external LLMs or API keys are required for summarization.
- **📋 Fact-Sheet Architect**: Claude proactively manages a structured knowledge base of your facts and preferences.
- **🔍 Semantic Search**: Uses ChromaDB and `sentence-transformers` to find relevant memories based on meaning, not just keywords.
- **⚡ Zero Dependency (LLM)**: Leverages the environment's LLM (e.g., Claude Desktop) for reasoning, removing the need for local Ollama or high-resource background tasks.

## Setup

### 1. Install Dependencies
```bash
pip install mcp[cli] chromadb sentence_transformers
```

### 2. Configure Claude Desktop
Add the following to your `claude_desktop_config.json` (usually found at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "python3",
      "args": [
        "/PATH/TO/memory_MCP/src/memory_mcp/server.py"
      ],
      "env": {
        "PYTHONPATH": "/PATH/TO/memory_MCP"
      }
    }
  }
}
```

## Usage

### The "Memory Instruction"
To make the memory layer effective, add the following to your **Claude Desktop Custom Instructions**:

> "You are an expert at managing project context. Use the `update_fact` tool whenever you learn a new preference, tech stack detail, or project goal. Always refer to the `memory://context` resource to ground your answers in existing knowledge."

### Available Tools
- **`update_fact`**: Store or update a categorized fact (e.g., "User Preferences").
- **`get_fact_sheet`**: View the current structured knowledge base.
- **`store_memory`**: Add a raw text memory to the vector database.
- **`retrieve_memory`**: Search historical memories using semantic query.

## Project Structure

```text
memory_MCP/
├── src/
│   └── memory_mcp/
│       ├── __init__.py
│       ├── server.py        # MCP Server entry point & tools logic
│       └── memory_store.py  # ChromaDB & Fact-Sheet persistence layer
├── tests/
│   └── test_memory.py       # Unit tests
├── README.md                # Documentation
└── pyproject.toml           # Project metadata & dependencies
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
