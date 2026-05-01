# Deep Research Agent

A multi-agent AI research system built with LangGraph that autonomously searches the web, validates facts, and produces structured research reports with embedded chart visualizations.

## Architecture

The system uses a **supervisor-subagent** pattern:

- **Research Agent** — Orchestrates subagents and synthesizes the final research report from their outputs.
- **Data Collector** — Searches Google and scrapes webpages to gather factual information with source URLs.
- **Data Validator** — Cross-checks facts and confirms which sources are real and credible.
- **Data Visualizer** — Converts numerical, statistical, and comparative data into structured JSON for charts (bar, line, pie, area, scatter, table).

The Research Agent enforces a strict workflow: collect → validate → visualize → synthesize. No answer is written until all subagents have returned.

## Features

- Autonomous web search via SerpAPI
- Multi-source web scraping
- Fact and URL verification
- Automatic chart/visualization generation from numerical data
- Two operational modes: **Deep Research** (high reasoning effort, recursion=100) and **Quick Research** (low reasoning effort, recursion=10)
- Configurable call limits to prevent runaway agent loops
- Citation tracking with automatic reference numbering
- Structured JSON responses for chart rendering on frontends
- Langfuse observability and tracing
- Daily log rotation with configurable levels
- Graceful error handling per tool (agent continues on tool failure)

## Prerequisites

- **SerpAPI API Key** — Get one at [serpapi.com](https://serpapi.com)
- **Google Application Default Credentials** — JSON file for Google Generative AI (`application_default_credentials.json` in project root)
- **Python 3.10+**

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# SerpAPI (required)
SERPAPI_API_KEY=your_serpapi_key

# Google Cloud credentials (file path is auto-detected)
# CREDENTIALS_FILE = src/application_default_credentials.json  # auto-resolved

# Research modes (set DEEP_Research=1 for deep mode, 0 for quick mode)
DEEP_Research=0
DEEP_Research_Recursion_Limit=100
DEEP_Research_Reasoning_Effort=high
DEEP_Research_Tool_Call_Limit=20
DEEP_Research_Model_Call_Limit=20

QUICK_Research_Recursion_Limit=10
QUICK_Research_Reasoning_Effort=low
QUICK_Research_Tool_Call_Limit=3
QUICK_Research_Model_Call_Limit=5

# Langfuse tracing (optional)
LANGFUSE_SECRET_KEY=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_BASE_URL=
LANGFUSE_TRACING_ENVIRONMENT=development

# Logging
LOGGING_LEVEL=DEBUG

# PostgreSQL (optional, for persistent memory)
POSTGRES_Url=
```

## Usage

Start the API server:

```bash
flask --app src/api/app run
```

## API

### POST /research

**Request:**

```json
{
  "query": "What are the latest developments in quantum computing?"
}
```

**Response:**

```json
{
  "content": "## Overview\n...\n```json\n{\"chartType\": \"bar\", ...}\n```\n...",
  "references": {
    "IBM announces breakthrough in quantum error correction — https://ibm.com/quantum": 1,
    "Google Quantum AI progress report — https://quantumai.google/blog": 2
  }
}
```

The `content` field contains the full research report in Markdown. Chart JSON blocks are embedded inline within the text, wrapped in triple-backtick fences. Citation markers like `[[[Title — URL]]]` in the raw LLM output are automatically converted to numbered references `[1]`, `[2]`, etc., with the mapping returned in the `references` field.

## Project Structure

```
src/
  api/
    app.py                # Flask API with POST /research endpoint
  agents/
    research.py         # Main research agent factory and citation cleaner
    subagents.py        # Collector, validator, visualizer subagent factories
  config/
    llm_models.py       # Google Gemini model creation
    prompts.py         # All agent system prompts
    settings.py         # Pydantic settings from .env
    agent_configs.py    # Backend and error handling middleware
  models/
    response_model.py  # ResearchDocument schema
  tools/
    google_search_tool.py  # SerpAPI search tool
    web_scrape_tool.py    # Web scraping tool
    ddg_mcp.py            # DuckDuckGo MCP tools
  observability/
    logging.py            # Loguru daily log rotation
    langfuse_config.py     # Langfuse callback handler
```

## Dependencies

- `deepagents` — Agent framework built on LangGraph
- `langchain` / `langgraph` — Agent and graph orchestration
- `langchain-google-genai` — Gemini LLM integration
- `google-search-results` — SerpAPI client
- `langfuse` — Observability and tracing
- `flask[async]` — Async API server
- `flask-cors` — CORS support
- `loguru` — Structured logging
- `langgraph-checkpoint-postgres` — Postgres checkpointing
- `python-dotenv` — Environment variable loading
- `langchain-community` — Document loaders for web scraping
- `beautifulsoup4` — HTML parsing