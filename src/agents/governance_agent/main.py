"""
Workflow Anthropologist - FastAPI Microservice (Port 8001)

Agent 2: "The Anthropologist" - Workflow & Context Expert responsible for:
- Institution profiling (academic vs private, volume, staffing)
- Workload pattern analysis (peak hours, bottlenecks, utilization)
- Error context explanation (WHY errors occur at specific institutions)
- Query delegation to Specialist and Auditor agents
- Findings integration (merge technical + operational context)

Supports BASELINE_MODE for single-agent evaluation (RQ2 comparison):
- When BASELINE_MODE=true: Uses unified vector store with ALL domain knowledge
- When BASELINE_MODE=false (default): Uses multi-agent delegation

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
import httpx

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from pydantic import ValidationError
from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority, ResponseType,
    ConsultRequest, ConsultResponse, AgentHealthStatus,
    DocumentReference, ConsultPayload
)
from src.agents.governance_agent.brain import WorkflowAnthropologistModule
from src.agents.governance_agent.clinical_governance_loader import ClinicalGovernanceLoader
from src.agents.governance_agent.vector_store import WorkflowAnthropologistStore
from src.agents.shared.dspy_config import configure_dspy
import dspy
from src.agents.shared.graph_service import get_graph_service
from src.agents.shared.security import configure_cors
from src.evaluation.diagnosis_logging import DiagnosisLog, DiagnosisLogger, RoundLog

# Backward compatibility imports
try:
    from src.agents.governance_agent.data_loader import TelekomLoader
except ImportError:
    TelekomLoader = None

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

# Baseline mode configuration
BASELINE_MODE = os.getenv("BASELINE_MODE", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global START_TIME

    # ==================== STARTUP ====================
    logger.info("=" * 60)
    if BASELINE_MODE:
        logger.info("WORKFLOW ANTHROPOLOGIST - Starting up in BASELINE MODE...")
        logger.info("Single-agent mode: Using unified vector store, NO delegation")
    else:
        logger.info("WORKFLOW ANTHROPOLOGIST (The Anthropologist) - Starting up...")
        logger.info("Multi-agent mode: Using domain-specific store WITH delegation")
    logger.info("=" * 60)

    START_TIME = datetime.utcnow()
    app.state.baseline_mode = BASELINE_MODE

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
        if BASELINE_MODE and BASELINE_AVAILABLE:
            logger.info("Initializing UNIFIED vector store (baseline mode)...")
            app.state.vector_store = UnifiedVectorStore()
            doc_count = app.state.vector_store.get_document_count()
            if doc_count == 0:
                logger.info("Unified store empty - indexing all domain documents...")
                doc_count = app.state.vector_store.index_documents(force_reindex=True)
            logger.info(f"Unified vector store ready: {doc_count} documents (all domains)")
        else:
            app.state.vector_store = WorkflowAnthropologistStore()
            doc_count = app.state.vector_store.get_document_count()
            logger.info(f"Anthropologist vector store ready: {doc_count} documents indexed")
        app.state.vs_ready = True
    except Exception as e:
        logger.error(f"Failed to initialize vector store: {e}")
        app.state.vector_store = None
        app.state.vs_ready = False

    try:
        app.state.brain = WorkflowAnthropologistModule(router_lm=app.state.router_lm)
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

    # Initialize diagnosis logger for reasoning chain capture
    app.state.diagnosis_logger = DiagnosisLogger()
    logger.info("Diagnosis logger initialized (logs/diagnosis/)")

    logger.info("=" * 60)
    logger.info("WORKFLOW ANTHROPOLOGIST (The Anthropologist) - Ready to serve!")
    logger.info("=" * 60)

    yield

    # ==================== SHUTDOWN ====================
    logger.info("Workflow Anthropologist shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Workflow Anthropologist Agent",
    description=(
        "Agent 2: The Anthropologist - Institution profiling, workload analysis, "
        "error context explanation, and specialist delegation. Part of the 3-Agent MAS."
    ),
    version="2.0.0",
    lifespan=lifespan
)

configure_cors(app)


def _determine_query_type(query: str, is_symptom: bool) -> str:
    """Determine query type for routing to the appropriate DSPy signature."""
    if is_symptom:
        return "symptom"
    query_lower = query.lower()
    workload_keywords = [
        'workload', 'utilization', 'peak', 'schedule', 'throughput',
        'bottleneck', 'capacity', 'patient volume', 'scan count',
        'idle time', 'overloaded', 'underutilized'
    ]
    if any(kw in query_lower for kw in workload_keywords):
        return "workload"
    return "general"


def _reclassify_from_evaluation(reasoning: str, query: str, is_symptom: bool) -> str:
    """Reclassify query type using LLM evaluation reasoning when keywords return 'general'."""
    if is_symptom:
        return 'symptom'
    reasoning_lower = reasoning.lower()
    if any(kw in reasoning_lower for kw in ['symptom', 'error', 'issue', 'problem', 'fault']):
        return 'symptom'
    if any(kw in reasoning_lower for kw in ['workload', 'utilization', 'schedule', 'peak']):
        return 'workload'
    return 'general'


@app.get("/")
async def root():
    return {
        "agent": "Workflow Anthropologist",
        "role": "The Anthropologist (Agent 2)",
        "port": 8001,
        "status": "running",
        "baseline_mode": BASELINE_MODE,
        "mode_description": "Single-agent (unified knowledge)" if BASELINE_MODE else "Multi-agent (delegation enabled)",
        "capabilities": [
            "Institution profiling",
            "Workload pattern analysis",
            "Error context explanation",
            "Specialist delegation",
            "Findings integration"
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
            agent_role=AgentRole.GOVERNANCE_AGENT,
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
            agent_role=AgentRole.GOVERNANCE_AGENT,
            status="unhealthy",
            vector_store_ready=False,
            dspy_ready=False,
            document_count=0,
            uptime_seconds=0.0
        )


@app.post("/consult", response_model=ConsultResponse)
async def consult(request: ConsultRequest):
    """Primary consultation endpoint for The Anthropologist."""
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
        location = validated_payload.location or "unknown"
        is_symptom = validated_payload.is_symptom
        customer_id = validated_payload.customer_id

        if not app.state.vector_store:
            raise HTTPException(status_code=503, detail="Vector store not initialized")

        if not app.state.brain:
            raise HTTPException(status_code=503, detail="Brain module not initialized")

        # Retrieve relevant documents with actual relevance scores (k=8 + threshold filtering)
        doc_score_pairs = app.state.vector_store.similarity_search_with_score(query, k=8)
        documents = [doc for doc, _ in doc_score_pairs]
        doc_scores = {id(doc): score for doc, score in doc_score_pairs}

        vector_context = "\n\n".join([
            f"[{doc.metadata.get('data_type', 'unknown')} | {doc.metadata.get('file_name', 'unknown')} | score:{score:.3f}]\n{doc.page_content}"
            for doc, score in doc_score_pairs
        ])

        if not vector_context:
            vector_context = "No relevant institution or workflow data found."

        # Knowledge Graph enrichment
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

        context = f"{vector_context}\n\n--- Knowledge Graph Context ---\n{graph_context}" if graph_context else vector_context

        # Autonomy protocol
        context_summary = f"Retrieved {len(documents)} documents from vector store"
        if graph_context:
            context_summary += " + knowledge graph context"

        with dspy.context(lm=app.state.router_lm):
            evaluation = app.state.brain.evaluate_incoming_request(query=query, context_summary=context_summary)

        eval_confidence = float(getattr(evaluation, 'confidence_level', getattr(evaluation, 'confidence', 0.8)))
        eval_response_type = getattr(evaluation, 'response_type', 'answer')
        eval_suggested_agent = getattr(evaluation, 'suggested_agent', 'none')
        eval_reasoning = getattr(evaluation, 'reasoning', '')

        logger.info(f"Evaluation: confidence={eval_confidence}, response_type={eval_response_type}, suggested={eval_suggested_agent}")

        # Determine query type with semantic fallback
        query_type = _determine_query_type(query, is_symptom)
        if query_type == 'general' and eval_reasoning:
            query_type = _reclassify_from_evaluation(eval_reasoning, query, is_symptom)
            if query_type != 'general':
                logger.info(f"Reclassified from 'general' to '{query_type}' via LLM reasoning")
        logger.info(f"Query type detected: {query_type}")

        # Process through DSPy brain
        result = app.state.brain(
            query=query,
            context=context,
            location=location,
            is_symptom=is_symptom,
            query_type=query_type
        )

        # Document references with actual similarity scores
        doc_refs = [
            DocumentReference(
                source=doc.metadata.get('source_type', 'anthropologist'),
                file_name=doc.metadata.get('file_name', 'unknown'),
                content_snippet=doc.page_content[:500] if doc.page_content else "",
                relevance_score=round(1.0 - doc_scores.get(id(doc), 0.15), 4),
                metadata=doc.metadata
            )
            for doc in documents
        ]

        # Extract delegation info
        target_agent = getattr(result, 'target_agent', 'self')
        delegation_reason = getattr(result, 'delegation_reason', '')
        refined_query = getattr(result, 'refined_query', query)

        # Build response payload based on query type
        if query_type == "symptom":
            response_payload = {
                "institution_profile": getattr(result, 'institution_profile', 'Unknown'),
                "contextual_explanation": getattr(result, 'contextual_explanation', ''),
                "risk_level": getattr(result, 'risk_level', 'unknown'),
                "risk_factors": getattr(result, 'risk_factors', 'None identified'),
                "recommended_actions": getattr(result, 'recommended_actions', 'No immediate actions'),
                "delegation": {
                    "target_agent": target_agent,
                    "reason": delegation_reason,
                    "refined_query": refined_query
                }
            }
            initial_risk = getattr(result, 'risk_level', 'low')
            priority = Priority.CRITICAL if initial_risk == 'critical' else (
                Priority.HIGH if initial_risk == 'high' else Priority.NORMAL
            )
        elif query_type == "workload":
            response_payload = {
                "workload_assessment": getattr(result, 'workload_assessment', ''),
                "peak_periods": getattr(result, 'peak_periods', ''),
                "bottleneck_analysis": getattr(result, 'bottleneck_analysis', ''),
                "optimization_suggestions": getattr(result, 'optimization_suggestions', ''),
                "answer": getattr(result, 'answer', ''),
                "delegation": {
                    "target_agent": target_agent,
                    "reason": delegation_reason,
                    "refined_query": refined_query
                }
            }
            priority = Priority.NORMAL
        else:
            # General query
            response_payload = {
                "answer": getattr(result, 'answer', ''),
                "confidence": getattr(result, 'confidence', 'medium'),
                "sources_used": getattr(result, 'sources_used', ''),
                "follow_up": getattr(result, 'follow_up', ''),
                "delegation": {
                    "target_agent": target_agent,
                    "reason": delegation_reason,
                    "refined_query": refined_query
                }
            }
            priority = Priority.NORMAL

        if customer_id:
            response_payload["customer_id"] = customer_id

        # Delegation logic
        if BASELINE_MODE:
            if target_agent and target_agent != 'self':
                logger.info(f"BASELINE MODE: Would delegate to {target_agent}, answering directly")
                response_payload["delegation"]["skipped"] = True
                response_payload["delegation"]["reason"] = "Baseline mode - single agent"
        elif target_agent and target_agent != 'self':
            agents_involved = [target_agent]
            logger.info(f"Delegating to {target_agent}...")
            specialist_response = await delegate_to_specialist(target_agent, refined_query, card.message_id)
            if specialist_response:
                response_payload["specialist_findings"] = specialist_response
                logger.info(f"Specialist {target_agent} response received")

                # Multi-hop: check if second specialist needed
                second_specialist_response = None
                if target_agent == 'hardware_agent' and _needs_safety_review(query, specialist_response):
                    logger.info("Multi-hop: hardware response needs safety review, consulting telemetry_agent...")
                    second_specialist_response = await delegate_to_specialist(
                        'telemetry_agent', f"Safety review: {refined_query}", card.message_id
                    )
                    if second_specialist_response:
                        agents_involved.append('telemetry_agent')
                        response_payload["second_specialist_findings"] = second_specialist_response
                        logger.info("Second specialist (telemetry_agent) response received")
                elif target_agent == 'telemetry_agent' and _needs_hardware_context(query, specialist_response):
                    logger.info("Multi-hop: safety response needs hardware context, consulting hardware_agent...")
                    second_specialist_response = await delegate_to_specialist(
                        'hardware_agent', f"Technical context: {refined_query}", card.message_id
                    )
                    if second_specialist_response:
                        agents_involved.append('hardware_agent')
                        response_payload["second_specialist_findings"] = second_specialist_response
                        logger.info("Second specialist (hardware_agent) response received")

                response_payload["agents_involved"] = agents_involved

                # Integrate all specialist findings
                try:
                    # Combine findings from both specialists if multi-hop
                    combined_findings = specialist_response
                    if second_specialist_response:
                        combined_findings = {
                            "primary": specialist_response,
                            "secondary": second_specialist_response,
                            "response_card": specialist_response.get("response_card", {}),
                        }

                    integration_result = app.state.brain.integrate_specialist_response(
                        query=query,
                        minister_assessment={
                            "institution_profile": response_payload.get("institution_profile", "unknown"),
                            "risk_factors": response_payload.get("risk_factors", "None"),
                            "contextual_explanation": response_payload.get("contextual_explanation", "None")
                        },
                        specialist_findings=combined_findings,
                        specialist_agent=", ".join(agents_involved)
                    )

                    response_payload["risk_level"] = integration_result.integrated_risk_level
                    response_payload["root_cause"] = integration_result.root_cause_summary
                    response_payload["recommended_actions"] = integration_result.integrated_actions
                    response_payload["integration_performed"] = True

                    integrated_risk = integration_result.integrated_risk_level.lower()
                    if integrated_risk == 'critical':
                        priority = Priority.CRITICAL
                    elif integrated_risk == 'high':
                        priority = Priority.HIGH

                    logger.info(f"Specialist findings integrated ({len(agents_involved)} agents involved)")
                except Exception as e:
                    logger.warning(f"Integration step failed: {e}")
                    response_payload["integration_performed"] = False
            else:
                logger.warning(f"Delegation to {target_agent} returned no response")
                response_payload["specialist_findings"] = {
                    "error": f"Specialist {target_agent} unavailable"
                }
                response_payload["agents_involved"] = [target_agent]

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

        if target_agent and target_agent != 'self' and 'specialist_findings' in response_payload:
            response_type = ResponseType.CONSULT

        suggested_agent_map = {
            'hardware_agent': AgentRole.HARDWARE_AGENT,
            'telemetry_agent': AgentRole.TELEMETRY_AGENT,
        }
        suggested_agent = suggested_agent_map.get(str(eval_suggested_agent).lower()) if eval_suggested_agent not in ['none', 'self'] else None

        response_card = AgentCard(
            correlation_id=card.message_id,
            sender=AgentRole.GOVERNANCE_AGENT,
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

        # Capture reasoning chain log
        try:
            import uuid as _uuid
            diag_log = DiagnosisLog(
                session_id=card.message_id or str(_uuid.uuid4()),
                mode="mas_full" if (target_agent and target_agent != 'self') else "governance_only",
                original_query=query,
                query_metadata={"customer_id": customer_id, "location": location, "is_symptom": is_symptom},
                final_diagnosis=response_payload.get("contextual_explanation", response_payload.get("answer", "")),
            )
            diag_log.add_round(RoundLog(
                round_number=0,
                agent="governance_agent",
                response_type=str(eval_response_type),
                confidence=eval_confidence,
                findings_summary=str(response_payload.get("contextual_explanation", response_payload.get("answer", "")))[:500],
                latency_ms=processing_time,
            ))
            if target_agent and target_agent != 'self' and 'specialist_findings' in response_payload:
                spec = response_payload.get("specialist_findings", {})
                spec_card = spec.get("response_card", {})
                spec_conf = spec_card.get("confidence", 0.7)
                spec_rt = spec_card.get("response_type", "answer")
                spec_payload = spec_card.get("payload", {})
                diag_log.add_round(RoundLog(
                    round_number=1,
                    agent=target_agent,
                    response_type=str(spec_rt),
                    confidence=float(spec_conf) if spec_conf else 0.7,
                    findings_summary=str(spec_payload.get("diagnosis", spec_payload.get("answer", "")))[:500],
                    latency_ms=spec.get("processing_time_ms", 0),
                ))
            # Log second specialist round if multi-hop occurred
            if 'second_specialist_findings' in response_payload:
                sec_spec = response_payload.get("second_specialist_findings", {})
                sec_card = sec_spec.get("response_card", {})
                sec_conf = sec_card.get("confidence", 0.7)
                sec_rt = sec_card.get("response_type", "answer")
                sec_payload = sec_card.get("payload", {})
                sec_agent = response_payload.get("agents_involved", ["", ""])[1] if len(response_payload.get("agents_involved", [])) > 1 else "unknown"
                diag_log.add_round(RoundLog(
                    round_number=2,
                    agent=sec_agent,
                    response_type=str(sec_rt),
                    confidence=float(sec_conf) if sec_conf else 0.7,
                    findings_summary=str(sec_payload.get("diagnosis", sec_payload.get("answer", "")))[:500],
                    latency_ms=sec_spec.get("processing_time_ms", 0),
                ))
            diag_log.termination_reason = "delegation_complete" if target_agent and target_agent != 'self' else "single_agent"
            # Add visualization data to response
            response_payload["reasoning_chain_visualization"] = diag_log.to_visualization_data()
            if hasattr(app.state, 'diagnosis_logger'):
                app.state.diagnosis_logger.save_log(diag_log)
        except Exception as log_err:
            logger.warning(f"Diagnosis logging failed (non-critical): {log_err}")

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
            sender=AgentRole.GOVERNANCE_AGENT,
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


async def delegate_to_specialist(target: str, query: str, correlation_id: str):
    """Delegate a query to a specialist agent (The Specialist or The Auditor)."""
    hardware_url = os.getenv("SIEMENS_TECHNICIAN_URL", "http://localhost:8002")
    telemetry_url = os.getenv("ILLIGO_OPERATOR_URL", "http://localhost:8003")

    agent_urls = {
        "hardware_agent": f"{hardware_url}/consult",
        "telemetry_agent": f"{telemetry_url}/consult",
        # Legacy aliases
        "siemens_technician": f"{hardware_url}/consult",
        "illigo_operator": f"{telemetry_url}/consult",
    }

    if target not in agent_urls:
        logger.warning(f"Unknown delegation target: {target}")
        return None

    target_role = (
        AgentRole.HARDWARE_AGENT if target in ("hardware_agent", "siemens_technician")
        else AgentRole.TELEMETRY_AGENT
    )

    delegation_card = AgentCard(
        correlation_id=correlation_id,
        sender=AgentRole.GOVERNANCE_AGENT,
        recipient=target_role,
        intent=IntentType.DELEGATE,
        priority=Priority.HIGH,
        payload={
            "query": query,
            "delegated_by": "governance_agent"
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


def _needs_safety_review(query: str, specialist_findings: dict) -> bool:
    """Check if a hardware specialist response also needs safety/compliance review."""
    safety_keywords = ['zone', 'safety', 'compliance', 'screening', 'personnel',
                       'sop', 'quench', 'ferromagnetic', 'acr', 'recalibrate',
                       'maintenance', 'service', 'intervention']
    if any(kw in query.lower() for kw in safety_keywords):
        return True
    if specialist_findings:
        spec_payload = specialist_findings.get('response_card', {}).get('payload', {})
        spec_text = str(spec_payload.get('diagnostic_steps', '')) + str(spec_payload.get('diagnosis', ''))
        if any(kw in spec_text.lower() for kw in ['recalibrate', 'replace', 'service', 'zone']):
            return True
    return False


def _needs_hardware_context(query: str, specialist_findings: dict) -> bool:
    """Check if a safety/compliance response also needs hardware technical context."""
    hw_keywords = ['dicom', 'gradient', 'coil', 'cryogen', 'helium', 'thermal',
                   'error', 'fault', 'failure', 'event log', 'rf', 'amplifier']
    return any(kw in query.lower() for kw in hw_keywords)


@app.post("/index")
async def index_documents(force_reindex: bool = False, use_legacy: bool = False):
    """Trigger vector store indexing."""
    try:
        logger.info("Starting document indexing...")

        if use_legacy and TelekomLoader:
            logger.info("Using legacy TelekomLoader")
            loader = TelekomLoader()
            documents = loader.load()
        else:
            logger.info("Using ClinicalGovernanceLoader (institution profiles + feedback)")
            loader = ClinicalGovernanceLoader()
            documents = loader.load()

        if not documents:
            return {"success": True, "message": "No documents found to index", "indexed_count": 0}

        if not app.state.vector_store:
            app.state.vector_store = WorkflowAnthropologistStore()

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
        agent_name="Workflow Anthropologist",
        env_var_name="TELEKOM_MINISTER_PORT",
        default_port=8001
    )
