"""
Siemens Technician - FastAPI Microservice (Port 8002)

Hardware Expert Agent responsible for:
- Equipment fault diagnosis
- Hardware specification lookup
- Pain point analysis from questionnaire data
- Technical troubleshooting recommendations

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

from pydantic import ValidationError
from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority,
    ConsultRequest, ConsultResponse, AgentHealthStatus,
    DocumentReference, ConsultPayload
)
from src.agents.siemens_technician.brain import SiemensTechnicianModule
from src.agents.siemens_technician.data_loader import SiemensLoader
from src.agents.siemens_technician.vector_store import SiemensVectorStore
from src.agents.shared.dspy_config import configure_dspy
from src.agents.shared.graph_service import get_graph_service
from src.agents.shared.security import configure_cors

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
    logger.info("SIEMENS TECHNICIAN AGENT - Starting up...")
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
        app.state.vector_store = SiemensVectorStore()
        doc_count = app.state.vector_store.get_document_count()
        logger.info(f"Vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        # Initialize brain module
        app.state.brain = SiemensTechnicianModule()
        logger.info("Brain module (DSPy) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize brain: {e}")
        app.state.brain = None

    try:
        # Initialize graph service for hybrid search
        app.state.graph_service = get_graph_service()
        if app.state.graph_service.is_available():
            logger.info("Knowledge Graph service ready (Neo4j connected)")
            app.state.graph_ready = True
        else:
            logger.warning("Knowledge Graph service unavailable (Neo4j not connected)")
            app.state.graph_ready = False
    except Exception as e:
        logger.warning(f"Graph service initialization skipped: {e}")
        app.state.graph_service = None
        app.state.graph_ready = False

    logger.info("=" * 60)
    logger.info("SIEMENS TECHNICIAN AGENT - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Siemens Technician shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Siemens Technician Agent",
    description=(
        "Hardware Expert Agent for equipment diagnosis and specifications. "
        "Part of the Distributed Multi-Agent System (MAS) for infrastructure diagnosis."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for Streamlit and other clients
# Restricted to known origins (configurable via CORS_ALLOWED_ORIGINS env var)
configure_cors(app)


@app.get("/")
async def root():
    """Root endpoint with agent information."""
    return {
        "agent": "Siemens Technician",
        "role": "Hardware Expert",
        "port": 8002,
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
            agent_role=AgentRole.SIEMENS_TECHNICIAN,
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
            agent_role=AgentRole.SIEMENS_TECHNICIAN,
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
        Query type: 'diagnosis', 'specification', 'pain_point', or 'general'
    """
    query_lower = query.lower()

    # Diagnosis indicators
    diagnosis_keywords = [
        'fault', 'error', 'issue', 'problem', 'broken', 'malfunction',
        'not working', 'failing', 'diagnose', 'troubleshoot', 'fix'
    ]
    if any(kw in query_lower for kw in diagnosis_keywords):
        return 'diagnosis'

    # Specification indicators
    spec_keywords = [
        'specification', 'spec', 'model', 'vendor', 'equipment',
        'how many', 'which', 'what type', 'linac', 'ct', 'mr scanner'
    ]
    if any(kw in query_lower for kw in spec_keywords):
        return 'specification'

    # Pain point indicators
    pain_keywords = [
        'pain point', 'challenge', 'difficulty', 'complaint',
        'issue with', 'problem with', 'struggle', 'coil', 'positioning'
    ]
    if any(kw in query_lower for kw in pain_keywords):
        return 'pain_point'

    return 'general'


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """
    Primary consultation endpoint.

    Receives an Agent Card, processes the query using DSPy brain,
    and returns a response card with hardware expert findings.

    The Technician will:
    1. Retrieve relevant equipment data and pain points
    2. Analyze query type (diagnosis, specification, pain point)
    3. Apply appropriate reasoning signature
    4. Return structured response with technical details
    """
    global LAST_QUERY_TIME
    start_time = time.time()

    try:
        card = request.card
        logger.info(f"Received consultation from {card.sender}: {card.intent}")

        # Validate and extract payload fields
        try:
            validated_payload = ConsultPayload.from_payload(card.payload)
        except ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid payload: {e.errors()}"
            )

        query = validated_payload.query
        equipment_type = validated_payload.equipment_type or "unknown"
        delegated_by = validated_payload.delegated_by

        # Log delegation context if present
        if delegated_by:
            logger.info(f"Handling delegated request from {delegated_by}")

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

        # Retrieve relevant documents (Vector Search)
        documents = app.state.vector_store.similarity_search(query, k=5)

        # Build context from retrieved documents
        vector_context = "\n\n".join([
            f"[Institution: {doc.metadata.get('institution', 'unknown')}]\n{doc.page_content}"
            for doc in documents
        ])

        if not vector_context:
            vector_context = "No relevant equipment or pain point data found."

        # Enrich with Knowledge Graph context (Hybrid Search)
        graph_context = ""
        if hasattr(app.state, 'graph_service') and app.state.graph_service:
            try:
                graph_context = app.state.graph_service.get_enriched_context(
                    query=query,
                    location=None  # Siemens doesn't use location context
                )
                if graph_context:
                    logger.info(f"Graph context retrieved: {len(graph_context)} chars")
            except Exception as e:
                logger.warning(f"Graph context retrieval failed: {e}")

        # Combine vector + graph context
        if graph_context:
            context = f"{vector_context}\n\n--- Knowledge Graph Context ---\n{graph_context}"
        else:
            context = vector_context

        # Determine query type
        query_type = _determine_query_type(query)
        logger.info(f"Query type detected: {query_type}")

        # Process through DSPy brain
        logger.info("Processing through DSPy brain (hybrid context)...")
        result = app.state.brain(
            query=query,
            context=context,
            query_type=query_type,
            equipment_type=equipment_type
        )

        # Convert retrieved docs to DocumentReference
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'siemens'),
                file_name=doc.metadata.get('file_name', 'unknown'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=0.85,  # Would use actual score in production
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Build response payload based on query type
        if query_type == "diagnosis":
            response_payload = {
                "diagnosis": getattr(result, 'diagnosis', 'Unable to determine diagnosis'),
                "severity": getattr(result, 'severity', 'unknown'),
                "diagnostic_steps": getattr(result, 'diagnostic_steps', 'No steps available'),
                "requires_escalation": getattr(result, 'requires_escalation', 'no'),
                "answer": getattr(result, 'answer', ''),
                "specialist_agent": "siemens_technician"
            }
            if delegated_by:
                response_payload["delegated_by"] = delegated_by
            severity = getattr(result, 'severity', 'low')
            priority = Priority.CRITICAL if severity == 'critical' else (
                Priority.HIGH if severity == 'high' else Priority.NORMAL
            )
        elif query_type == "specification":
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to find specification'),
                "equipment_details": getattr(result, 'equipment_details', ''),
                "source_institutions": getattr(result, 'source_institutions', ''),
                "specialist_agent": "siemens_technician"
            }
            if delegated_by:
                response_payload["delegated_by"] = delegated_by
            priority = Priority.NORMAL
        elif query_type == "pain_point":
            response_payload = {
                "common_issues": getattr(result, 'common_issues', 'No issues found'),
                "affected_institutions": getattr(result, 'affected_institutions', ''),
                "recommended_solutions": getattr(result, 'recommended_solutions', ''),
                "answer": getattr(result, 'answer', ''),
                "specialist_agent": "siemens_technician"
            }
            if delegated_by:
                response_payload["delegated_by"] = delegated_by
            priority = Priority.NORMAL
        else:
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to process query'),
                "troubleshooting_steps": getattr(result, 'troubleshooting_steps', ''),
                "likely_resolution": getattr(result, 'likely_resolution', ''),
                "parts_or_service_needed": getattr(result, 'parts_or_service_needed', ''),
                "specialist_agent": "siemens_technician"
            }
            if delegated_by:
                response_payload["delegated_by"] = delegated_by
            priority = Priority.NORMAL

        # Build response card
        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.SIEMENS_TECHNICIAN,
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
            sender=AgentRole.SIEMENS_TECHNICIAN,
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
        loader = SiemensLoader()
        documents = loader.load()

        if not documents:
            return {
                "success": True,
                "message": "No documents found to index",
                "indexed_count": 0
            }

        # Index documents
        if not app.state.vector_store:
            app.state.vector_store = SiemensVectorStore()

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


if __name__ == "__main__":
    from src.agents.shared.server_utils import run_agent_server

    run_agent_server(
        app=app,
        agent_name="Siemens Technician",
        env_var_name="SIEMENS_TECHNICIAN_PORT",
        default_port=8002
    )
