# Infrastructure: Graphiti + FalkorDB

> **Implements**: Phase V (V1–V5)
> **UserInput Refs**: A1, A5

## Overview

Graphiti is the open-source temporal knowledge graph engine that powers Zep Cloud (24.5k ★, Apache 2.0). We use it with FalkorDB (a Redis-compatible graph database) for local development, and can switch to Neo4j for AWS production.

**Why Graphiti?** It tracks **temporal facts** — how opinions change over time — which is perfect for a simulation where agent stances evolve across rounds.

## Architecture

```
┌── Backend (FastAPI) ───────────────────────────────┐
│                                                     │
│  GraphitiService                                    │
│  ├── graphiti_core.Graphiti (client)                │
│  ├── Uses session LLM (Gemini/OpenAI)              │
│  └── Temporal memory: agent opinions, chat history  │
│                                                     │
└────────────────┬────────────────────────────────────┘
                 │ bolt://falkordb:6379
┌────────────────▼────────────────────────────────────┐
│  FalkorDB (Redis-compatible graph DB)               │
│  Image: falkordb/falkordb:latest (~200MB)           │
│  Port: 6379 · No Java · Minimal RAM                 │
│  Data: /data (Docker volume)                         │
└─────────────────────────────────────────────────────┘
```

## Installation

Already included in `docker-compose.yml`. For Python:

```bash
pip install graphiti-core[google-genai]  # For Gemini
# or
pip install graphiti-core                # Core only, bring your own LLM client
```

## GraphitiService Implementation

```python
# backend/src/mckainsey/services/graphiti_service.py

from graphiti_core import Graphiti
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
import os

class GraphitiService:
    """Manages temporal knowledge graph for agent memory.

    Replaces Zep Cloud. Tracks how agent opinions evolve across
    simulation rounds and provides context for chat interactions.
    """

    def __init__(self, session_config: dict):
        self.session_id = session_config["session_id"]
        self.provider = session_config.get("provider", "gemini")
        self.api_key = session_config.get("api_key", "")
        self.model = session_config.get("model", "gemini-2.0-flash")

        # Graph DB connection
        self.db_url = os.getenv("FALKORDB_HOST", "localhost")
        self.db_port = int(os.getenv("FALKORDB_PORT", "6379"))

        self.graphiti = None

    async def initialize(self):
        """Initialize Graphiti client with the session's LLM provider."""
        if self.provider == "gemini":
            llm_client = GeminiClient(
                config=LLMConfig(api_key=self.api_key, model=self.model)
            )
        elif self.provider == "openai":
            llm_client = OpenAIClient(
                config=LLMConfig(api_key=self.api_key, model=self.model)
            )
        elif self.provider == "ollama":
            # Ollama uses OpenAI-compatible API
            llm_client = OpenAIClient(
                config=LLMConfig(
                    api_key="ollama",
                    model=self.model,
                    base_url="http://host.docker.internal:11434/v1"
                )
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        self.graphiti = Graphiti(
            f"bolt://{self.db_url}:{self.db_port}",
            "default",
            "",
            llm_client=llm_client,
        )
        await self.graphiti.build_indices_and_constraints()

    async def add_agent_memory(self, agent_id: str, content: str,
                                round_no: int, timestamp: str):
        """Store an agent's post/opinion as a temporal fact.

        This creates nodes and edges in the knowledge graph that
        track how the agent's views evolve over time.
        """
        await self.graphiti.add_episode(
            name=f"agent_{agent_id}_round_{round_no}",
            episode_body=content,
            source_description=f"Agent {agent_id} during round {round_no}",
            reference_time=timestamp,
            group_id=f"session_{self.session_id}",
        )

    async def add_opinion_checkpoint(self, agent_id: str, opinion_score: float,
                                      round_no: int, timestamp: str):
        """Record an agent's checkpoint opinion score as a temporal fact."""
        await self.graphiti.add_episode(
            name=f"checkpoint_{agent_id}_round_{round_no}",
            episode_body=f"Agent {agent_id} rated their opinion as {opinion_score}/10 at round {round_no}.",
            source_description=f"Checkpoint interview for agent {agent_id}",
            reference_time=timestamp,
            group_id=f"session_{self.session_id}",
        )

    async def search_agent_context(self, agent_id: str, query: str,
                                    limit: int = 10) -> list[dict]:
        """Search the knowledge graph for relevant context about an agent.

        Used during chat to retrieve the agent's history, opinions,
        and interactions.
        """
        results = await self.graphiti.search(
            query=query,
            group_ids=[f"session_{self.session_id}"],
            num_results=limit,
        )
        return [
            {
                "content": r.fact,
                "timestamp": str(r.valid_at),
                "confidence": r.score,
            }
            for r in results
        ]

    async def get_agent_opinion_history(self, agent_id: str) -> list[dict]:
        """Retrieve an agent's opinion trajectory across rounds."""
        results = await self.graphiti.search(
            query=f"opinion score for agent {agent_id}",
            group_ids=[f"session_{self.session_id}"],
            num_results=20,
        )
        return [
            {"fact": r.fact, "timestamp": str(r.valid_at)}
            for r in results
        ]

    async def cleanup(self):
        """Clean up session data after simulation ends."""
        if self.graphiti:
            await self.graphiti.close()
```

## Migration from Zep Cloud

### What was Zep Cloud doing?

Looking at `memory_service.py`, Zep was used for:
1. Storing agent memories (posts, opinions) during simulation
2. Searching agent context during chat interactions
3. Maintaining chat session history

### Migration mapping

| Zep Cloud Method | Graphiti Replacement |
|:-----------------|:--------------------|
| `zep.memory.add_memory()` | `graphiti.add_episode()` |
| `zep.memory.search()` | `graphiti.search()` |
| `zep.user.add()` | N/A (agents are episode sources) |
| `zep.memory.get_session()` | `graphiti.search(group_ids=[session_id])` |

### Fallback

Keep Zep Cloud as an optional fallback via environment variable:

```python
# In memory_service.py
MEMORY_BACKEND = os.getenv("MEMORY_BACKEND", "graphiti")  # or "zep"

if MEMORY_BACKEND == "graphiti":
    service = GraphitiService(session_config)
elif MEMORY_BACKEND == "zep":
    service = ZepService(session_config)  # existing implementation
```

## FalkorDB vs Neo4j

| Feature | FalkorDB (Local) | Neo4j (AWS) |
|:--------|:-----------------|:------------|
| Image size | ~200MB | ~500MB |
| RAM | Minimal | 1GB+ |
| Language | Redis protocol | Bolt protocol |
| UI Dashboard | No web UI | Browser UI at :7474 |
| Monitoring | `redis-cli` | Cypher queries + dashboard |
| Docker | Single image | Single image |
| Best for | Local dev, lightweight | Production, monitoring |

For AWS deployment, change `docker-compose.yml`:
```yaml
# Replace falkordb service with:
neo4j:
  image: neo4j:5.26
  ports:
    - "7474:7474"  # Browser UI
    - "7687:7687"  # Bolt protocol
  environment:
    - NEO4J_AUTH=neo4j/password
  volumes:
    - neo4j_data:/data
```

And update the connection string:
```python
graphiti = Graphiti("bolt://neo4j:7687", "neo4j", "password", llm_client=...)
```

## Tests

- [ ] `GraphitiService.initialize()` connects to FalkorDB
- [ ] `add_agent_memory()` creates nodes in the graph
- [ ] `search_agent_context()` returns relevant results
- [ ] `add_opinion_checkpoint()` records temporal facts
- [ ] `get_agent_opinion_history()` returns chronological results
- [ ] `cleanup()` closes connections cleanly
- [ ] Fallback to Zep Cloud works when `MEMORY_BACKEND=zep`
- [ ] Graph data persists across container restarts (Docker volume)
