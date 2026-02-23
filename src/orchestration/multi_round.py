"""
Multi-Round Orchestration - Emergence-Enabling Dialogue Protocol

Implements the multi-round dialogue protocol from design doc section 4.
Manages state across rounds, handles all response types, and enables
emergent diagnosis through agent consultation.

Flow:
    User → Governance → Specialist A → (CONSULT) → Specialist B → Synthesis → User

Per design doc section 4 - Multi-Round Dialogue Protocol.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import httpx

from src.protocol.schema import (
    AgentResponse,
    DiagnosisSession,
    ResponseType,
    AgentCard,
    AgentRole,
    IntentType,
    Priority
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiRoundOrchestrator:
    """
    Orchestrates multi-round agent dialogue for emergent diagnosis.

    Implements the protocol:
    1. Max 4 rounds to prevent infinite loops
    2. Governance orchestrates - always returns between specialist calls
    3. Accumulating context - each round adds to shared understanding
    4. Termination on: confidence >= 0.8, max rounds, or all consulted
    """

    # Default agent URLs
    DEFAULT_URLS = {
        'governance_agent': 'http://localhost:8001',
        'hardware_agent': 'http://localhost:8002',
        'telemetry_agent': 'http://localhost:8003'
    }

    # Agent expertise descriptions for context
    AGENT_EXPERTISE = {
        'governance_agent': 'SLA compliance, network intent, governance policies, uptime requirements',
        'hardware_agent': 'MRI hardware, Siemens equipment, temperature sensors, thermal management, Phoenix Protocol',
        'telemetry_agent': 'MRI event logs, session monitoring, temporal patterns, idle times, fault cycles'
    }

    def __init__(
        self,
        governance_url: str = None,
        hardware_url: str = None,
        telemetry_url: str = None,
        confidence_threshold: float = 0.8,
        max_rounds: int = 4,
        timeout_seconds: float = 120.0
    ):
        """
        Initialize orchestrator with agent URLs.

        Args:
            governance_url: URL for governance agent (default: localhost:8001)
            hardware_url: URL for hardware agent (default: localhost:8002)
            telemetry_url: URL for telemetry agent (default: localhost:8003)
            confidence_threshold: Confidence level to terminate (default: 0.8)
            max_rounds: Maximum dialogue rounds (default: 4)
            timeout_seconds: HTTP request timeout (default: 30)
        """
        self.agent_urls = {
            'governance_agent': governance_url or self.DEFAULT_URLS['governance_agent'],
            'hardware_agent': hardware_url or self.DEFAULT_URLS['hardware_agent'],
            'telemetry_agent': telemetry_url or self.DEFAULT_URLS['telemetry_agent']
        }
        self.confidence_threshold = confidence_threshold
        self.max_rounds = max_rounds
        self.timeout = timeout_seconds

    async def _call_agent(
        self,
        agent_id: str,
        query: str,
        context: str = "",
        is_consultation: bool = False
    ) -> Tuple[AgentResponse, float]:
        """
        Call an agent's /consult endpoint.

        Args:
            agent_id: Agent to call
            query: Query or symptom
            context: Accumulated context from previous rounds
            is_consultation: Whether this is a CONSULT request

        Returns:
            Tuple of (AgentResponse, latency_ms)
        """
        url = f"{self.agent_urls[agent_id]}/consult"
        start_time = time.time()

        # Build request card
        # Note: ConsultPayload.context is Dict[str, Any], so wrap the context string
        card = AgentCard(
            sender=AgentRole.ORCHESTRATOR,
            recipient=AgentRole(agent_id),
            intent=IntentType.DIAGNOSE if not is_consultation else IntentType.QUERY,
            priority=Priority.HIGH,
            payload={
                'query': f"{query}\n\nContext:\n{context}" if context else query,
                'context': {
                    'accumulated_context': context,
                    'is_consultation': is_consultation,
                    'expertise_needed': self.AGENT_EXPERTISE.get(agent_id, '')
                }
            }
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json={'card': card.model_dump(), 'await_response': True}
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Extract response from card
            response_card = data.get('response_card', {})
            payload = response_card.get('payload', {})

            # Map to AgentResponse
            agent_response = AgentResponse(
                response_type=ResponseType(response_card.get('response_type', 'answer')),
                confidence=response_card.get('confidence', 0.5),
                findings=payload.get('answer', payload.get('diagnosis', '')),
                reasoning=payload.get('reasoning', ''),
                suggested_agent=response_card.get('suggested_agent'),
                missing_information=payload.get('missing_info', ''),
                clarification_questions=payload.get('clarification_questions', []),
                consultation_reason=payload.get('consultation_reason', ''),
                agent_id=agent_id,
                round_number=0,  # Will be set by caller
                timestamp=datetime.utcnow()
            )

            return agent_response, latency_ms

        except Exception as e:
            logger.error(f"Error calling agent {agent_id}: {e}")
            latency_ms = (time.time() - start_time) * 1000

            # Return error response
            return AgentResponse(
                response_type=ResponseType.REFUSE,
                confidence=0.0,
                findings=None,
                reasoning=f"Agent communication error: {str(e)}",
                agent_id=agent_id,
                round_number=0,
                timestamp=datetime.utcnow()
            ), latency_ms

    def _get_unconsulted_agents(self, session: DiagnosisSession) -> List[str]:
        """Get list of agents not yet consulted."""
        all_agents = set(self.agent_urls.keys())
        consulted = set(session.agents_consulted)
        return list(all_agents - consulted)

    def _build_context(self, session: DiagnosisSession) -> str:
        """Build accumulated context from session history."""
        context_parts = [
            f"Original Query: {session.original_query}",
            f"Round: {session.current_round + 1} of {session.max_rounds}",
            ""
        ]

        if session.reasoning_chain:
            context_parts.append("Accumulated Findings:")
            for reasoning in session.reasoning_chain:
                context_parts.append(f"  {reasoning}")
            context_parts.append("")

        if session.agent_responses:
            context_parts.append("Previous Agent Responses:")
            for resp in session.agent_responses[-3:]:  # Last 3 responses
                context_parts.append(
                    f"  - {resp.agent_id}: {resp.findings[:200] if resp.findings else 'No findings'}..."
                )

        return '\n'.join(context_parts)

    async def orchestrate_round(
        self,
        session: DiagnosisSession,
        latest_response: AgentResponse
    ) -> DiagnosisSession:
        """
        Main orchestration logic for a single round.

        Handles all response types per design doc section 4:
        - ANSWER with high confidence → finalize
        - CONSULT → delegate to suggested agent
        - PARTIAL → try unconsulted agents
        - CLARIFY → request user clarification
        - REDIRECT → route to suggested agent
        - REFUSE → try other agents or synthesize

        Args:
            session: Current diagnosis session
            latest_response: Response from last agent call

        Returns:
            Updated session
        """
        logger.info(
            f"Orchestrating round {session.current_round + 1}: "
            f"response_type={latest_response.response_type}, "
            f"confidence={latest_response.confidence}"
        )

        # Hard termination check — must come first to prevent infinite recursion
        if session.current_round >= session.max_rounds:
            latest_response.round_number = session.current_round
            session.add_agent_response(latest_response)
            return self._synthesize_best_effort(session)

        # Add response to session
        latest_response.round_number = session.current_round
        session.add_agent_response(latest_response)

        unconsulted = self._get_unconsulted_agents(session)

        # Check for high-confidence answer
        if latest_response.response_type == ResponseType.ANSWER:
            if latest_response.confidence >= self.confidence_threshold:
                return self._finalize_diagnosis(session)
            # Low confidence answer - try to get more input
            if unconsulted:
                session.current_round += 1
                context = self._build_context(session)
                next_response, _ = await self._call_agent(
                    unconsulted[0],
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            else:
                return self._finalize_diagnosis(session)

        # CONSULT - agent wants peer input (critical for emergence)
        elif latest_response.response_type == ResponseType.CONSULT:
            suggested = latest_response.suggested_agent
            # Only consult if the suggested agent hasn't been consulted yet
            if suggested and suggested in self.agent_urls and suggested not in session.agents_consulted:
                session.current_round += 1
                context = self._build_context(session)
                context += f"\n\nConsultation requested by {latest_response.agent_id}: {latest_response.consultation_reason}"

                logger.info(f"CONSULT: {latest_response.agent_id} -> {suggested}")
                next_response, _ = await self._call_agent(
                    suggested,
                    session.original_query,
                    context,
                    is_consultation=True
                )
                return await self.orchestrate_round(session, next_response)
            elif unconsulted:
                # Suggested agent already consulted, try another unconsulted agent
                session.current_round += 1
                context = self._build_context(session)
                next_response, _ = await self._call_agent(
                    unconsulted[0],
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            else:
                return self._synthesize_partial_findings(session)

        # PARTIAL - agent has some info but not complete
        elif latest_response.response_type == ResponseType.PARTIAL:
            if unconsulted:
                session.current_round += 1
                context = self._build_context(session)
                context += f"\n\nPartial findings: {latest_response.findings}"
                context += f"\nMissing: {latest_response.missing_information}"

                next_response, _ = await self._call_agent(
                    unconsulted[0],
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            else:
                return self._synthesize_partial_findings(session)

        # CLARIFY - need user input
        elif latest_response.response_type == ResponseType.CLARIFY:
            return self._request_user_clarification(session, latest_response)

        # REDIRECT - wrong agent for this query
        elif latest_response.response_type == ResponseType.REDIRECT:
            suggested = latest_response.suggested_agent
            if suggested and suggested in self.agent_urls and suggested not in session.agents_consulted:
                session.current_round += 1
                context = self._build_context(session)

                logger.info(f"REDIRECT: {latest_response.agent_id} -> {suggested}")
                next_response, _ = await self._call_agent(
                    suggested,
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            elif unconsulted:
                session.current_round += 1
                context = self._build_context(session)
                next_response, _ = await self._call_agent(
                    unconsulted[0],
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            else:
                return self._synthesize_best_effort(session)

        # REFUSE - agent cannot help
        elif latest_response.response_type == ResponseType.REFUSE:
            if unconsulted:
                session.current_round += 1
                context = self._build_context(session)
                next_response, _ = await self._call_agent(
                    unconsulted[0],
                    session.original_query,
                    context
                )
                return await self.orchestrate_round(session, next_response)
            else:
                return self._synthesize_best_effort(session)

        # Fallback: if no branch handled finalization, synthesize
        return self._synthesize_best_effort(session)

    def _finalize_diagnosis(self, session: DiagnosisSession) -> DiagnosisSession:
        """Finalize session with high-confidence answer."""
        session.is_complete = True
        session.termination_reason = "confidence_reached"

        # Synthesize final diagnosis from responses
        findings = []
        for resp in session.agent_responses:
            if resp.findings:
                findings.append(f"{resp.agent_id}: {resp.findings}")

        session.final_diagnosis = "\n".join(findings)
        session.recommended_actions = self._extract_actions(session)

        logger.info(f"Session finalized: {session.termination_reason}")
        return session

    def _synthesize_partial_findings(self, session: DiagnosisSession) -> DiagnosisSession:
        """Synthesize best diagnosis from partial findings."""
        session.is_complete = True
        session.termination_reason = "all_consulted"

        findings = []
        for resp in session.agent_responses:
            if resp.findings:
                findings.append(f"{resp.agent_id}: {resp.findings}")

        session.final_diagnosis = (
            "Partial diagnosis synthesized from multiple agents:\n" +
            "\n".join(findings)
        )
        session.recommended_actions = self._extract_actions(session)

        logger.info(f"Session synthesized from partial findings")
        return session

    def _synthesize_best_effort(self, session: DiagnosisSession) -> DiagnosisSession:
        """Synthesize best-effort diagnosis at max rounds."""
        session.is_complete = True
        session.termination_reason = "max_rounds"

        findings = []
        for resp in session.agent_responses:
            if resp.findings:
                findings.append(f"{resp.agent_id}: {resp.findings}")

        session.final_diagnosis = (
            f"Best-effort diagnosis after {session.max_rounds} rounds:\n" +
            "\n".join(findings) if findings else "Insufficient data for diagnosis"
        )
        session.recommended_actions = self._extract_actions(session)

        logger.info(f"Session terminated at max rounds")
        return session

    def _request_user_clarification(
        self,
        session: DiagnosisSession,
        response: AgentResponse
    ) -> DiagnosisSession:
        """Mark session as needing user clarification."""
        session.termination_reason = "user_clarification_needed"

        if response.clarification_questions:
            session.pending_clarifications.extend(response.clarification_questions)
        elif response.missing_information:
            session.pending_clarifications.append(
                f"Please provide: {response.missing_information}"
            )

        logger.info(f"Clarification needed: {session.pending_clarifications}")
        return session

    def _extract_actions(self, session: DiagnosisSession) -> List[str]:
        """Extract recommended actions from agent responses."""
        actions = []
        for resp in session.agent_responses:
            if hasattr(resp, 'recommended_actions') and resp.recommended_actions:
                actions.append(resp.recommended_actions)
            # Also check findings for action keywords
            if resp.findings:
                if any(kw in resp.findings.lower() for kw in ['recommend', 'action', 'should']):
                    actions.append(resp.findings)

        return list(set(actions))[:5]  # Dedupe and limit

    async def run_diagnosis(
        self,
        query: str,
        location: str = "unknown",
        equipment_type: str = "MRI"
    ) -> DiagnosisSession:
        """
        Run complete multi-round diagnosis session.

        Args:
            query: User's query or symptom description
            location: Location context
            equipment_type: Type of equipment

        Returns:
            Completed DiagnosisSession
        """
        logger.info(f"Starting diagnosis session: {query[:100]}...")

        # Create new session
        session = DiagnosisSession(
            original_query=query,
            max_rounds=self.max_rounds
        )

        # Start with governance agent
        context = f"Location: {location}\nEquipment: {equipment_type}"
        initial_response, latency = await self._call_agent(
            'governance_agent',
            query,
            context
        )

        # Orchestrate until complete
        last_processed_count = 0
        while not session.is_complete and session.current_round < session.max_rounds:
            session = await self.orchestrate_round(session, initial_response)

            if session.termination_reason == "user_clarification_needed":
                break

            # Guard against infinite loops: if no new responses were added,
            # there is nothing more to process
            if len(session.agent_responses) == last_processed_count:
                session = self._synthesize_best_effort(session)
                break
            last_processed_count = len(session.agent_responses)

            # If not complete, check for next response to process
            if not session.is_complete and session.agent_responses:
                initial_response = session.agent_responses[-1]

        logger.info(
            f"Diagnosis complete: {session.termination_reason}, "
            f"rounds={session.current_round}, "
            f"confidence={session.current_confidence}"
        )

        return session


async def main():
    """Test the multi-round orchestrator."""
    logger.info("=" * 60)
    logger.info("Testing Multi-Round Orchestrator")
    logger.info("=" * 60)

    orchestrator = MultiRoundOrchestrator()

    # Test case: Cascading Thermal Fault
    test_query = (
        "MRI scanner shows uptime SLA breach at 94% vs 99% target. "
        "Temperature sensor readings are intermittent. "
        "Session failures occurring every 90 minutes."
    )

    logger.info(f"\nTest Query: {test_query}\n")

    # Note: This requires running agent services
    try:
        session = await orchestrator.run_diagnosis(
            query=test_query,
            location="Radiology Department",
            equipment_type="Siemens MRI"
        )

        logger.info("\n" + "=" * 60)
        logger.info("DIAGNOSIS RESULT")
        logger.info("=" * 60)
        logger.info(f"Session ID: {session.session_id}")
        logger.info(f"Rounds: {session.current_round}")
        logger.info(f"Termination: {session.termination_reason}")
        logger.info(f"Confidence: {session.current_confidence}")
        logger.info(f"\nAgents Consulted: {session.agents_consulted}")
        logger.info(f"\nReasoning Chain:")
        for step in session.reasoning_chain:
            logger.info(f"  {step}")
        logger.info(f"\nFinal Diagnosis:\n{session.final_diagnosis}")

    except Exception as e:
        logger.error(f"Test failed (agents may not be running): {e}")
        logger.info("To run this test, start the agent services first:")
        logger.info("  python -m src.agents.governance_agent.main")
        logger.info("  python -m src.agents.hardware_agent.main")
        logger.info("  python -m src.agents.telemetry_agent.main")

    logger.info("\n" + "=" * 60)
    logger.info("Orchestrator test complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
