# ⚽ Football Multi-Agent Analysis System — Week 2

> **A configuration-driven multi-agent framework** that delivers three independent AI analyst perspectives on any football match — powered by structured match data, expert opinion synthesis, and real-time internet search.

---

## 🏗️ System Architecture

```text
                         ┌──────────────────────────────┐
                         │         User Query           │
                         │  "Mexico vs South Africa"    │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │       MatchResolver          │
                         │  fuzzy token matching →      │
                         │  game_id: 1953853            │
                         └──────────────┬───────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
        ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
        │  📊 Summary     │ │  🗣️ Opinion     │ │  🌐 Web Search  │
        │    Analyst      │ │    Analyst      │ │    Analyst      │
        └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                 │                   │                   │
                 ▼                   ▼                   ▼
        ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
        │ get_match_      │ │ get_match_      │ │  web_search()   │
        │ summary()       │ │ opinions()      │ │  Tavily API     │
        │ Local JSON      │ │ Local JSON      │ │  Real-time      │
        └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                 │                   │                   │
                 └───────────────────┴───────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │     OpenRouter LLM Client    │
                         │   openai/gpt-4o-mini         │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │  3 × AgentResponse objects   │
                         │  (ready for Week 3 debate)   │
                         └──────────────────────────────┘
```

### Why a Custom Framework Instead of LangChain?

| Concern | Our Approach |
|---|---|
| **Transparency** | Full visibility into every prompt: `Persona + Memory + Evidence + Query` |
| **Persona flexibility** | Adding a new agent = creating one YAML file, zero Python changes |
| **Testability** | LLM and tools are injected dependencies — trivially mockable in tests |
| **Week 3 readiness** | `AgentResponse` is a stable, typed handoff object for the debate engine |

---

## 👤 Persona System

Each agent is defined entirely in a YAML file. The same `BaseAgent` class powers all three — the persona config drives the behavior, tool selection, and communication style.

| Persona | Role | Evidence Source | Input Mode |
|---|---|---|---|
| `match_summary_analyst` | Quantitative data analyst — VAEP, xT, stats | `data/matchs summary.json` | `game_id` |
| `match_opinion_analyst` | Studio commentary synthesizer | `data/opinion.json` | `game_id` |
| `web_search_analyst` | Real-time news & media scout | Tavily Internet Search | search query |

**A persona YAML defines:**
```yaml
id:                   # unique identifier used in memory session keys
name:                 # display name
role:                 # one-line job title fed into the prompt
background:           # domain expertise paragraph
stance:               # analytical philosophy and epistemic rules
communication_style:  # tone and format instructions
expertise:            # list of focus areas
priorities:           # ordered list of what the agent emphasises first
required_tool:        # which tool this agent calls automatically
input_mode:           # match_specific | search_query
```

---

## 🛠️ Tools Layer

All tools implement a unified contract and are dispatched through `ToolRegistry`.

```python
result = registry.execute("get_match_summary", game_id=1953853)

# Every tool returns a ToolResult:
ToolResult(
    success=True,
    tool_name="get_match_summary",
    data={ ... },           # evidence passed directly into the LLM prompt
    metadata={"sources": [...]},
)
```

| Tool | File | Data Source | Notes |
|---|---|---|---|
| `get_match_summary` | `match_summary_tool.py` | `data/matchs summary.json` | VAEP, xT, scoreline, MVP, key actions |
| `get_match_opinions` | `match_opinion_tool.py` | `data/opinion.json` | 4 expert studio opinions per match |
| `web_search` | `web_search_tool.py` | Tavily Search API | `max_results=3`, returns answer + sources |

> **Implementation note:** `data/opinion.json` is stored as 72 concatenated JSON objects (not a proper array). `match_opinion_tool.py` detects and normalises this automatically before parsing.

---

## 🔍 Match Resolver

The `MatchResolver` converts a natural-language query into a `game_id` using fuzzy token matching against the match index.

```python
resolver = MatchResolver()

resolver.resolve("Mexico South Africa")   # → game_id 1953853
resolver.resolve("Brazil")               # → all Brazil matches
resolver.resolve("1953853")              # → exact game_id lookup
```

If multiple matches are found, the orchestrator lists them and asks the user to choose. Common noise words (`vs`, `versus`, `match`, `game`, `ضد`) are stripped before matching.

---

## 💾 Memory Architecture

`JsonMemoryStore` provides persistent, session-isolated conversation history written to disk.

```
data/memory/
  match_summary_analyst__1953853__main_1953853.json
  match_opinion_analyst__1953853__main_1953853.json
  web_search_analyst__general__main_1953853.json
```

**Session key format:**
```
{persona_id}__{game_id}__{conversation_id}
```

Each stored entry:
```json
{
  "role": "user | assistant | tool | system",
  "content": "...",
  "timestamp": "2026-09-04T01:30:00+00:00",
  "metadata": {}
}
```

**Key design properties:**
- **Session isolation** — persona, match, and conversation are all part of the key; no context leakage between agents or matches
- **Persistence** — survives application restarts; Week 3's debate engine can resume from where Week 2 left off
- **Sliding window** — only the last 10 messages enter the prompt (cost and latency control)

---

## 🤖 LLM Client — OpenRouter

`OpenRouterClient` calls [OpenRouter](https://openrouter.ai) using the OpenAI-compatible SDK.

```python
client = OpenRouterClient()        # reads OPENROUTER_API_KEY from .env
opinion = client.generate(prompt)  # → str
```

**Default model:** `openai/gpt-4o-mini`
Swap to any OpenRouter model by setting `OPENROUTER_MODEL=anthropic/claude-3.5-haiku` in `.env`.

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone <repo-url>
cd Intelligent-Agent-Framework-tools
pip install -r requirements.txt
```

### 2. Set API Keys

```bash
cp .env.example .env
# Edit .env and fill in:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   TAVILY_API_KEY=tvly-...
```

### 3. Run

```bash
# By team name (fuzzy match)
python main.py "Mexico South Africa"

# By game ID
python main.py 1953853

# Interactive mode (prompted for input)
python main.py
```

### Example Output

```
========================================================================
  ⚽  FOOTBALL MULTI-AGENT ANALYSIS SYSTEM
========================================================================
  Match   : 2026-06-11 Mexico-South Africa
  Teams   : Mexico  vs  South Africa
  Stage   : World Cup Grp. A
  Score   : 2 - 0
  Game ID : 1953853
========================================================================

  🤖  Running 3 agents ...

  ⏳  📊 Running Match Summary Analyst ...
  ✅  Match Summary Analyst done.
  ⏳  🗣️ Running Match Opinion Analyst ...
  ✅  Match Opinion Analyst done.
  ⏳  🌐 Running Web Search Analyst ...
  ✅  Web Search Analyst done.

------------------------------------------------------------------------
  📊  AGENT: MATCH SUMMARY ANALYST
  Tool used  : get_match_summary
------------------------------------------------------------------------

  Mexico delivered a dominant 2-0 win, with a VAEP of 2.04 versus
  South Africa's 0.27. Raúl Jiménez was named MVP ...

------------------------------------------------------------------------
  🗣️  AGENT: MATCH OPINION ANALYST
  Tool used  : get_match_opinions
------------------------------------------------------------------------

  Analysts largely agree on Mexico's tactical superiority ...

------------------------------------------------------------------------
  🌐  AGENT: WEB SEARCH ANALYST
  Tool used  : web_search
------------------------------------------------------------------------

  ESPN described the result as "a statement win for El Tri" ...

  📎 Sources:
     • Mexico 2-0 South Africa — ESPN
       https://www.espn.com/soccer/...

========================================================================
  ✅  All agents completed their initial opinions.
  🔜  Next week: agents will debate each other.
========================================================================
```

---

## 📁 Project Structure

```
├── data/
│   ├── matchs summary.json      # Structured match stats (72 matches)
│   ├── opinion.json             # 4 expert opinions per match (72 matches)
│   └── memory/                  # Auto-created — persistent agent memory
│
├── personas/
│   ├── match_summary_analyst.yaml
│   ├── match_opinion_analyst.yaml
│   └── web_search_analyst.yaml
│
├── src/
│   ├── agents/
│   │   ├── base_agent.py        # Core agent loop (tool call → prompt → LLM → memory)
│   │   └── factory.py           # create_agent() — loads persona + wires dependencies
│   │
│   ├── llm/
│   │   └── openrouter_client.py # OpenRouter via openai SDK (gpt-4o-mini default)
│   │
│   ├── memory/
│   │   ├── base.py              # MemoryStore abstract interface
│   │   └── json_memory.py       # JsonMemoryStore — disk-backed sliding window
│   │
│   ├── models/
│   │   ├── persona.py           # Persona dataclass + load_persona()
│   │   └── responses.py         # ToolResult, AgentResponse (Week 3 handoff types)
│   │
│   └── tools/
│       ├── match_resolver.py    # Fuzzy match query → game_id
│       ├── match_summary_tool.py
│       ├── match_opinion_tool.py
│       ├── web_search_tool.py   # Tavily API
│       └── registry.py          # ToolRegistry — dispatch by name
│
├── main.py                      # Orchestrator — resolve → run 3 agents → print
├── .env.example                 # API key template
└── requirements.txt
```




