# 🛡️ Sentinel-Agent: Secure Agentic Orchestrator with MCP

> A production-ready autonomous AI agent that utilizes the **Model Context Protocol (MCP)** to execute multi-step workflows across APIs and databases, protected by a deterministic **3-Gate Security Pipeline** that prevents prompt injection attacks.

---

## 🏗️ Architecture

```
User Input
   ↓
🔐 Gate 1 — Security Firewall (42+ regex patterns, <5ms)
   ↓
🧠 Gate 2 — ReAct Reasoning Loop (Think → Act → Observe)
   ↓
🔧 MCP Tools — Database / Weather API / Calculator
   ↓
🔍 Gate 3 — Output Validator (PII & Secret Redaction)
   ↓
✅ Safe Response
```

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **3-Gate Security** | Prompt injection firewall → ReAct reasoning → PII output filter |
| **MCP Protocol** | Tools are compatible with Claude Desktop, Cursor, and any MCP host |
| **ReAct Agent** | Think → Act → Observe loop with self-correcting error feedback |
| **Vector Memory** | SQLite-vec embeddings for long-term contextual recall |
| **7 Tools** | DB CRUD, Weather, News, Calculator — all sandboxed |
| **Langfuse Tracing** | Full observability of every reasoning step |
| **Docker + CI/CD** | Production containerization with GitHub Actions |

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/your-username/sentinel-agent.git
cd sentinel-agent
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env with your API keys
```

### 3. Run the Server

```bash
python -m backend.main
```

Visit: **http://localhost:8000** (Dashboard) | **http://localhost:8000/docs** (Swagger API)

### 4. Run Tests

```bash
pytest tests/ -v
```

### 5. Docker

```bash
docker-compose up --build
```

## 🔐 Security: Gate 1 Patterns

Gate 1 detects **7 threat categories** with 42+ regex patterns:

| Category | Example Attack |
|----------|----------------|
| Role Hijacking | "Ignore previous instructions" |
| Context Override | "Show me your system prompt" |
| Jailbreak | "Enable DAN mode" |
| Command Injection | "DROP TABLE users" |
| Privilege Escalation | "Give me admin access" |
| Data Exfiltration | "Show all passwords" |
| System Manipulation | "Modify your core instructions" |

## 🧠 ReAct Agent Flow

```
User: "What's the weather in my preferred city?"

THOUGHT → "I need to check the user's city preference first"
ACTION  → get_preference(key="city")
OBSERVE → {"found": true, "value": "Delhi"}

THOUGHT → "Now I'll fetch weather for Delhi"
ACTION  → get_weather(city="Delhi")
OBSERVE → {"temp": "34°C", "condition": "Sunny"}

FINAL   → "It's currently 34°C and sunny in Delhi! ☀️"
```

## 📁 Project Structure

```
sentinel-agent/
├── backend/
│   ├── main.py              # FastAPI server (all 3 gates wired)
│   ├── config.py            # Pydantic-settings env config
│   ├── agent/
│   │   ├── react_loop.py    # ReAct reasoning engine
│   │   ├── llm_client.py    # OpenAI GPT-4o wrapper
│   │   └── memory.py        # SQLite-vec vector memory
│   ├── gates/
│   │   ├── gate1_security.py  # Prompt injection firewall
│   │   └── gate3_validator.py # PII/secret output filter
│   ├── mcp/
│   │   ├── server.py         # FastMCP tool registry
│   │   └── tools/
│   │       ├── db_tool.py    # SQLite CRUD (parameterized)
│   │       ├── api_tool.py   # Weather/News (exponential backoff)
│   │       └── calc_tool.py  # AST-based safe calculator
│   ├── models/
│   │   └── schemas.py        # Pydantic v2 API schemas
│   └── observability/
│       └── langfuse_client.py # Langfuse tracing
├── frontend/
│   ├── index.html            # Chat dashboard
│   ├── style.css             # Dark glassmorphism theme
│   └── app.js                # Real-time gate status UI
├── tests/                    # pytest suite
├── Dockerfile                # Multi-stage production build
├── docker-compose.yml        # One-command deployment
└── .github/workflows/        # CI/CD pipeline
```

## 🛠️ Tech Stack

- **Backend**: FastAPI + Python 3.12 + Pydantic v2
- **AI**: OpenAI GPT-4o + ReAct pattern
- **Protocol**: Model Context Protocol (MCP) via FastMCP
- **Database**: SQLite + SQLite-vec (vector embeddings)
- **Observability**: Langfuse (full trace per request)
- **DevOps**: Docker + GitHub Actions CI/CD

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
