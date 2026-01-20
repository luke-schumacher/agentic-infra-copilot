# How to Run the Agentic Infra Co-Pilot

## What is this? (The Hospital Metaphor)

Imagine your infrastructure is a **patient** that sometimes gets sick (faults, errors, anomalies). This system is like a **hospital with three specialist doctors** who work together to diagnose problems:

| Agent | Role | Think of it as... |
|-------|------|-------------------|
| **Telekom Minister** (Port 8001) | Governance & SLA Authority | The **Chief of Medicine** - knows all the rules, protocols, and decides who should handle what |
| **Siemens Technician** (Port 8002) | Hardware Expert | The **Radiologist** - expert in reading equipment scans and understanding machine problems |
| **Illigo Operator** (Port 8003) | Live Monitor | The **ER Doctor** - monitors real-time vital signs and catches problems as they happen |

The **Streamlit UI** is like the **Hospital Reception** - patients (you) describe their symptoms, and it routes them to the right doctors.

---

## Quick Start (5 Minutes)

### Step 1: Install Dependencies

```bash
# Open terminal in project folder
cd agentic-infra-copilot

# Create virtual environment (like creating a clean workspace)
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate

# Activate it (Mac/Linux)
source venv/bin/activate

# Install all the tools the doctors need
pip install -r requirements.txt
```

### Step 2: Set Up Your API Keys

Create a file called `.env` in the `config/` folder:

```bash
# config/.env

# Groq API Key (free at console.groq.com) - This is the "brain" of our doctors
GROQ_API_KEY=your_groq_api_key_here

# Optional: OpenAI for better embeddings (costs money but higher quality)
OPENAI_API_KEY=your_openai_api_key_here
```

**Getting a Groq API Key (Free!):**
1. Go to https://console.groq.com
2. Sign up for free
3. Create an API key
4. Copy it to your `.env` file

### Step 3: Start the Doctors (Agents)

Open **4 separate terminal windows** (think of it as opening 4 different clinics):

**Terminal 1 - The Chief of Medicine (Telekom Minister):**
```bash
cd agentic-infra-copilot
venv\Scripts\activate  # or source venv/bin/activate
python src/agents/telekom_minister/main.py
```
You should see: `TELEKOM MINISTER AGENT - Ready to serve!`

**Terminal 2 - The Radiologist (Siemens Technician):**
```bash
cd agentic-infra-copilot
venv\Scripts\activate
python src/agents/siemens_technician/main.py
```
You should see: `SIEMENS TECHNICIAN AGENT - Ready to serve!`

**Terminal 3 - The ER Doctor (Illigo Operator):**
```bash
cd agentic-infra-copilot
venv\Scripts\activate
python src/agents/illigo_operator/main.py
```
You should see: `ILLIGO OPERATOR AGENT - Ready to serve!`

**Terminal 4 - The Reception Desk (Streamlit UI):**
```bash
cd agentic-infra-copilot
venv\Scripts\activate
streamlit run src/ui/app.py
```
A browser window should open at `http://localhost:8501`

### Step 4: Index the Medical Records (Load Your Data)

Before the doctors can help, they need to read the patient files:

1. Open the Streamlit UI in your browser
2. In the sidebar, click **"📚 Index Documents"**
3. Wait for it to complete

Or do it manually via API:
```bash
# Index Telekom documents
curl -X POST http://localhost:8001/index

# Index Siemens documents
curl -X POST http://localhost:8002/index

# Index Illigo documents
curl -X POST http://localhost:8003/index
```

### Step 5: Ask Your First Question

In the Streamlit chat, try:
- "What caused the ground fault at Koumassi?"
- "Which hospitals have coil positioning issues?"
- "What are the SLA requirements for latency?"

---

## Understanding the Architecture (The Restaurant Metaphor)

Think of the system like a **high-end restaurant**:

```
┌─────────────────────────────────────────────────────────────┐
│                    🍽️  STREAMLIT UI                         │
│                  (The Maitre d' / Host)                     │
│         Takes your order and coordinates everything         │
└──────────────────────────┬──────────────────────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     │                     │                     │
     ▼                     ▼                     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   TELEKOM   │     │   SIEMENS   │     │   ILLIGO    │
│   MINISTER  │     │  TECHNICIAN │     │  OPERATOR   │
│             │     │             │     │             │
│ 👨‍🍳 Head Chef │     │ 🔧 Sous Chef │     │ 📊 Pastry   │
│             │     │             │     │    Chef     │
│ Decides the │     │ Handles the │     │ Monitors    │
│ menu/rules  │     │ hardware    │     │ live orders │
└─────────────┘     └─────────────┘     └─────────────┘
     │                     │                     │
     ▼                     ▼                     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  📚 Recipe  │     │  📚 Recipe  │     │  📚 Recipe  │
│    Book     │     │    Book     │     │    Book     │
│  (Vector    │     │  (Vector    │     │  (Vector    │
│   Store)    │     │   Store)    │     │   Store)    │
│             │     │             │     │             │
│ Telekom PDFs│     │ Siemens CSV │     │ Illigo      │
│ SLA/Intent  │     │ Equipment   │     │ Events/Logs │
└─────────────┘     └─────────────┘     └─────────────┘
```

**How a request flows:**
1. You ask a question (place an order)
2. The UI (Host) sends it to the Telekom Minister (Head Chef)
3. The Minister checks the rules and decides if specialists are needed
4. If needed, they "delegate" to Siemens (hardware) or Illigo (events)
5. Each agent looks up relevant info from their "recipe book" (vector store)
6. The answer comes back to you

---

## Key Concepts Explained

### What is a "Vector Store"? (The Library Card Catalog)

Imagine a massive library with thousands of books. A vector store is like a **magical card catalog** that:
- Understands the *meaning* of your question
- Finds books that are *similar in meaning*, not just matching words
- Returns the most relevant passages

When you ask "What caused problems at Koumassi?", it finds documents about Koumassi faults even if they use different words like "ground fault" or "charging station error".

### What is "DSPy"? (The Doctor's Training)

DSPy is like **medical school for AI agents**. It teaches them:
- How to think step-by-step (Chain of Thought)
- What questions to ask themselves
- How to format their answers

Each agent has a "brain" file (`brain.py`) with their specialized training.

### What is "ChromaDB"? (The Filing Cabinet)

ChromaDB is where each agent stores their documents:
- `./chroma_db/telekom_minister/` - SLA and Intent documents
- `./chroma_db/siemens_technician/` - Equipment specs and pain points
- `./chroma_db/illigo_operator/` - Event logs and station data

---

## Troubleshooting (When Things Go Wrong)

### "GROQ_API_KEY not found"
→ Make sure you created `config/.env` with your Groq API key

### "Vector store not initialized"
→ Click "Index Documents" in the sidebar, or run the index endpoints

### "Agent OFFLINE" in sidebar
→ That agent isn't running. Start it with `python src/agents/<name>/main.py`

### "No relevant documents found"
→ The vector store is empty. Index your documents first.

### Port already in use
→ Another process is using that port. Kill it or change the port:
```bash
# Check what's using port 8001
netstat -ano | findstr :8001

# Or set a different port
set TELEKOM_MINISTER_PORT=9001
python src/agents/telekom_minister/main.py
```

---

## Data Locations

| Data Type | Location | Description |
|-----------|----------|-------------|
| Telekom PDFs | `data/raw/telekom/` | SLA and Intent documentation |
| Siemens CSVs | `data/raw/siemens/` | Equipment questionnaire responses |
| Illigo Data | `data/raw/illigo/data/` | Charging station stats and events |
| Vector DBs | `./chroma_db/` | Indexed documents (auto-created) |

---

## API Endpoints Reference

Each agent exposes the same pattern of endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Agent info |
| `/health` | GET | Health status |
| `/consult` | POST | Send a query |
| `/index` | POST | Index documents |
| `/documents/count` | GET | Document count |
| `/documents/search` | GET | Search documents |

Example health check:
```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## Next Steps After Setup

1. **Explore the data** - Run the EDA notebook: `jupyter lab notebooks/thesis_comprehensive_eda.ipynb`

2. **Test individual agents** - Use the `/documents/search` endpoint to see what each agent knows

3. **Try the Grid-Lock scenario** - Ask about the "Jan 2026 Grid-Lock" incident to test multi-agent diagnosis

4. **Add your own data** - Put PDFs in `data/raw/telekom/`, CSVs in `data/raw/siemens/`, and re-index

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────────────┐
│                    QUICK REFERENCE                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  START EVERYTHING:                                         │
│  ─────────────────                                         │
│  Terminal 1: python src/agents/telekom_minister/main.py    │
│  Terminal 2: python src/agents/siemens_technician/main.py  │
│  Terminal 3: python src/agents/illigo_operator/main.py     │
│  Terminal 4: streamlit run src/ui/app.py                   │
│                                                            │
│  PORTS:                                                    │
│  ───────                                                   │
│  8001 = Telekom Minister (Governance)                      │
│  8002 = Siemens Technician (Hardware)                      │
│  8003 = Illigo Operator (Live Monitor)                     │
│  8501 = Streamlit UI                                       │
│                                                            │
│  INDEX DATA:                                               │
│  ───────────                                               │
│  curl -X POST http://localhost:8001/index                  │
│  curl -X POST http://localhost:8002/index                  │
│  curl -X POST http://localhost:8003/index                  │
│                                                            │
│  HEALTH CHECK:                                             │
│  ─────────────                                             │
│  curl http://localhost:8001/health                         │
│  curl http://localhost:8002/health                         │
│  curl http://localhost:8003/health                         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

**Happy Diagnosing! 🏥🔧⚡**
