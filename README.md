# Agents in Cahoots

A robust multi-agent simulation system with state machine orchestration, hierarchical memory, and advanced coordination features.

## Features

### 1. Architectural Robustness
- **State Machine Orchestrator**: Prevents infinite loops with structured state transitions (IDLE → THINKING → EXECUTING → IDLE)
- **Structured Output Enforcement**: Pydantic models ensure agents return valid JSON schemas
- **Circuit Breaker**: Token & cost monitoring that halts execution when limits are exceeded

### 2. Enhanced Memory & Context
- **Hierarchical Memory**: Short-term (current task) + Long-term (vector store) memory with semantic retrieval
- **Shared Blackboard**: Team workspace where agents can post and read information
- **Vector Store**: TF-IDF based embeddings for semantic memory search

### 3. Advanced Coordination
- **Secret Channels**: Private messaging system for game-theory scenarios (The Traitors, Werewolf)
- **Role-Based Access Control (RBAC)**: Different tool permissions per role (Mayor, Merchant, Hermit, Guard, Spy)

### 4. Developer Experience
- **Human-in-the-Loop (HITL)**: Approve/reject/modify agent actions before execution
- **Tracing**: LangSmith and Phoenix integration for debugging
- **Mock Environment**: Test without burning LLM credits

### 5. Deployment & UI
- **Async Processing**: Concurrent agent execution with asyncio
- **Docker Support**: Dockerfile and docker-compose.yml included
- **Streamlit Dashboard**: Real-time visualization of agent simulation

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Initialize the database
python setup_database.py

# Run the simulation
python run_simulation.py -n 10

# Or use the dashboard
streamlit run streamlit_dashboard.py
```

## Configuration

Set environment variables:

```bash
export OPENAI_API_KEY=your_api_key
export LLM_MODEL=gpt-3.5-turbo
export SIMULATION_TICKS=10
export MOCK_MODE=true  # Test without API key
```

## Architecture

```
agents-in-cahoots/
├── orchestrator/          # State machine & circuit breaker
│   ├── models.py         # Pydantic models
│   ├── state_machine.py  # Agent state management
│   └── circuit_breaker.py
├── memory/               # Hierarchical memory
│   └── hierarchical.py
├── collaboration/        # Agent communication
│   ├── blackboard.py    # Shared workspace
│   └── secret_channels.py
├── security/             # Access control
│   └── rbac.py
├── tracing/              # Debugging
│   └── tracer.py
├── testing/              # Testing utilities
│   └── mock_environment.py
├── hitl/                 # Human oversight
│   └── interface.py
├── async_/               # Async processing
│   └── processor.py
├── tests/                # Test suite
└── streamlit_dashboard.py
```

## Testing

```bash
pytest tests/ -v
```

## Docker

```bash
docker-compose up --build
```

## License

MIT
