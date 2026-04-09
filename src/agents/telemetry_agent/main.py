"""
Safety Auditor - FastAPI Microservice (Port 8003)

Agent 3: "The Auditor" - Safety & Compliance Expert responsible for:
- SOP compliance validation for proposed actions/workflow changes
- Safety review of diagnostic actions from Agent 1 (The Specialist)
- MRI safety zone compliance checking (Zone I-IV)
- Workflow change auditing for regulatory compliance

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
from src.agents.telemetry_agent.brain import SafetyAuditorModule
from src.agents.telemetry_agent.mri_data_loader import MRITelemetryLoader
from src.agents.telemetry_agent.vector_store import SafetyAuditorStore
from src.agents.shared.dspy_config import configure_dspy
import dspy
from src.agents.shared.graph_service import get_graph_service
from src.agents.shared.security import configure_cors

# Backward compatibility imports
try:
    from src.agents.telemetry_agent.data_loader import IlligoLoader
except ImportError:
    IlligoLoader = None

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
    logger.info("SAFETY AUDITOR (The Auditor) - Starting up...")
    logger.info("=" * 60)

    START_TIME = datetime.utcnow()

    try:
        lm_config = configure_dspy()
        app.state.router_lm = lm_config.router
        logger.info("DSPy configured: Router=GPT-4.1-nano, Reasoner=Claude-Haiku-4.5")
        app.state.dspy_ready = True
    except Exception as e:
        logger.error(f"Failed to configure DSPy: {e}")
        app.state.dspy_ready = False
        app.state.router_lm = None

    try:
        app.state.vector_store = SafetyAuditorStore()
        doc_count = app.state.vector_store.get_document_count()
        if doc_count == 0:
            logger.info("Vector store empty - auto-indexing telemetry documents...")
            try:
                loader = MRITelemetryLoader()
                documents = loader.load(include_pdfs=True)
                if documents:
                    doc_count = app.state.vector_store.index_documents(documents)
                    logger.info(f"Auto-indexed {doc_count} telemetry documents")
                else:
                    logger.warning("No telemetry documents found to auto-index")
            except Exception as idx_err:
                logger.error(f"Auto-indexing failed: {idx_err}")
        logger.info(f"Vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        app.state.brain = SafetyAuditorModule(router_lm=app.state.router_lm)
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

    logger.info("=" * 60)
    logger.info("SAFETY AUDITOR (The Auditor) - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Safety Auditor shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Safety Auditor Agent",
    description=(
        "Agent 3: The Auditor - MRI safety compliance, SOP validation, "
        "safety zone management, and regulatory auditing. Part of the 3-Agent MAS."
    ),
    version="2.0.0",
    lifespan=lifespan
)

configure_cors(app)


@app.get("/")
async def root():
    return {
        "agent": "Safety Auditor",
        "role": "The Auditor (Agent 3)",
        "port": 8003,
        "status": "running",
        "capabilities": [
            "SOP compliance validation",
            "Diagnostic action safety review",
            "MRI safety zone compliance (Zone I-IV)",
            "Workflow change auditing"
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
            agent_role=AgentRole.TELEMETRY_AGENT,
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
            agent_role=AgentRole.TELEMETRY_AGENT,
            status="unhealthy",
            vector_store_ready=False,
            dspy_ready=False,
            document_count=0,
            uptime_seconds=0.0
        )


def _determine_query_type(query: str) -> str:
    """Determine query type for routing to the appropriate DSPy signature."""
    query_lower = query.lower()

    # Compliance check indicators
    compliance_keywords = [
        'compliant', 'compliance', 'sop', 'procedure', 'regulation',
        'standard', 'requirement', 'policy', 'guideline', 'protocol',
        'acr', 'appropriateness'
    ]
    if any(kw in query_lower for kw in compliance_keywords):
        return 'compliance_check'

    # Action review indicators (from Agent 1)
    review_keywords = [
        'review', 'approve', 'safe to', 'can we', 'is it safe',
        'diagnostic action', 'proposed action', 'intervention',
        'calibrate', 'recalibrate', 'service', 'maintenance'
    ]
    if any(kw in query_lower for kw in review_keywords):
        return 'action_review'

    # Safety zone indicators
    zone_keywords = [
        'zone', 'zone i', 'zone ii', 'zone iii', 'zone iv',
        'magnet room', 'control room', 'access', 'screening',
        'ferromagnetic', 'quench', 'restricted area'
    ]
    if any(kw in query_lower for kw in zone_keywords):
        return 'safety_zone'

    # Workflow audit indicators (from Agent 2)
    audit_keywords = [
        'workflow', 'schedule', 'staffing', 'training',
        'audit', 'change', 'optimize', 'reduce', 'increase',
        'patient flow', 'throughput'
    ]
    if any(kw in query_lower for kw in audit_keywords):
        return 'workflow_audit'

    return 'general'


def _reclassify_from_evaluation(reasoning: str, query: str) -> str:
    """Reclassify query type using LLM evaluation reasoning when keywords return 'general'."""
    reasoning_lower = reasoning.lower()
    if any(kw in reasoning_lower for kw in ['compliance', 'sop', 'regulation', 'procedure']):
        return 'compliance_check'
    if any(kw in reasoning_lower for kw in ['review', 'safe', 'approve', 'intervention']):
        return 'action_review'
    if any(kw in reasoning_lower for kw in ['zone', 'magnet room', 'access', 'screening']):
        return 'safety_zone'
    if any(kw in reasoning_lower for kw in ['workflow', 'schedule', 'staffing', 'audit']):
        return 'workflow_audit'
    return 'general'


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """Primary consultation endpoint for The Auditor."""
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
        station_id = validated_payload.station_id or "unknown"
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
            f"[{doc.metadata.get('data_type', 'safety')} | {doc.metadata.get('file_name', 'unknown')} | score:{score:.3f}]\n{doc.page_content}"
            for doc, score in doc_score_pairs
        ])

        if not vector_context:
            vector_context = "No relevant safety documentation found."

        # Knowledge Graph enrichment
        graph_context = ""
        if hasattr(app.state, 'graph_service') and app.state.graph_service:
            try:
                graph_context = app.state.graph_service.get_enriched_context(
                    query=query,
                    location=station_id if station_id != "unknown" else None
                )
                if graph_context:
                    logger.info(f"Graph context retrieved: {len(graph_context)} chars")
            except Exception as e:
                logger.warning(f"Graph context retrieval failed: {e}")

        context = f"{vector_context}\n\n--- Knowledge Graph Context ---\n{graph_context}" if graph_context else vector_context

        # Retrieve safety zone definitions separately for richer context
        safety_zone_context = ""
        try:
            zone_docs = app.state.vector_store.similarity_search(
                "safety zone definitions Zone I II III IV access requirements personnel", k=3
            )
            if zone_docs:
                safety_zone_context = "\n\n".join([doc.page_content for doc in zone_docs])
                logger.info(f"Safety zone context retrieved: {len(safety_zone_context)} chars")
        except Exception as e:
            logger.warning(f"Safety zone context retrieval failed: {e}")

        # Autonomy protocol (before routing, so reasoning can reclassify)
        context_summary = f"Retrieved {len(documents)} documents from vector store"
        if graph_context:
            context_summary += " + knowledge graph context"

        with dspy.context(lm=app.state.router_lm):
            evaluation = app.state.brain.evaluate_incoming_request(query=query, context_summary=context_summary)

        _raw_conf = getattr(evaluation, 'confidence_level', None) or getattr(evaluation, 'confidence', None)
        try:
            eval_confidence = float(_raw_conf) if _raw_conf is not None else 0.8
        except (TypeError, ValueError):
            eval_confidence = 0.8
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

        # Process through DSPy brain (pass real safety zone context)
        result = app.state.brain(
            query=query,
            context=context,
            query_type=query_type,
            station_id=station_id,
            safety_zone_context=safety_zone_context
        )

        # Document references with actual similarity scores
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'auditor'),
                file_name=doc.metadata.get('file_name', 'safety_doc'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=round(max(0.0, 1.0 - doc_scores.get(id(doc), 0.15)), 4),
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Build response payload
        if query_type == "compliance_check":
            response_payload = {
                "is_compliant": getattr(result, 'is_compliant', 'needs-review') or 'needs-review',
                "compliance_details": getattr(result, 'compliance_details', '') or '',
                "safety_concerns": getattr(result, 'safety_concerns', '') or '',
                "required_personnel": getattr(result, 'required_personnel', '') or '',
                "answer": getattr(result, 'answer', '') or '',
                "specialist_agent": "telemetry_agent"
            }
            compliance = getattr(result, 'is_compliant', 'needs-review') or 'needs-review'
            priority = Priority.HIGH if compliance == 'non-compliant' else Priority.NORMAL
        elif query_type == "action_review":
            response_payload = {
                "safety_assessment": getattr(result, 'safety_assessment', 'unknown') or 'unknown',
                "sop_compliance": getattr(result, 'sop_compliance', '') or '',
                "personnel_requirements": getattr(result, 'personnel_requirements', '') or '',
                "safety_checklist": getattr(result, 'safety_checklist', '') or '',
                "answer": getattr(result, 'answer', '') or '',
                "specialist_agent": "telemetry_agent"
            }
            assessment = getattr(result, 'safety_assessment', 'caution') or 'caution'
            priority = Priority.CRITICAL if assessment == 'unsafe' else (
                Priority.HIGH if assessment == 'caution' else Priority.NORMAL
            )
        elif query_type == "safety_zone":
            response_payload = {
                "zone_classification": getattr(result, 'zone_classification', '') or '',
                "access_requirements": getattr(result, 'access_requirements', '') or '',
                "screening_requirements": getattr(result, 'screening_requirements', '') or '',
                "restrictions": getattr(result, 'restrictions', '') or '',
                "answer": getattr(result, 'answer', '') or '',
                "specialist_agent": "telemetry_agent"
            }
            priority = Priority.HIGH  # Zone queries are always important
        elif query_type == "workflow_audit":
            response_payload = {
                "audit_result": getattr(result, 'audit_result', 'needs-review') or 'needs-review',
                "safety_gaps": getattr(result, 'safety_gaps', '') or '',
                "training_requirements": getattr(result, 'training_requirements', '') or '',
                "documentation_requirements": getattr(result, 'documentation_requirements', '') or '',
                "answer": getattr(result, 'answer', '') or '',
                "specialist_agent": "telemetry_agent"
            }
            audit = getattr(result, 'audit_result', 'conditionally-approved') or 'conditionally-approved'
            priority = Priority.HIGH if audit == 'rejected' else Priority.NORMAL
        else:
            response_payload = {
                "answer": getattr(result, 'answer', 'Unable to process query') or 'Unable to process query',
                "confidence": getattr(result, 'confidence', 'medium') or 'medium',
                "sources_used": getattr(result, 'sources_used', '') or '',
                "follow_up": getattr(result, 'follow_up', '') or '',
                "specialist_agent": "telemetry_agent"
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
            'hardware_agent': AgentRole.HARDWARE_AGENT,
        }
        suggested_agent = suggested_agent_map.get(str(eval_suggested_agent).lower()) if eval_suggested_agent not in ['none', 'self'] else None

        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.TELEMETRY_AGENT,
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
            sender=AgentRole.TELEMETRY_AGENT,
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

        if use_legacy and IlligoLoader:
            logger.info("Using legacy IlligoLoader")
            loader = IlligoLoader()
            documents = loader.load()
        else:
            logger.info("Using MRITelemetryLoader (safety procedures + zones)")
            loader = MRITelemetryLoader()
            documents = loader.load(include_pdfs=True)

        if not documents:
            return {"success": True, "message": "No documents found to index", "indexed_count": 0}

        if not app.state.vector_store:
            app.state.vector_store = SafetyAuditorStore()

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


if __name__ == "__main__":
    from src.agents.shared.server_utils import run_agent_server

    run_agent_server(
        app=app,
        agent_name="Safety Auditor",
        env_var_name="ILLIGO_OPERATOR_PORT",
        default_port=8003
    )
