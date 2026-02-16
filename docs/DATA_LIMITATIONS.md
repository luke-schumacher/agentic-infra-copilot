# Data Limitations

## 1. Institution Profile Coverage (3 of 35 customers)

**Source**: MRRT questionnaire (`sample_processed_wide_format.csv`, `sample_processed_long_format.csv`)

Only 3 institutions completed the MRRT questionnaire:
- University Hospital Munich
- Memorial Cancer Center
- Karolinska Institute

However, MRI event logs exist for 35 distinct customer IDs (mr141049 through mr237202).

**Impact on Governance Agent**: The `ExplainErrorContext` DSPy signature requires `institution_profile` + `technical_error` to contextualize errors. For the 32 customers without institution profiles, the agent can only rely on workload patterns and error statistics, not institutional context (equipment, patient volume, pain points).

**Mitigation**: The Governance Agent falls back gracefully to workload-based context when no institution profile is available. The `customer_mapping.csv` provides basic event count and error statistics for all 35 customers.

## 2. ChromaDB Re-indexing Required

After adding new data loaders (failure mode catalog, clinical protocols, RadLex terms, governance PDFs), the ChromaDB vector stores for all three agents need re-indexing:

- **Hardware Agent** (`chroma_db/hardware_agent/`): Was empty; stale DB deleted. Needs full indexing via `POST /index` on port 8002.
- **Telemetry Agent** (`chroma_db/telemetry_agent/`): Was empty; stale DB deleted. Needs full indexing via `POST /index` on port 8003.
- **Governance Agent** (`chroma_db/governance_agent/`): Has existing index (58 MB) but is missing clinical protocols, RadLex terms, and governance PDFs. Needs re-indexing via `POST /index` on port 8001.

## 3. Event Log Data Not in Vector Store

The 35 customers' Parquet event log files (~1.4 GB) are not indexed into ChromaDB by default (`include_event_logs=False`). The Hardware Agent relies on summary statistics from `per_customer_error_profiles.csv` and the curated `failure_modes.csv` catalog instead.

This is by design to avoid memory issues during indexing, but means the Hardware Agent cannot search raw event-level data through RAG.
