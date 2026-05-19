# Google ADK — Primitives Cheat Sheet

> **Version covered:** `google-adk 1.33.0` (Python, released May 8, 2026). The same primitives exist in `@google/adk` (TypeScript), `google.golang.org/adk` (Go), and `com.google.adk` (Java) — naming is consistent across all four SDKs.
>
> **Mental model:** ADK is to AI agents what a web framework is to HTTP. You don't reinvent request routing, middleware, sessions, or templating — you assemble them. ADK gives you that same skeleton, but for agents: a worker (Agent), things it can do (Tools), a memory of the chat (Session), middleware hooks (Callbacks), and an engine that runs the whole thing (Runner). Everything else is variations on those five.

---

## The Big Picture (read this first)

Picture a call center. A customer dials in. There's a **worker** taking the call (Agent). The worker has access to internal **systems** — CRM, billing, knowledge base (Tools). The worker scribbles notes during the call on a sticky pad (State). The whole transcript of the call is filed away (Session). Quality assurance listens in and flags issues (Callbacks). The worker can pull up the customer's history from past calls (Memory). The worker can attach a PDF to the case file (Artifacts). And there's a manager routing calls between specialist workers (Multi-Agent / Workflow Agents). The phone system itself — connecting everyone, recording events, switching lines — is the Runner.

That's it. Everything below is one of those pieces.

---

## 1. `LlmAgent` (a.k.a. `Agent`) — The Worker

**What it is:** An LLM-powered worker. Give it a name, a model, an instruction (system prompt), and tools. It reasons and decides what to do.

```python
from google.adk.agents import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="weather_assistant",
    model="gemini-2.5-flash",
    description="Answers weather questions.",  # used by other agents to decide whether to delegate
    instruction="You help users check the weather. Use tools when needed.",
    tools=[google_search],
)
```

**When to use:** The default. Any time you need natural-language understanding, reasoning, or dynamic decision-making. 95% of agents you build start here.

**Use cases:** Chatbots, research assistants, support agents, code assistants, anything that needs to "think."

**Gotcha:** `description` matters in multi-agent setups — other agents read it to decide whether to hand off work. Write it like a job posting, not a comment.

---

## 2. `FunctionTool` — Giving the Agent Hands

**What it is:** Any Python function becomes a tool the LLM can call. ADK auto-generates the schema from the type hints and docstring.

```python
def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city: The name of the city.
    Returns:
        dict: status and result or error message.
    """
    if city.lower() == "colombo":
        return {"status": "success", "report": "Hot and humid, 31°C."}
    return {"status": "error", "error_message": f"No data for {city}."}

agent = Agent(
    name="weather_agent",
    model="gemini-2.5-flash",
    instruction="Help users check the weather.",
    tools=[get_weather],   # just pass the function
)
```

**When to use:** Whenever the agent needs to *do* something the LLM alone can't — call an API, query a DB, do math, hit a microservice.

**Use cases:** CRM lookups, DB queries, sending email, hitting your own internal APIs, anything stateful or side-effecting.

**Gotcha:** The docstring **is** the prompt. The LLM reads it to decide when to call the tool. Vague docstring = wrong calls. Return a `dict` with a clear `status` field so the LLM can recover from errors.

---

## 3. Workflow Agents — Deterministic Orchestration

These are agents that **don't use an LLM to decide flow**. They run sub-agents in a fixed pattern. Think of them as pipelines.

### 3a. `SequentialAgent` — Step by step

```python
from google.adk.agents import SequentialAgent

pipeline = SequentialAgent(
    name="research_pipeline",
    sub_agents=[researcher_agent, summarizer_agent, formatter_agent],
)
```
**When to use:** Output of step N feeds step N+1. ETL, multi-stage research, "draft → review → polish" flows.

### 3b. `ParallelAgent` — Fan-out

```python
from google.adk.agents import ParallelAgent

researchers = ParallelAgent(
    name="multi_source_research",
    sub_agents=[arxiv_agent, web_agent, wikipedia_agent],
)
```
**When to use:** Independent sub-tasks. Saves wall-clock time. Each sub-agent runs concurrently; results are gathered.

### 3c. `LoopAgent` — Iterate until done

```python
from google.adk.agents import LoopAgent

refine_loop = LoopAgent(
    name="iterative_refiner",
    sub_agents=[draft_agent, critic_agent],
    max_iterations=5,
)
```
**When to use:** "Critique-then-improve" patterns, retry-until-pass, agentic self-correction.

**Big idea:** Workflow agents are cheaper, faster, and more predictable than letting an LLM orchestrate. Use them whenever the *control flow* is known in advance — even if the *content* at each step is still LLM-driven.

---

## 4. Multi-Agent Systems — Specialist Teams

**What it is:** A root agent with sub-agents. The LLM can either **delegate** (transfer control) or **invoke as a tool** (call and get the answer back).

```python
greeter = Agent(name="greeter", model="gemini-2.5-flash",
                instruction="Greet users warmly.",
                description="Handles greetings and small talk.")

booker = Agent(name="booker", model="gemini-2.5-flash",
               instruction="Book appointments.",
               description="Handles all appointment booking.")

coordinator = Agent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction="Route the user to the right specialist.",
    sub_agents=[greeter, booker],     # delegation: child takes over
    # or: tools=[AgentTool(booker)]   # tool-style: call & return
)
```

**When to use:** When one agent's instruction would become an unreadable monster. Split by *responsibility*, not by *file size*.

**Use cases:** Customer support triage (billing/tech/sales), research orchestrator with domain specialists, mafia village simulation where each villager is an agent.

**Rule of thumb:** `sub_agents` = control transfer (the conversation moves to them). `AgentTool` = function call (you call them, they answer, you continue).

---

## 5. `Session` & `State` — Short-term Memory

**What it is:** A `Session` is one conversation. Inside it, `State` is a dict the agent and tools can read/write — the sticky note pad for that call.

```python
# Inside a tool function:
def remember_preference(preference: str, tool_context) -> dict:
    tool_context.state["favorite_color"] = preference
    return {"status": "saved"}

# State keys with prefixes have special scopes:
# state["key"]            → session-scoped
# state["user:key"]       → persisted across sessions for this user
# state["app:key"]        → app-wide
# state["temp:key"]       → only this turn
```

**When to use:** Anything the agent needs to remember **within the current conversation** — collected slots in a form, intermediate results between sub-agents, user choices.

**Use cases:** Order-taking flows, multi-turn data collection, passing data between sub-agents in a Sequential pipeline (Step 1 writes to state, Step 2 reads it).

**Gotcha:** State is *not* the same as Memory. Close the chat and session-scoped state is gone unless persisted by your `SessionService`.

---

## 6. `Memory` — Long-term Recall

**What it is:** A separate service for "what does the agent remember about this user *across sessions*." Backed by `InMemoryMemoryService` for dev, `VertexAiMemoryBankService` for production.

```python
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import load_memory  # built-in tool

memory_service = InMemoryMemoryService()

agent = Agent(
    name="personal_assistant",
    model="gemini-2.5-flash",
    instruction="Use load_memory to recall past info about the user.",
    tools=[load_memory],
)
```

**When to use:** Personal assistants, support agents that should remember the customer, anything where "I told you last week..." should work.

**Use cases:** Personalized recommendations, ongoing therapy/coaching bots, CRM agents, your VedicAstro.me–style apps that need to remember chart details across sessions.

**Distinction:** `State` = sticky note. `Memory` = the filing cabinet.

---

## 7. `Callbacks` — Middleware Hooks

**What it is:** Functions that run at specific lifecycle points: before/after the agent runs, before/after the model is called, before/after a tool fires. Think Express middleware or Django signals.

```python
def block_pii(callback_context, llm_request):
    """Run before each model call — scrub or block PII."""
    text = llm_request.contents[-1].parts[0].text
    if "ssn" in text.lower():
        return  # short-circuit: return an LlmResponse to override
    return None  # None = proceed normally

agent = Agent(
    name="safe_agent",
    model="gemini-2.5-flash",
    instruction="Help the user.",
    before_model_callback=block_pii,
    # other hooks: before_agent_callback, after_agent_callback,
    # after_model_callback, before_tool_callback, after_tool_callback
)
```

**When to use:** Guardrails, logging, caching, rate limits, audit trails, redaction, observability — anything that needs to run *around* the agent, not *inside* it.

**Use cases:** Block prompt injection attempts, log all tool calls to BigQuery, cache identical LLM requests, enforce per-user rate limits, redact PII before it hits the model.

---

## 8. `Runner` — The Engine

**What it is:** The thing that actually executes your agent. You rarely write this from scratch — `adk web`, `adk run`, and `adk api_server` give you Runners for free. But for production embedding, you wire it yourself.

```python
from google.adk.runners import InMemoryRunner

runner = InMemoryRunner(agent=root_agent, app_name="my_app")
session = await runner.session_service.create_session(
    app_name="my_app", user_id="ashan"
)

from google.genai import types
user_msg = types.Content(role="user", parts=[types.Part(text="Hi!")])

async for event in runner.run_async(
    user_id="ashan", session_id=session.id, new_message=user_msg
):
    if event.is_final_response():
        print(event.content.parts[0].text)
```

**When to use:** When you embed an agent inside another app (FastAPI route, background job, Cloud Run service) instead of the dev UI.

**Use cases:** Production deployments, custom backends, batch processing of agent tasks, integrating with Trigger.dev / Cloudflare Workflows–style orchestrators.

---

## 9. `Event` — The Currency of the Runtime

**What it is:** Every "thing that happened" — a user message, an agent response, a tool call, a tool result, a state delta. Sessions are just ordered lists of events. The Runner yields events as a stream.

```python
async for event in runner.run_async(...):
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.text:
                print("TEXT:", part.text)
            if part.function_call:
                print("TOOL CALL:", part.function_call.name)
            if part.function_response:
                print("TOOL RESULT:", part.function_response.response)
    if event.actions and event.actions.state_delta:
        print("STATE CHANGED:", event.actions.state_delta)
```

**When to use:** Streaming UIs, custom logging, observability, debugging "why did the agent do that."

**Use cases:** Streaming token output to a web client, building a custom dev UI, real-time agent dashboards, replaying conversations.

---

## 10. `Artifacts` — Files & Binary Data

**What it is:** A way for agents to save and load files (images, PDFs, generated reports) tied to a session or user, with versioning. Don't stuff binary blobs into State — that's what Artifacts are for.

```python
# Inside a tool:
async def save_chart(data: dict, tool_context) -> dict:
    import io, matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(data["x"], data["y"])
    buf = io.BytesIO()
    plt.savefig(buf, format="png")

    from google.genai import types
    artifact = types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")
    version = await tool_context.save_artifact("chart.png", artifact)
    return {"status": "saved", "version": version}
```

**When to use:** Any time the agent produces or consumes a file — generated images, uploaded PDFs, exported CSVs.

**Use cases:** Image generation agents, document processing pipelines, report builders, OCR flows.

---

## 11. Built-in Tools — Batteries Included

ADK ships ready-made tools you import and pass straight into `tools=[...]`.

| Tool | What it does |
|---|---|
| `google_search` | Grounded web search via Gemini |
| `vertex_ai_search` | Grounded search over your Vertex AI datastores (RAG) |
| `built_in_code_execution` | Run Python in a sandbox |
| `load_memory` | Retrieve from the Memory service |
| `load_artifacts` | Pull saved artifacts into context |
| `transfer_to_agent` | Hand off to a sub-agent (auto-added in multi-agent) |
| `AgentTool(other_agent)` | Call another agent as if it were a function |
| `LongRunningFunctionTool` | Async/human-in-the-loop tools that pause and resume |

```python
from google.adk.tools import google_search, built_in_code_execution
from google.adk.tools.agent_tool import AgentTool

agent = Agent(
    name="researcher",
    model="gemini-2.5-flash",
    tools=[google_search, built_in_code_execution, AgentTool(specialist)],
)
```

**When to use:** Always check the built-in tools list before writing your own. `google_search` alone replaces a custom Bing/Serper integration.

---

## 12. MCP Tools — The Universal Adapter

**What it is:** Connect to any MCP (Model Context Protocol) server — Asana, Notion, GitHub, Slack, your own — and expose its tools to the agent.

```python
from google.adk.tools.mcp_tool import MCPToolset
from mcp import StdioServerParameters

toolset = MCPToolset(
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    ),
)

agent = Agent(
    name="file_agent",
    model="gemini-2.5-flash",
    instruction="Help the user work with their files.",
    tools=[toolset],
)
```

**When to use:** When a service already has an MCP server, use it instead of writing a `FunctionTool` from scratch.

**Use cases:** Anything in the MCP ecosystem — and that ecosystem is growing fast. Devin AI integration, IDE tools, third-party SaaS.

---

## 13. OpenAPI Tools — Auto-generate from Swagger

**What it is:** Point it at an OpenAPI/Swagger spec; ADK auto-generates one tool per endpoint.

```python
from google.adk.tools.openapi_tool import OpenAPIToolset

toolset = OpenAPIToolset(
    spec_str=open("petstore.yaml").read(),
    spec_str_type="yaml",
)

agent = Agent(name="pet_agent", model="gemini-2.5-flash", tools=[toolset])
```

**When to use:** Wrapping an existing REST API. Way faster than writing 30 `FunctionTool`s by hand.

**Use cases:** Internal microservices, third-party APIs with good OpenAPI specs (Stripe, GitHub, etc.).

---

## 14. `A2A` (Agent-to-Agent Protocol) — Remote Agents

**What it is:** A protocol for one agent (possibly running on a different server, in a different language, by a different team) to call another. Local multi-agent is in-process; A2A is over the network.

```python
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

remote = RemoteA2aAgent(
    name="finance_specialist",
    description="External finance agent",
    agent_card="https://finance.example.com/.well-known/agent.json",
)

coordinator = Agent(
    name="coordinator",
    model="gemini-2.5-flash",
    sub_agents=[remote],
)
```

**When to use:** Decoupled microservice-style agents, cross-team agent composition, exposing your agent for others to consume.

**Use cases:** Enterprise agent meshes, third-party agent marketplaces, splitting a monolithic agent app across teams.

---

## 15. `Plugins` — Cross-Cutting Behaviors

**What it is:** Pre-packaged bundles of callbacks + tools + setup, applied across the whole app rather than per-agent. Logging, tracing, safety filters, BigQuery exporters all ship as plugins.

```python
from google.adk.apps import App
from google.adk.plugins import LoggingPlugin

app = App(
    name="my_app",
    root_agent=root_agent,
    plugins=[LoggingPlugin()],
)
```

**When to use:** When the same behavior must apply to every agent in your app (observability, audit, safety).

---

## 16. Evaluation — Don't Ship Vibes

**What it is:** Built-in tooling to define eval sets (`.evalset.json`) and run them via CLI or the dev UI. Measures trajectory match, response quality, custom metrics.

```bash
adk eval samples_for_testing/hello_world \
         samples_for_testing/hello_world/hello_world_eval_set_001.evalset.json
```

**When to use:** Before every prompt change, before every deploy. Treat agents like software: regression tests, not vibes.

**Use cases:** CI/CD for agents, A/B testing prompts, comparing model versions (Flash vs Pro), measuring tool-call accuracy.

---

## 17. Deployment — Where Agents Live

| Target | Command / Class | When |
|---|---|---|
| **Local dev UI** | `adk web` | While building |
| **Local CLI** | `adk run <agent>` | Quick terminal tests |
| **Local API server** | `adk api_server` | Test cURL/HTTP before deploy |
| **Agent Engine (Vertex)** | `adk deploy agent_engine` | Managed runtime, sessions, memory bank |
| **Cloud Run** | `adk deploy cloud_run` | Container, scales to zero |
| **GKE** | `adk deploy gke` | Custom infra, big enterprise |

**Rule of thumb:** Start with Agent Engine unless you have a specific reason not to — it gives you managed sessions, memory, tracing, and IAM for free.

---

## The 80% Workflow (in 8 lines)

```python
from google.adk.agents import Agent, SequentialAgent
from google.adk.tools import google_search

def my_tool(x: str) -> dict:
    """Does the thing. Args: x: input. Returns: dict with status."""
    return {"status": "ok", "result": x.upper()}

specialist = Agent(name="spec", model="gemini-2.5-flash",
                   instruction="Do X.", tools=[my_tool])
root_agent = Agent(name="root", model="gemini-2.5-flash",
                   instruction="Coordinate.", sub_agents=[specialist],
                   tools=[google_search])
```

Run with `adk web`. That's 80% of what you'll do. Everything else — callbacks, memory, artifacts, A2A, plugins — is what you reach for when the 80% stops being enough.

---

## Quick Mental Map

```
                ┌─────────────────────────────────┐
                │           Runner                 │  ← executes everything
                │  (yields Events as they happen)  │
                └────────────┬────────────────────┘
                             │
            ┌────────────────▼────────────────┐
            │           Root Agent             │  ← LlmAgent / Workflow / Custom
            │  ┌─────────┐  ┌─────────┐        │
            │  │ Sub-Agt │  │ Sub-Agt │  ...   │  ← multi-agent / sub_agents
            │  └─────────┘  └─────────┘        │
            │      │             │             │
            │  ┌───▼───┐    ┌────▼────┐        │
            │  │ Tools │    │  Tools  │        │  ← FunctionTool, MCP, OpenAPI, AgentTool
            │  └───────┘    └─────────┘        │
            └──┬───────────────────┬───────────┘
               │                   │
        ┌──────▼──────┐    ┌───────▼────────┐
        │  Callbacks   │    │   Plugins      │  ← middleware (per-agent / app-wide)
        └──────────────┘    └────────────────┘
               │
   ┌───────────▼──────────────────────────┐
   │  Session (Events + State)             │  ← short-term, this conversation
   │  Memory (across sessions)             │  ← long-term, per user
   │  Artifacts (files, binary data)       │  ← versioned blobs
   └───────────────────────────────────────┘
```

---

## Install & Get Started

```bash
pip install google-adk        # latest: 1.33.0 (May 2026)
# or
npm install @google/adk
# or
go get google.golang.org/adk
```

Then drop the 8-line example above into `agent.py`, set `GOOGLE_API_KEY` in `.env`, and run `adk web`.

**Docs:** https://google.github.io/adk-docs/
**LLM-friendly docs (for Cursor/Devin/Claude Code):** https://google.github.io/adk-docs/llms-full.txt
