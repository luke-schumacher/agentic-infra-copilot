"""
Illigo Operator - FastAPI Microservice (Port 8003)

Live Monitor Agent responsible for:
- OCPP event log analysis
- Anomaly detection in charging station data
- Real-time fault correlation
- Load balance monitoring

Endpoints:
- POST /consult - Primary consultation endpoint
- GET /health - Health check
- POST /index - Trigger vector store indexing

Part of the Tripartite MAS for infrastructure fault diagnosis.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority,
    ConsultRequest, ConsultResponse, AgentHealthStatus,
    DocumentReference
)
from src.agents.illigo_operator.brain import IlligoOperatorModule
from src.agents.illigo_operator.data_loader import IlligoLoader
from src.agents.illigo_operator.vector_store import IlligoVectorStore
from src.agents.shared.dspy_config import configure_dspy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
START_TIME: Optional[datetime] = None
LAST_QUERY_TIME: Optional[datetime] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global START_TIME

    # ==================== STARTUP ====================
    logger.info("=" * 60)
    logger.info("ILLIGO OPERATOR AGENT - Starting up...")
    logger.info("=" * 60)

    START_TIME = datetime.utcnow()

    try:
        # Configure DSPy with Groq
        configure_dspy()
        logger.info("DSPy configured with Groq/Llama3-70B")
        app.state.dspy_ready = True
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        app.state.dspy_ready = False

    try:
        # Initialize vector store
        app.state.vector_store = IlligoVectorStore()
        doc_count = app.state.vector_store.get_document_count()
        logger.info(f"Vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        # Initialize brain module
        app.state.brain = IlligoOperatorModule()
        logger.info("Brain module (DSPy) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize brain: {e}")
        app.state.brain = None

    logger.info("=" * 60)
    logger.info("ILLIGO OPERATOR AGENT - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Illigo Operator shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Illigo Operator Agent",
    description=(
        "Live Monitor Agent for OCPP event analysis and anomaly detection. "
        "Part of the Distributed Multi-Agent System (MAS) for infrastructure diagnosis."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for Streamlit and other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with agent information."""
    return {
        "agent": "Illigo Operator",
        "role": "Live Monitor",
        "port": 8003,
        "status": "running",
        "endpoints": ["/health", "/consult", "/index"]
    }


@app.get("/health", response_model=AgentHealthStatus)
async def health_check():
    """
    Health check endpoint.

    Returns current status of the agent including:
    - Vector store readiness
    - DSPy readiness
    - Document count
    - Uptime
    """
    global LAST_QUERY_TIME

    try:
        doc_count = 0
        vs_ready = False

        if hasattr(app.state, 'vector_store') and app.state.vector_store:
            doc_count = app.state.vector_store.get_document_count()
            vs_ready = True

        dspy_ready = getattr(app.state, 'dspy_ready', False)

        uptime = 0.0
        if START_TIME:
            uptime = (datetime.utcnow() - START_TIME).total_seconds()

        # Determine overall status
        if vs_ready and dspy_ready:
            status = "healthy"
        elif vs_ready or dspy_ready:
            status = "degraded"
        else:
            status = "unhealthy"

        return AgentHealthStatus(
            agent_role=AgentRole.ILLIGO_OPERATOR,
            status=status,
            vector_store_ready=vs_ready,
            dspy_ready=dspy_ready,
            document_count=doc_count,
            last_query_time=LAST_QUERY_TIME,
            uptime_seconds=uptime
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return AgentHealthStatus(
            agent_role=AgentRole.ILLIGO_OPERATOR,
            status="unhealthy",
            vector_store_ready=False,
            dspy_ready=False,
            document_count=0,
            uptime_seconds=0.0
        )


def _determine_query_type(query: str) -> str:
    """
    Determine the type of query based on content analysis.

    Args:
        query: User's query string

    Returns:
        Query type: 'fault', 'anomaly', 'correlation', 'load', or 'general'
    """
    query_lower = query.lower()

    # Fault analysis indicators
    fault_keywords = [
        'fault', 'error', 'ground fault', 'over current', 'failure',
        'ocpp', 'cx00', 'faulted', 'offline', 'communication failure'
    ]
    if any(kw in query_lower for kw in fault_keywords):
        return 'fault'

    # Anomaly detection indicators
    anomaly_keywords = [
        'anomaly', 'abnormal', 'unusual', 'deviation', 'spike',
        'unexpected', 'irregular', 'baseline'
    ]
    if any(kw in query_lower for kw in anomaly_keywords):
        return 'anomaly'

    # Event correlation indicators
    correlation_keywords = [
        'correlate', 'correlation', 'pattern', 'sequence', 'cascade',
        'chain', 'related events', 'timeline'
    ]
    if any(kw in query_lower for kw in correlation_keywords):
        return 'correlation'

    # Load balance indicators
    load_keywords = [
        'load', 'balance', 'imbalance', 'energy', 'consumption',
        'overloaded', 'underutilized', 'distribution'
    ]
    if any(kw in query_lower for kw in load_keywords):
        return 'load'

    return 'general'


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """
    Primary consultation endpoint.

    Receives an Agent Card, processes the query using DSPy brain,
    and returns a response card with live monitoring findings.

    The Operator will:
    1. Retrieve relevant event logs and station data
    2. Analyze query type (fault, anomaly, correlation, load, general)
    3. Apply appropriate reasoning signature
    4. Return structured response with operational insights
    """
    global LAST_QUERY_TIME
    start_time = time.time()

    try:
        card = request.card
        logger.info(f"Received consultation from {card.sender}: {card.intent}")

        # Extract query from payload
        query = card.payload.get("query", "")
        station_id = card.payload.get("station_id", "unknown")
        timestamp = card.payload.get("timestamp", "")

        if not query:
            raise HTTPException(
                status_code=400,
                detail="Query is required in payload"
            )

        # Check if vector store and brain are available
        if not app.state.vector_store:
            raise HTTPException(
                status_code=503,
                detail="Vector store not initialized"
            )

        if not app.state.brain:
            raise HTTPException(
                status_code=503,
                detail="Brain module not initialized"
            )

        # Retrieve relevant documents
        documents = app.state.vector_store.similarity_search(query, k=5)

        # Build context from retrieved documents
        context = "\n\n".join([
            f"[{doc.metadata.get('data_type', 'event')}] {doc.page_content}"
            for doc in documents
        ])

        if not context:
            context = "No relevant charging station data or event logs found."

        # Determine query type
        query_type = _determine_query_type(query)
        logger.info(f"Query type detected: {query_type}")

        # Process through DSPy brain
        logger.info("Processing through DSPy brain...")
        result = app.state.brain(
            query=query,
            context=context,
            query_type=query_type,
            station_id=station_id,
            timestamp=timestamp
        )

        # Convert retrieved docs to DocumentReference
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'illigo'),
                file_name=doc.metadata.get('file_name', 'event_log'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=0.85,
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Build response payload based on query type
        if query_type == "fault":
            response_payload = {
                "root_cause": getattr(result, 'root_cause', 'Unable to determine root cause'),
                "impact": getattr(result, 'impact', 'Unknown impact'),
                "severity": getattr(result, 'severity', 'unknown'),
                "corrective_actions": getattr(result, 'corrective_actions', 'No actions recommended'),
                "answer": getattr(result, 'answer', '')
            }
            severity = getattr(result, 'severity', 'low')
            priority = Priority.CRITICAL if severity == 'critical' else (
                Priority.HIGH if severity == 'high' else Priority.NORMAL
            )
        elif query_type == "anomaly":
            response_payload = {
                "is_anomaly": getattr(result, 'is_anomaly', 'unknown'),
                "anomaly_type": getattr(result, 'anomaly_type', ''),
                "deviation_description": getattr(result, 'deviation_description', ''),
                "risk_level": getattr(result, 'risk_level', 'unknown'),
                "answer": getattr(result, 'answer', '')
            }
            risk = getattr(result, 'risk_level', 'low')
            priority = Priority.HIGH if risk == 'high' else Priority.NORMAL
        elif query_type == "correlation":
            response_payload = {
                "correlation_found": getattr(result, 'correlation_found', 'unknown'),
                "pattern_description": getattr(result, 'pattern_description', ''),
                "causal_chain": getattr(result, 'causal_chain', ''),
                "affected_stations": getattr(result, 'affected_stations', ''),
                "answer": getattr(result, 'answer', '')
            }
            priority = Priority.NORMAL
        elif query_type == "load":
            response_payload = {
                "imbalance_detected": getattr(result, 'imbalance_detected', 'unknown'),
                "overloaded_stations": getattr(result, 'overloaded_stations', ''),
                "underutilized_stations": getattr(result, 'underutilized_stations', ''),
                "recommendations": getattr(result, 'recommendations', ''),
                "answer": getattr(result, 'answer', '')
            }
            priority = Priority.NORMAL
        else:
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to process query'),
                "data_summary": getattr(result, 'data_summary', ''),
                "confidence": getattr(result, 'confidence', 'low')
            }
            priority = Priority.NORMAL

        # Build response card
        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.ILLIGO_OPERATOR,
            recipient=card.sender,
            intent=IntentType.REPORT,
            priority=priority,
            payload=response_payload,
            documents=doc_refs
        )

        LAST_QUERY_TIME = datetime.utcnow()
        processing_time = (time.time() - start_time) * 1000

        logger.info(f"Consultation completed in {processing_time:.2f}ms")

        return ConsultResponse(
            success=True,
            response_card=response_card,
            processing_time_ms=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Consultation failed: {e}", exc_info=True)
        processing_time = (time.time() - start_time) * 1000

        error_card = AgentCard(
            sender=AgentRole.ILLIGO_OPERATOR,
            recipient=request.card.sender,
            intent=IntentType.REPORT,
            priority=Priority.HIGH,
            payload={"error": str(e)}
        )

        return ConsultResponse(
            success=False,
            response_card=error_card,
            processing_time_ms=processing_time,
            error=str(e)
        )


@app.post("/index")
async def index_documents(force_reindex: bool = False):
    """
    Trigger vector store indexing.

    Args:
        force_reindex: If True, clear existing documents and re-index

    Returns:
        Indexing results with document count
    """
    try:
        logger.info("Starting document indexing...")

        # Load documents
        loader = IlligoLoader()
        documents = loader.load()

        if not documents:
            return {
                "success": True,
                "message": "No documents found to index",
                "indexed_count": 0
            }

        # Index documents
        if not app.state.vector_store:
            app.state.vector_store = IlligoVectorStore()

        count = app.state.vector_store.index_documents(
            documents,
            force_reindex=force_reindex
        )

        return {
            "success": True,
            "message": f"Successfully indexed {count} documents",
            "indexed_count": count,
            "total_in_store": app.state.vector_store.get_document_count()
        }

    except Exception as e:
        logger.error(f"Indexing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/count")
async def get_document_count():
    """Get the current document count in the vector store."""
    if not app.state.vector_store:
        return {"count": 0, "status": "vector_store_not_initialized"}

    count = app.state.vector_store.get_document_count()
    return {"count": count, "status": "ok"}


@app.get("/documents/search")
async def search_documents(query: str, k: int = 5):
    """
    Search documents endpoint for debugging.

    Args:
        query: Search query
        k: Number of results

    Returns:
        List of matching documents
    """
    if not app.state.vector_store:
        raise HTTPException(
            status_code=503,
            detail="Vector store not initialized"
        )

    documents = app.state.vector_store.similarity_search(query, k=k)

    return {
        "query": query,
        "results": [
            {
                "content": doc.page_content[:500],
                "metadata": doc.metadata
            }
            for doc in documents
        ]
    }


@app.get("/events/recent")
async def get_recent_events(station_id: Optional[str] = None, k: int = 10):
    """
    Get recent events from the vector store.

    Args:
        station_id: Optional station filter
        k: Number of events to return

    Returns:
        List of recent events
    """
    if not app.state.vector_store:
        raise HTTPException(
            status_code=503,
            detail="Vector store not initialized"
        )

    documents = app.state.vector_store.get_recent_events(station_id=station_id, k=k)

    return {
        "station_filter": station_id,
        "events": [
            {
                "content": doc.page_content,
                "event_id": doc.metadata.get('event_id'),
                "station_id": doc.metadata.get('station_id'),
                "severity": doc.metadata.get('severity'),
                "timestamp": doc.metadata.get('timestamp')
            }
            for doc in documents
        ]
    }


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default to 8003
    port = int(os.getenv("ILLIGO_OPERATOR_PORT", "8003"))

    logger.info(f"Starting Illigo Operator on port {port}...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
