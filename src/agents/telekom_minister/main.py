"""
Telekom Minister - FastAPI Microservice (Port 8001)

Governance Agent responsible for:
- SLA compliance monitoring
- Network Intent validation
- Workflow orchestration and delegation to specialist agents

Supports BASELINE_MODE for single-agent evaluation (RQ2 comparison):
- When BASELINE_MODE=true: Uses unified vector store with ALL domain knowledge
- When BASELINE_MODE=false (default): Uses multi-agent delegation

Endpoints:
- POST /consult - Primary consultation endpoint
- GET /health - Health check
- POST /index - Trigger vector store indexing

Follows Telekom's 'External Minister' pattern for MAS architecture.

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
import httpx

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from pydantic import ValidationError
from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority,
    ConsultRequest, ConsultResponse, AgentHealthStatus,
    DocumentReference, ConsultPayload
)
from src.agents.telekom_minister.brain import TelekomMinisterModule
from src.agents.telekom_minister.data_loader import TelekomLoader
from src.agents.telekom_minister.vector_store import TelekomVectorStore
from src.agents.shared.dspy_config import configure_dspy
from src.agents.shared.graph_service import get_graph_service
from src.agents.shared.security import configure_cors

# Baseline mode imports (for single-agent A/B comparison)
try:
    from src.agents.baseline.unified_store import UnifiedVectorStore
    BASELINE_AVAILABLE = True
except ImportError:
    BASELINE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
START_TIME: Optional[datetime] = None
LAST_QUERY_TIME: Optional[datetime] = None

# Baseline mode configuration (for single-agent A/B comparison)
BASELINE_MODE = os.getenv("BASELINE_MODE", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global START_TIME

    # ==================== STARTUP ====================
    logger.info("=" * 60)
    if BASELINE_MODE:
        logger.info("TELEKOM MINISTER AGENT - Starting up in BASELINE MODE...")
        logger.info("Single-agent mode: Using unified vector store, NO delegation")
    else:
        logger.info("TELEKOM MINISTER AGENT - Starting up in MULTI-AGENT MODE...")
        logger.info("Multi-agent mode: Using domain-specific store WITH delegation")
    logger.info("=" * 60)

    START_TIME = datetime.utcnow()
    app.state.baseline_mode = BASELINE_MODE

    try:
        # Configure DSPy with Groq
        configure_dspy()
        logger.info("DSPy configured with Groq/Llama3-70B")
        app.state.dspy_ready = True
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        app.state.dspy_ready = False

    try:
        # Initialize vector store based on mode
        if BASELINE_MODE and BASELINE_AVAILABLE:
            # BASELINE MODE: Use unified vector store with ALL domain knowledge
            logger.info("Initializing UNIFIED vector store (baseline mode)...")
            app.state.vector_store = UnifiedVectorStore()
            doc_count = app.state.vector_store.get_document_count()
            if doc_count == 0:
                logger.info("Unified store empty - indexing all domain documents...")
                doc_count = app.state.vector_store.index_documents(force_reindex=True)
            logger.info(f"Unified vector store ready: {doc_count} documents (all domains)")
        else:
            # MULTI-AGENT MODE: Use domain-specific Telekom store
            app.state.vector_store = TelekomVectorStore()
            doc_count = app.state.vector_store.get_document_count()
            logger.info(f"Telekom vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        # Initialize brain module
        app.state.brain = TelekomMinisterModule()
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
    logger.info("TELEKOM MINISTER AGENT - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Telekom Minister shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Telekom Minister Agent",
    description=(
        "Governance Agent for SLA/Intent Authority. "
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
        "agent": "Telekom Minister",
        "role": "Governance Agent",
        "port": 8001,
        "status": "running",
        "baseline_mode": BASELINE_MODE,
        "mode_description": "Single-agent (unified knowledge)" if BASELINE_MODE else "Multi-agent (delegation enabled)",
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
            agent_role=AgentRole.TELEKOM_MINISTER,
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
            agent_role=AgentRole.TELEKOM_MINISTER,
            status="unhealthy",
            vector_store_ready=False,
            dspy_ready=False,
            document_count=0,
            uptime_seconds=0.0
        )


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """
    Primary consultation endpoint.

    Receives an Agent Card, processes the query using DSPy brain,
    and returns a response card with findings and delegation decisions.

    The Minister will:
    1. Retrieve relevant SLA/Intent documents
    2. Assess risk if symptom is reported
    3. Determine if delegation to specialist is needed
    4. Return structured response with recommendations
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
        location = validated_payload.location or "unknown"
        is_symptom = validated_payload.is_symptom

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
            f"[Source: {doc.metadata.get('file_name', 'unknown')}]\n{doc.page_content}"
            for doc in documents
        ])

        if not vector_context:
            vector_context = "No relevant SLA or Intent documentation found."

        # Enrich with Knowledge Graph context (Hybrid Search)
        graph_context = ""
        if hasattr(app.state, 'graph_service') and app.state.graph_service:
            try:
                graph_context = app.state.graph_service.get_enriched_context(
                    query=query,
                    location=location if location != "unknown" else None
                )
                if graph_context:
                    logger.info(f"Graph context retrieved: {len(graph_context)} chars")
            except Exception as e:
                logger.warning(f"Graph context retrieval failed: {e}")

        # Combine vector + graph context for hybrid reasoning
        if graph_context:
            context = f"{vector_context}\n\n--- Knowledge Graph Context ---\n{graph_context}"
        else:
            context = vector_context

        # Process through DSPy brain
        logger.info("Processing through DSPy brain (hybrid context)...")
        result = app.state.brain(
            query=query,
            context=context,
            location=location,
            is_symptom=is_symptom
        )

        # Convert retrieved docs to DocumentReference
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'telekom'),
                file_name=doc.metadata.get('file_name', 'unknown'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=0.85,  # Would use actual score in production
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Extract delegation info from brain result
        target_agent = getattr(result, 'target_agent', 'self')
        delegation_reason = getattr(result, 'delegation_reason', '')
        refined_query = getattr(result, 'refined_query', query)

        # Build base response payload based on query type
        if is_symptom:
            response_payload = {
                "risk_level": getattr(result, 'risk_level', 'unknown'),
                "violated_slas": getattr(result, 'violated_slas', 'None identified'),
                "recommended_actions": getattr(result, 'recommended_actions', 'No immediate actions'),
                "delegation": {
                    "target_agent": target_agent,
                    "reason": delegation_reason,
                    "refined_query": refined_query
                }
            }
            # Set priority based on risk level
            risk = getattr(result, 'risk_level', 'low')
            priority = Priority.CRITICAL if risk == 'critical' else (
                Priority.HIGH if risk == 'high' else Priority.NORMAL
            )
        else:
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to determine answer'),
                "confidence": getattr(result, 'confidence', 'low'),
                "sources_used": getattr(result, 'sources_used', ''),
                "delegation": {
                    "target_agent": target_agent,
                    "reason": delegation_reason,
                    "refined_query": refined_query
                }
            }
            priority = Priority.NORMAL

        # If delegation needed, await specialist response BEFORE building response card
        # BASELINE MODE: Skip delegation entirely - answer from unified knowledge
        if BASELINE_MODE:
            if target_agent and target_agent != 'self':
                logger.info(f"BASELINE MODE: Would delegate to {target_agent}, but answering directly instead")
                response_payload["delegation"]["skipped"] = True
                response_payload["delegation"]["reason"] = "Baseline mode - single agent answering from unified knowledge"
        elif target_agent and target_agent != 'self':
            # MULTI-AGENT MODE: Execute delegation
            logger.info(f"Delegating to {target_agent}...")
            specialist_response = await delegate_to_specialist(
                target_agent,
                refined_query,
                card.message_id
            )
            if specialist_response:
                response_payload["specialist_findings"] = specialist_response
                logger.info(f"Specialist {target_agent} findings integrated into response")
            else:
                logger.warning(f"Delegation to {target_agent} returned no response")
                response_payload["specialist_findings"] = {
                    "error": f"Specialist {target_agent} unavailable or returned no response"
                }

        # Build response card WITH specialist findings included
        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.TELEKOM_MINISTER,
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
            sender=AgentRole.TELEKOM_MINISTER,
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


async def delegate_to_specialist(target: str, query: str, correlation_id: str):
    """
    Delegate a query to a specialist agent.

    Args:
        target: Target agent name ('siemens_technician' or 'illigo_operator')
        query: Refined query for the specialist
        correlation_id: Original message ID for correlation
    """
    # Support Docker and local environments via environment variables
    siemens_url = os.getenv("SIEMENS_TECHNICIAN_URL", "http://localhost:8002")
    illigo_url = os.getenv("ILLIGO_OPERATOR_URL", "http://localhost:8003")

    agent_urls = {
        "siemens_technician": f"{siemens_url}/consult",
        "illigo_operator": f"{illigo_url}/consult"
    }

    if target not in agent_urls:
        logger.warning(f"Unknown delegation target: {target}")
        return None

    target_role = (
        AgentRole.SIEMENS_TECHNICIAN if "siemens" in target
        else AgentRole.ILLIGO_OPERATOR
    )

    delegation_card = AgentCard(
        correlation_id=correlation_id,
        sender=AgentRole.TELEKOM_MINISTER,
        recipient=target_role,
        intent=IntentType.DELEGATE,
        priority=Priority.HIGH,
        payload={
            "query": query,
            "delegated_by": "telekom_minister"
        }
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                agent_urls[target],
                json=ConsultRequest(card=delegation_card).model_dump(),
                timeout=30.0
            )
            logger.info(f"Delegation to {target} completed: {response.status_code}")
            return response.json()
    except Exception as e:
        logger.error(f"Delegation to {target} failed: {e}")
        return None


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
        loader = TelekomLoader()
        documents = loader.load()

        if not documents:
            return {
                "success": True,
                "message": "No documents found to index",
                "indexed_count": 0
            }

        # Index documents
        if not app.state.vector_store:
            app.state.vector_store = TelekomVectorStore()

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


if __name__ == "__main__":
    from src.agents.shared.server_utils import run_agent_server

    run_agent_server(
        app=app,
        agent_name="Telekom Minister",
        env_var_name="TELEKOM_MINISTER_PORT",
        default_port=8001
    )
