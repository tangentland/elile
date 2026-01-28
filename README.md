# Elile

Autonomous research agent for comprehensive investigations and risk assessment.

## Overview

Elile is a multi-model AI agent that conducts thorough research on entities to uncover hidden connections, potential risks, and strategic insights. It uses LangGraph for orchestration and integrates with multiple AI providers (Anthropic Claude, OpenAI, Google Gemini).

## Features

- **Multi-Model Integration**: Seamlessly switch between AI providers
- **LangGraph Orchestration**: Sophisticated workflow management with conditional routing
- **Consecutive Search Strategy**: Intelligent search progression that builds on discoveries
- **Risk Assessment**: Automated risk scoring and categorization
- **Connection Mapping**: Entity relationship discovery and visualization

## Installation

### Requirements

- Python 3.14+
- API keys for at least one provider (Anthropic, OpenAI, or Google)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/elile-team/elile.git
   cd elile
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Usage

### Basic Usage

```python
from elile.agent.graph import research_graph
from elile.agent.state import AgentState

# Initialize state
initial_state: AgentState = {
    "messages": [],
    "target": "Entity Name",
    "search_queries": [],
    "search_results": [],
    "findings": [],
    "risk_findings": [],
    "connections": [],
    "search_depth": 0,
    "should_continue": True,
    "final_report": None,
}

# Run the research graph
result = await research_graph.ainvoke(initial_state)
print(result["final_report"])
```

### Using Model Adapters Directly

```python
from elile.models.registry import get_model
from elile.models.base import Message, MessageRole
from elile.config.settings import ModelProvider

# Get a model adapter
model = get_model(ModelProvider.ANTHROPIC)

# Generate a response
messages = [
    Message(role=MessageRole.USER, content="Hello!")
]
response = await model.generate(messages)
print(response.content)
```

## Development

### Code Formatting

```bash
black .
```

### Linting

```bash
ruff check .
```

### Type Checking

```bash
mypy src/elile
```

### Running Tests

```bash
pytest
```

### Running with Coverage

```bash
pytest --cov=elile --cov-report=html
```

## Project Structure

```
elile/
├── src/elile/
│   ├── agent/          # LangGraph workflow
│   ├── config/         # Configuration management
│   ├── models/         # Model adapters
│   ├── risk/           # Risk assessment
│   ├── search/         # Search system
│   └── utils/          # Utilities
├── tests/
│   ├── conftest.py     # Test fixtures
│   └── unit/           # Unit tests
├── pyproject.toml      # Project configuration
└── langgraph.json      # LangGraph deployment config
```

## Configuration

Configure Elile using environment variables or a `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `DEFAULT_MODEL_PROVIDER` | Default provider | `anthropic` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_SEARCH_DEPTH` | Maximum search iterations | `5` |

## License

MIT License
