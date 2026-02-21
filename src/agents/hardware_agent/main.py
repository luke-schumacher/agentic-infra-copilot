"""
Diagnostic Specialist - FastAPI Microservice (Port 8002)

Agent 1: "The Specialist" - Diagnostic & Technical Expert responsible for:
- DICOM conformance failure diagnosis (cross-ref SOP UIDs with event log errors)
- MRI hardware/software error analysis from event logs
- Technical specification lookup from DCS/CSPL documentation
- SOP Class UID cross-referencing

Endpoints:
- POST /consult - Primary consultation endpoint
- GET /health - Health check
- POST /index - Trigger vector store indexing

Part of the 3-Agent MAS for Siemens MRI Operations Analysis.

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
    AgentCard, AgentRole, IntentType, Priority, ResponseType,
    ConsultRequest, ConsultResponse, AgentHealthStatus,
    DocumentReference, ConsultPayload
)
from src.agents.hardware_agent.brain import DiagnosticSpecialistModule
from src.agents.hardware_agent.mri_hardware_loader import MRIHardwareLoader
from src.agents.hardware_agent.vector_store import DiagnosticSpecialistStore
from src.agents.shared.dspy_config import configure_dspy
import dspy
from src.agents.shared.graph_service import get_graph_service
from src.agents.shared.security import configure_cors

# Polars event log loader
try:
    from src.preprocessing.parquet_loader import LazyParquetLoader
    PARQUET_AVAILABLE = True
except ImportError:
    LazyParquetLoader = None
    PARQUET_AVAILABLE = False

# Backward compatibility imports
try:
    from src.agents.hardware_agent.data_loader import SiemensLoader
except ImportError:
    SiemensLoader = None

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
    logger.info("DIAGNOSTIC SPECIALIST (The Specialist) - Starting up...")
    logger.info("=" * 60)

    START_TIME = datetime.utcnow()

    try:
        lm_config = configure_dspy()
        app.state.router_lm = lm_config.router
        logger.info("DSPy configured: Router=GPT-4.1-nano, Reasoner=Claude-3.5-Haiku")
        app.state.dspy_ready = True
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        app.state.dspy_ready = False
        app.state.router_lm = None

    try:
        app.state.vector_store = DiagnosticSpecialistStore()
        doc_count = app.state.vector_store.get_document_count()
        logger.info(f"Vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        app.state.brain = DiagnosticSpecialistModule(router_lm=app.state.router_lm)
        logger.info("Brain module (DSPy) initialized")
    except Exception as e:
        logger.error(f"Failed to initialize brain: {e}")
        app.state.brain = None

    try:
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

    # Initialize Polars event log loader
    try:
        parquet_dir = os.getenv("PARQUET_DATA_DIR", "data/raw/siemens/eventlog_txt")
        if PARQUET_AVAILABLE:
            app.state.parquet_loader = LazyParquetLoader(parquet_dir)
            customers = app.state.parquet_loader.list_customers()
            logger.info(f"Polars event log loader ready: {len(customers)} customers available")
            app.state.parquet_ready = True
        else:
            logger.warning("Polars not available - event log queries disabled")
            app.state.parquet_loader = None
            app.state.parquet_ready = False
    except Exception as e:
        logger.warning(f"Parquet loader initialization failed: {e}")
        app.state.parquet_loader = None
        app.state.parquet_ready = False

    logger.info("=" * 60)
    logger.info("DIAGNOSTIC SPECIALIST (The Specialist) - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Diagnostic Specialist shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Diagnostic Specialist Agent",
    description=(
        "Agent 1: The Specialist - DICOM conformance diagnosis, MRI hardware error analysis, "
        "and technical specification lookup. Part of the 3-Agent MAS."
    ),
    version="2.0.0",
    lifespan=lifespan
)

configure_cors(app)


@app.get("/")
async def root():
    return {
        "agent": "Diagnostic Specialist",
        "role": "The Specialist (Agent 1)",
        "port": 8002,
        "status": "running",
        "capabilities": [
            "DICOM conformance failure diagnosis",
            "MRI hardware/software error analysis",
            "Technical specification lookup",
            "SOP Class UID cross-referencing"
        ],
        "endpoints": ["/health", "/consult", "/index"]
    }


@app.get("/health", response_model=AgentHealthStatus)
async def health_check():
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

        if vs_ready and dspy_ready:
            status = "healthy"
        elif vs_ready or dspy_ready:
            status = "degraded"
        else:
            status = "unhealthy"

        return AgentHealthStatus(
            agent_role=AgentRole.HARDWARE_AGENT,
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
            agent_role=AgentRole.HARDWARE_AGENT,
            status="unhealthy",
            vector_store_ready=False,
            dspy_ready=False,
            document_count=0,
            uptime_seconds=0.0
        )


def _determine_query_type(query: str) -> str:
    """Determine query type for routing to the appropriate DSPy signature."""
    query_lower = query.lower()

    # DICOM diagnosis indicators
    dicom_keywords = [
        'dicom', 'sop class', 'sop uid', 'transfer syntax', 'association',
        'pacs', 'storage commit', 'conformance', 'c-store', 'c-find',
        'c-move', 'worklist', 'mpps', 'modality worklist'
    ]
    if any(kw in query_lower for kw in dicom_keywords):
        return 'dicom_diagnosis'

    # Hardware error indicators
    hardware_keywords = [
        'error', 'fault', 'failure', 'crash', 'malfunction', 'broken',
        'gradient', 'rf amplifier', 'cryogen', 'helium', 'thermal',
        'cooling', 'quench', 'service', 'calibration', 'coil',
        'event log', 'error log', 'syngo'
    ]
    if any(kw in query_lower for kw in hardware_keywords):
        return 'hardware_error'

    # Technical specification indicators
    spec_keywords = [
        'specification', 'spec', 'model', 'xa50', 'xa51', 'xa60',
        'magnetom', 'sola', 'field strength', 'parameter', 'capability',
        'support', 'compatible', 'version', 'cspl', 'dcs'
    ]
    if any(kw in query_lower for kw in spec_keywords):
        return 'technical_spec'

    return 'general'


def _reclassify_from_evaluation(reasoning: str, query: str) -> str:
    """Reclassify query type using LLM evaluation reasoning when keywords return 'general'."""
    reasoning_lower = reasoning.lower()
    if any(kw in reasoning_lower for kw in ['dicom', 'conformance', 'sop class', 'transfer syntax']):
        return 'dicom_diagnosis'
    if any(kw in reasoning_lower for kw in ['hardware', 'gradient', 'cryogen', 'thermal', 'fault']):
        return 'hardware_error'
    if any(kw in reasoning_lower for kw in ['specification', 'capability', 'supported', 'feature']):
        return 'technical_spec'
    return 'general'


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """Primary consultation endpoint for The Specialist."""
    global LAST_QUERY_TIME
    start_time = time.time()

    try:
        card = request.card
        logger.info(f"Received consultation from {card.sender}: {card.intent}")

        try:
            validated_payload = ConsultPayload.from_payload(card.payload)
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid payload: {e.errors()}")

        query = validated_payload.query
        equipment_type = validated_payload.equipment_type or "MRI"
        customer_id = validated_payload.customer_id
        delegated_by = validated_payload.delegated_by

        if delegated_by:
            logger.info(f"Handling delegated request from {delegated_by}")

        if not app.state.vector_store:
            raise HTTPException(status_code=503, detail="Vector store not initialized")

        if not app.state.brain:
            raise HTTPException(status_code=503, detail="Brain module not initialized")

        # Retrieve relevant documents with actual relevance scores (k=8 + threshold filtering)
        doc_score_pairs = app.state.vector_store.similarity_search_with_score(query, k=8)
        documents = [doc for doc, _ in doc_score_pairs]
        doc_scores = {id(doc): score for doc, score in doc_score_pairs}

        vector_context = "\n\n".join([
            f"[{doc.metadata.get('data_type', 'technical')} | {doc.metadata.get('file_name', 'unknown')} | score:{score:.3f}]\n{doc.page_content}"
            for doc, score in doc_score_pairs
        ])

        if not vector_context:
            vector_context = "No relevant technical documentation found."

        # Try to extract customer_id from query if not explicitly provided
        if not customer_id and getattr(app.state, 'parquet_loader', None):
            import re
            match = re.search(r'mr\d{5,}', query.lower())
            if match:
                customer_id = match.group()
                logger.info(f"Extracted customer_id from query: {customer_id}")

        # Polars event log enrichment for customer-specific or event-log queries
        event_log_context = ""
        if customer_id and getattr(app.state, 'parquet_loader', None):
            try:
                summary = app.state.parquet_loader.get_error_summary(customer_id)
                if summary.get('source') != 'not_found':
                    event_log_context = f"\n\n--- Event Log Data ({customer_id}) ---\n{str(summary)[:4000]}"
                    logger.info(f"Event log context added for {customer_id}")
            except Exception as e:
                logger.warning(f"Event log enrichment failed: {e}")

        if event_log_context:
            vector_context += event_log_context

        # Knowledge Graph enrichment
        graph_context = ""
        if hasattr(app.state, 'graph_service') and app.state.graph_service:
            try:
                graph_context = app.state.graph_service.get_enriched_context(query=query, location=None)
                if graph_context:
                    logger.info(f"Graph context retrieved: {len(graph_context)} chars")
            except Exception as e:
                logger.warning(f"Graph context retrieval failed: {e}")

        context = f"{vector_context}\n\n--- Knowledge Graph Context ---\n{graph_context}" if graph_context else vector_context

        # Autonomy protocol: evaluate request (before routing, so reasoning can reclassify)
        context_summary = f"Retrieved {len(documents)} documents from vector store"
        if graph_context:
            context_summary += " + knowledge graph context"

        with dspy.context(lm=app.state.router_lm):
            evaluation = app.state.brain.evaluate_incoming_request(query=query, context_summary=context_summary)

        eval_confidence = float(getattr(evaluation, 'confidence_level', getattr(evaluation, 'confidence', 0.8)))
        eval_response_type = getattr(evaluation, 'response_type', 'answer')
        eval_suggested_agent = getattr(evaluation, 'suggested_agent', 'none')
        eval_reasoning = getattr(evaluation, 'reasoning', '')

        logger.info(f"Evaluation: confidence={eval_confidence}, response_type={eval_response_type}")

        # Determine query type with semantic fallback
        query_type = _determine_query_type(query)
        if query_type == 'general' and eval_reasoning:
            query_type = _reclassify_from_evaluation(eval_reasoning, query)
            if query_type != 'general':
                logger.info(f"Reclassified from 'general' to '{query_type}' via LLM reasoning")
        logger.info(f"Query type detected: {query_type}")

        # Process through DSPy brain (pass real event log context)
        result = app.state.brain(
            query=query,
            context=context,
            query_type=query_type,
            equipment_type=equipment_type,
            event_log_context=event_log_context
        )

        # Document references with actual similarity scores
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'specialist'),
                file_name=doc.metadata.get('file_name', 'unknown'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=round(1.0 - doc_scores.get(id(doc), 0.15), 4),
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Build response payload
        if query_type == "dicom_diagnosis":
            response_payload = {
                "diagnosis": getattr(result, 'diagnosis', 'Unable to determine'),
                "severity": getattr(result, 'severity', 'unknown'),
                "affected_component": getattr(result, 'affected_component', ''),
                "diagnostic_steps": getattr(result, 'diagnostic_steps', ''),
                "answer": getattr(result, 'answer', ''),
                "specialist_agent": "hardware_agent"
            }
            severity = getattr(result, 'severity', 'low')
            priority = Priority.CRITICAL if severity == 'critical' else (
                Priority.HIGH if severity == 'high' else Priority.NORMAL
            )
        elif query_type == "hardware_error":
            response_payload = {
                "diagnosis": getattr(result, 'diagnosis', 'Unable to determine'),
                "severity": getattr(result, 'severity', 'unknown'),
                "affected_component": getattr(result, 'affected_component', ''),
                "diagnostic_steps": getattr(result, 'diagnostic_steps', ''),
                "requires_service": getattr(result, 'requires_service', 'unknown'),
                "answer": getattr(result, 'answer', ''),
                "specialist_agent": "hardware_agent"
            }
            severity = getattr(result, 'severity', 'low')
            priority = Priority.CRITICAL if severity == 'critical' else (
                Priority.HIGH if severity == 'high' else Priority.NORMAL
            )
        elif query_type == "technical_spec":
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to find specification'),
                "source_document": getattr(result, 'source_document', ''),
                "confidence": getattr(result, 'confidence', 'low'),
                "specialist_agent": "hardware_agent"
            }
            priority = Priority.NORMAL
        else:
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to process query'),
                "confidence": getattr(result, 'confidence', 'medium'),
                "sources_used": getattr(result, 'sources_used', ''),
                "follow_up": getattr(result, 'follow_up', ''),
                "specialist_agent": "hardware_agent"
            }
            priority = Priority.NORMAL

        if delegated_by:
            response_payload["delegated_by"] = delegated_by
        if customer_id:
            response_payload["customer_id"] = customer_id

        # Map response type
        response_type_map = {
            'answer': ResponseType.ANSWER,
            'partial': ResponseType.PARTIAL,
            'clarify': ResponseType.CLARIFY,
            'redirect': ResponseType.REDIRECT,
            'refuse': ResponseType.REFUSE,
            'consult': ResponseType.CONSULT
        }
        response_type = response_type_map.get(str(eval_response_type).lower(), ResponseType.ANSWER)

        suggested_agent_map = {
            'governance_agent': AgentRole.GOVERNANCE_AGENT,
            'telemetry_agent': AgentRole.TELEMETRY_AGENT,
        }
        suggested_agent = suggested_agent_map.get(str(eval_suggested_agent).lower()) if eval_suggested_agent not in ['none', 'self'] else None

        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.HARDWARE_AGENT,
            recipient=card.sender,
            intent=IntentType.REPORT,
            priority=priority,
            payload=response_payload,
            documents=doc_refs,
            confidence=eval_confidence,
            response_type=response_type,
            suggested_agent=suggested_agent
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
            sender=AgentRole.HARDWARE_AGENT,
            recipient=request.card.sender,
            intent=IntentType.REPORT,
            priority=Priority.HIGH,
            payload={"error": str(e)},
            response_type=ResponseType.REFUSE
        )

        return ConsultResponse(
            success=False,
            response_card=error_card,
            processing_time_ms=processing_time,
            error=str(e)
        )


@app.post("/index")
async def index_documents(force_reindex: bool = False, use_legacy: bool = False):
    """Trigger vector store indexing."""
    try:
        logger.info("Starting document indexing...")

        if use_legacy and SiemensLoader:
            logger.info("Using legacy SiemensLoader")
            loader = SiemensLoader()
            documents = loader.load()
        else:
            logger.info("Using MRIHardwareLoader (DCS + error profiles)")
            loader = MRIHardwareLoader()
            documents = loader.load(include_pdfs=True)

        if not documents:
            return {"success": True, "message": "No documents found to index", "indexed_count": 0}

        if not app.state.vector_store:
            app.state.vector_store = DiagnosticSpecialistStore()

        count = app.state.vector_store.index_documents(documents, force_reindex=force_reindex)

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
    if not app.state.vector_store:
        return {"count": 0, "status": "vector_store_not_initialized"}
    count = app.state.vector_store.get_document_count()
    return {"count": count, "status": "ok"}


@app.get("/documents/search")
async def search_documents(query: str, k: int = 5):
    if not app.state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    documents = app.state.vector_store.similarity_search(query, k=k)

    return {
        "query": query,
        "results": [
            {"content": doc.page_content[:500], "metadata": doc.metadata}
            for doc in documents
        ]
    }


@app.get("/silo-audit")
async def silo_audit():
    """Return cognitive silo audit: collection stats and domain boundary verification."""
    if not app.state.vector_store:
        return {"error": "vector_store_not_initialized"}
    return app.state.vector_store.get_silo_audit()


@app.post("/event-logs/{customer_id}")
async def query_event_logs(
    customer_id: str,
    severity: Optional[str] = None,
    source_filter: Optional[str] = None,
    dicom_only: bool = False,
    limit: int = 100
):
    """
    Query MRI event logs for a specific customer via Polars LazyParquetLoader.

    Supports filtering by severity (E/W/I), source, and DICOM-specific errors.
    Optionally runs DSPy analysis on retrieved events.
    """
    if not getattr(app.state, 'parquet_loader', None):
        raise HTTPException(status_code=503, detail="Event log loader not available")

    loader = app.state.parquet_loader

    if not loader.has_parquet(customer_id):
        raise HTTPException(status_code=404, detail=f"No event logs found for {customer_id}")

    try:
        if dicom_only:
            df = loader.find_dicom_errors(customer_id=customer_id, limit=limit)
        else:
            df = loader.query_events_for_customer(
                customer_id=customer_id,
                severity=severity,
                source_filter=source_filter,
                limit=limit
            )

        if df is None or len(df) == 0:
            return {"customer_id": customer_id, "events": [], "count": 0}

        events = df.to_dicts()
        summary = loader.get_error_summary(customer_id)

        result = {
            "customer_id": customer_id,
            "events": events[:limit],
            "count": len(events),
            "summary": summary,
        }

        # Run DSPy analysis if brain is available and we have events
        if app.state.brain and len(events) > 0:
            try:
                # Get failure mode context from vector store
                fm_context = ""
                if app.state.vector_store:
                    fm_docs = app.state.vector_store.similarity_search(
                        f"failure mode {customer_id} errors", k=3
                    )
                    fm_context = "\n".join(d.page_content[:300] for d in fm_docs)

                analysis_result = app.state.brain.analyze_event_logs(
                    customer_id=customer_id,
                    event_data_summary=str(summary)[:2000],
                    known_failure_modes=fm_context or "No failure mode catalog available"
                )
                result["analysis"] = {
                    "analysis": getattr(analysis_result, 'analysis', ''),
                    "identified_issues": getattr(analysis_result, 'identified_issues', ''),
                    "failure_mode_matches": getattr(analysis_result, 'failure_mode_matches', ''),
                    "recommendations": getattr(analysis_result, 'recommendations', ''),
                }
            except Exception as e:
                logger.warning(f"Event log DSPy analysis failed: {e}")
                result["analysis"] = {"error": str(e)}

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event log query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    from src.agents.shared.server_utils import run_agent_server

    run_agent_server(
        app=app,
        agent_name="Diagnostic Specialist",
        env_var_name="SIEMENS_TECHNICIAN_PORT",
        default_port=8002
    )
