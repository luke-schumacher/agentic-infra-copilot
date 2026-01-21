# Agentic Infra Co-Pilot

A Multi-Agent System (MAS) for infrastructure fault diagnosis, powered by RAG and Neuro-Symbolic AI.

## Project Overview

**Agentic Infra Co-Pilot** is a distributed **Multi-Agent System (MAS)** designed to autonomously diagnose complex infrastructure faults. It mimics a specialized human team by orchestrating distinct AI agents that collaborate to analyze data from three distinct domains:

1. **Telekom Minister (Governance)**: Enforces SLAs and interprets Network Intent (PDFs).
2. **Siemens Technician (Hardware)**: Diagnoses physical equipment faults using technical manuals (CSV/PDFs).
3. **Illigo Operator (Telemetry)**: Monitors live event logs and detects anomalies (JSON).

The system leverages **Retrieval-Augmented Generation (RAG)** and **Knowledge Graph technology (Neo4j)** to provide intelligent, grounded fault diagnosis and resolution recommendations.

## Key Features

- **Multi-Agent Architecture**: Three specialized agents (Governance, Hardware, Telemetry) working in concert.
- **Tripartite Data Ingestion**: Custom parsers for PDF, CSV, and JSON formats.
- **Neuro-Symbolic Reasoning**: Combines Knowledge Graphs (Neo4j) with Large Language Models.
- **Retrieval Capabilities**: LangChain-powered retrieval for grounded answers.
- **Chain of Thought**: Step-by-step reasoning for complex diagnoses.
- **Simulation Framework**: "Jan 2026 Grid-Lock" scenario testing.
- **Mean Time to Innocence (MTTI)**: Performance measurement and evaluation.

## Project Structure

```
agentic-infra-copilot/
├── data/                           # Data directories
│   ├── raw/                        # Raw data from three domains
│   │   ├── telekom/                # Telekom PDF intent docs
│   │   ├── siemens/                # Siemens CSV hardware scans
│   │   └── illigo/                 # Illigo JSON event logs
│   └── processed/                  # Processed and cleaned data
│       ├── telekom/
│       ├── siemens/
│       └── illigo/
│
├── src/                            # Source code
│   ├── ingestion/                  # Data ingestion modules
│   │   ├── pdf_parser.py           # Telekom PDF parser
│   │   ├── csv_parser.py           # Siemens CSV parser
│   │   └── json_parser.py          # Illigo JSON parser
│   │
│   ├── preprocessing/              # Data preprocessing
│   │   ├── telekom_preprocessor.py # Telekom data cleaning
│   │   ├── siemens_preprocessor.py # Siemens data cleaning
│   │   └── illigo_preprocessor.py  # Illigo event processing
│   │
│   ├── graph/                      # Knowledge Graph
│   │   ├── neo4j_connector.py      # Neo4j database connector
│   │   └── graph_builder.py        # Graph construction logic
│   │
│   ├── retrieval/                  # RAG retrieval
│   │   ├── vector_store.py         # Vector database manager
│   │   └── embeddings.py           # Embedding generation
│   │
│   ├── agent/                      # LangChain agent
│   │   ├── reasoning_engine.py     # Main reasoning logic
│   │   └── chain_of_thought.py     # CoT reasoning implementation
│   │
│   └── simulation/                 # Simulation scenarios
│       └── jan_2026_gridlock.py    # Grid-Lock scenario
│
├── notebooks/                      # Jupyter notebooks
│   ├── 01_eda_telekom.ipynb        # Telekom data EDA
│   ├── 02_eda_siemens.ipynb        # Siemens data EDA
│   ├── 03_eda_illigo.ipynb         # Illigo data EDA
│   └── 04_prototype_rag.ipynb      # Retrieval mechanism prototyping
│
├── config/                         # Configuration files
│   ├── .env.example                # Environment variables template
│   └── config.yaml                 # Application configuration
│
├── tests/                          # Test suite
│   └── test_ingestion.py           # Ingestion tests
│
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
└── README.md                       # This file
```

## Installation

### Prerequisites

- Python 3.9 or higher
- Neo4j database (local or cloud)
- OpenAI API key (or local LLM setup)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd agentic-infra-copilot
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   # Copy the example .env file
   cp config/.env.example config/.env

   # Edit config/.env and add your credentials
   # - OPENAI_API_KEY
   # - NEO4J_URI
   # - NEO4J_USERNAME
   # - NEO4J_PASSWORD
   ```

5. **Setup Neo4j**
   - Install Neo4j Desktop or use Neo4j Aura (cloud)
   - Create a new database
   - Update connection details in `config/.env`

6. **Verify installation**
   ```bash
   python -c "import langchain, neo4j, chromadb; print('All imports successful!')"
   ```

## Usage

### 1. Data Ingestion

Place your raw data files in the appropriate directories:
- `data/raw/telekom/` - PDF files
- `data/raw/siemens/` - CSV files
- `data/raw/illigo/` - JSON files

```python
from src.ingestion.pdf_parser import TelekomPDFParser
from src.ingestion.csv_parser import SiemensCSVParser
from src.ingestion.json_parser import IlligoJSONParser

# Parse data
telekom_parser = TelekomPDFParser()
telekom_data = telekom_parser.parse_all()

siemens_parser = SiemensCSVParser()
siemens_data = siemens_parser.parse_all()

illigo_parser = IlligoJSONParser()
illigo_data = illigo_parser.parse_all()
```

### 2. Build Knowledge Graph

```python
from src.graph.neo4j_connector import Neo4jConnector
from src.graph.graph_builder import GraphBuilder

with Neo4jConnector() as connector:
    builder = GraphBuilder(connector)
    builder.build_graph(telekom_data, siemens_data, illigo_data)
```

### 3. Run Diagnostic Query

```python
from src.agent.reasoning_engine import ReasoningEngine

engine = ReasoningEngine()
result = engine.diagnose_fault("Device shows error code E3401")
print(result)
```

### 4. Run Simulation

```python
from src.simulation.jan_2026_gridlock import GridLockSimulation

simulation = GridLockSimulation(reasoning_engine, graph_connector, vector_store)
results = simulation.run_simulation()
simulation.save_results("results/gridlock_results.json")
```

## Key Components Explained

### Data Ingestion (`src/ingestion/`)

- **pdf_parser.py**: Extracts text and metadata from Telekom PDF documentation
- **csv_parser.py**: Processes 500+ Siemens hardware scan CSV files
- **json_parser.py**: Parses and validates Illigo OCPP 2.0.1 event logs

### Preprocessing (`src/preprocessing/`)

- Cleans and normalizes data from each domain
- Extracts entities (devices, errors, procedures)
- Detects anomalies in hardware scans
- Identifies temporal event patterns

### Knowledge Graph (`src/graph/`)

- **neo4j_connector.py**: Manages Neo4j database connections
- **graph_builder.py**: Constructs the infrastructure knowledge graph
  - Node types: Device, Error, Procedure, Event, Hardware
  - Relationships: CAUSES, RESOLVES, OCCURS_IN, DETECTED_BY, FOLLOWS

### Knowledge Retrieval (`src/retrieval/`)

- **vector_store.py**: Manages ChromaDB or FAISS vector database
- **embeddings.py**: Generates embeddings using OpenAI or local models

### Agents (`src/agents/`)

- **Telekom Minister**: FastAPI microservice for governance and delegation.
- **Siemens Technician**: FastAPI microservice for hardware diagnosis.
- **Illigo Operator**: FastAPI microservice for telemetry analysis.
- **Shared Brain**: DSPy-based reasoning modules used by all agents (`src/agent/reasoning_engine.py`).

### Simulation (`src/simulation/`)

- **jan_2026_gridlock.py**: Simulates complex infrastructure failure
- Measures Mean Time to Innocence (MTTI)
- Evaluates diagnostic accuracy

## Configuration

### Environment Variables (`config/.env`)

```bash
# OpenAI
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Vector Store
VECTOR_STORE_TYPE=chromadb
EMBEDDING_MODEL_TYPE=openai
```

### Application Config (`config/config.yaml`)

See `config/config.yaml` for detailed configuration options including:
- Data ingestion settings
- Preprocessing parameters
- Graph schema definitions
- Retrieval configuration
- Agent parameters
- Simulation settings

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Quality

```bash
# Format code
black src/

# Lint
flake8 src/

# Type checking
mypy src/
```

### Jupyter Notebooks

Launch Jupyter to explore data and prototype:

```bash
jupyter lab
```

Then navigate to `notebooks/` directory.

## Evaluation Metrics

The system is evaluated using:

- **Mean Time to Innocence (MTTI)**: Time from fault occurrence to correct diagnosis
- **Diagnostic Accuracy**: Precision and recall of fault identification
- **Retrieval Performance**: Relevance of retrieved documentation
- **Reasoning Quality**: Correctness of generated recommendations

## Thesis Context

This project is part of a Master's thesis investigating:
- RAG architectures for infrastructure fault diagnosis
- Multi-domain knowledge integration
- Chain of Thought reasoning for complex technical problems
- Mean Time to Innocence as a key performance metric

## License

[Add your license here]

## Contact

[Add your contact information]

## Acknowledgments

- Telekom for infrastructure documentation
- Siemens for hardware scan data
- Illigo for OCPP event logs

---

**Note:** This is a research project. The codebase contains placeholder implementations (marked with `TODO`) that need to be completed as part of the thesis work.
