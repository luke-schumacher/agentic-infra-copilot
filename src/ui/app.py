"""
Streamlit Orchestrator - Multi-Agent System UI

HTTP client that orchestrates the distributed MAS architecture.
IMPORTANT: Does NOT import agent code directly - communicates only via HTTP.

Features:
- Chat interface for user queries
- Agent health monitoring
- Workflow visualization
- Response aggregation from multiple agents

Usage:
    streamlit run src/ui/app.py

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import streamlit as st
import httpx

# Add project root to path for protocol imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.protocol.schema import (
    AgentCard, AgentRole, IntentType, Priority,
    ConsultRequest, ConsultResponse, AgentHealthStatus
)

# ============================================================
# Configuration (supports Docker and local environments)
# ============================================================

# Agent URLs - use environment variables for Docker, fallback to localhost
TELEKOM_URL = os.getenv("TELEKOM_MINISTER_URL", "http://localhost:8001")
SIEMENS_URL = os.getenv("SIEMENS_TECHNICIAN_URL", "http://localhost:8002")
ILLIGO_URL = os.getenv("ILLIGO_OPERATOR_URL", "http://localhost:8003")

AGENT_ENDPOINTS = {
    "Governance Agent": {
        "url": TELEKOM_URL,
        "role": AgentRole.GOVERNANCE_AGENT,
        "description": "Governance - SLAs & Intent",
        "port": 8001,
        "legacy_name": "Telekom Minister"
    },
    "Hardware Agent": {
        "url": SIEMENS_URL,
        "role": AgentRole.HARDWARE_AGENT,
        "description": "Hardware Expert - Specs & Manuals",
        "port": 8002,
        "legacy_name": "Siemens Technician"
    },
    "Telemetry Agent": {
        "url": ILLIGO_URL,
        "role": AgentRole.TELEMETRY_AGENT,
        "description": "Live Monitor - Logs & Events",
        "port": 8003,
        "legacy_name": "Illigo Operator"
    }
}

# ============================================================
# Page Configuration
# ============================================================

st.set_page_config(
    page_title="Agentic Infra Co-Pilot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# Helper Functions
# ============================================================


def check_agent_health(agent_name: str, agent_config: Dict) -> Optional[AgentHealthStatus]:
    """
    Check health of a single agent via HTTP.

    Args:
        agent_name: Display name of the agent
        agent_config: Configuration dict with url and role

    Returns:
        AgentHealthStatus if reachable, None otherwise
    """
    try:
        response = httpx.get(
            f"{agent_config['url']}/health",
            timeout=5.0
        )
        if response.status_code == 200:
            return AgentHealthStatus(**response.json())
    except Exception:
        pass
    return None


def send_query_to_minister(
    query: str,
    location: str = "unknown",
    is_symptom: bool = True
) -> Optional[ConsultResponse]:
    """
    Send a query to Governance Agent (entry point for all workflows).

    All queries start at the Minister, who may delegate to specialists.

    Args:
        query: User's question or symptom description
        location: Location context if applicable
        is_symptom: Whether this describes an issue/symptom

    Returns:
        ConsultResponse if successful, None otherwise
    """
    card = AgentCard(
        sender=AgentRole.ORCHESTRATOR,
        recipient=AgentRole.GOVERNANCE_AGENT,
        intent=IntentType.QUERY,
        priority=Priority.NORMAL,
        payload={
            "query": query,
            "location": location,
            "is_symptom": is_symptom
        }
    )

    request = ConsultRequest(card=card)

    try:
        response = httpx.post(
            f"{AGENT_ENDPOINTS['Governance Agent']['url']}/consult",
            json=request.model_dump(),
            timeout=60.0
        )

        if response.status_code == 200:
            return ConsultResponse(**response.json())
        else:
            st.error(f"Governance Agent returned error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Failed to contact Governance Agent: {e}")

    return None


# ============================================================
# UI Components
# ============================================================


def render_sidebar():
    """Render sidebar with agent status and controls."""
    st.sidebar.title("🤖 Agent Status")
    st.sidebar.markdown("---")

    for agent_name, config in AGENT_ENDPOINTS.items():
        with st.sidebar.expander(agent_name, expanded=True):
            health = check_agent_health(agent_name, config)

            if health:
                status_emoji = {
                    "healthy": "🟢",
                    "degraded": "🟡",
                    "unhealthy": "🔴"
                }.get(health.status, "⚪")

                st.markdown(f"**Status:** {status_emoji} {health.status.upper()}")
                st.markdown(f"**Documents:** {health.document_count:,}")
                st.markdown(f"**DSPy:** {'✅' if health.dspy_ready else '❌'}")
                st.markdown(f"**Vector Store:** {'✅' if health.vector_store_ready else '❌'}")

                if health.uptime_seconds > 0:
                    uptime_min = health.uptime_seconds / 60
                    st.markdown(f"**Uptime:** {uptime_min:.1f} min")
            else:
                st.markdown("**Status:** 🔴 OFFLINE")
                st.caption(f"Port {config['port']} not responding")

            st.caption(config["description"])

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Actions")

    if st.sidebar.button("🔄 Refresh Status"):
        st.rerun()

    if st.sidebar.button("📚 Index Documents"):
        with st.spinner("Indexing..."):
            try:
                response = httpx.post(
                    f"{AGENT_ENDPOINTS['Governance Agent']['url']}/index",
                    timeout=120.0
                )
                if response.status_code == 200:
                    result = response.json()
                    st.sidebar.success(f"Indexed {result.get('indexed_count', 0)} documents")
                else:
                    st.sidebar.error("Indexing failed")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")


def render_header():
    """Render main header."""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("Agentic Infra Co-Pilot")
        st.markdown(
            "*Distributed Multi-Agent System for Critical Infrastructure Diagnosis*"
        )

    with col2:
        st.markdown("### Architecture")
        st.caption(
            "Telekom 'External Minister' + 'Agent2Agent' Pattern"
        )


def render_chat_interface():
    """Render main chat interface."""

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat container
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                # Display sources if available
                if message.get("sources"):
                    with st.expander("📚 View Sources", expanded=False):
                        for source in message["sources"]:
                            st.markdown(
                                f"- **{source['source']}**: {source['file_name']}"
                            )

                # Display delegation info if available
                if message.get("delegation"):
                    deleg = message["delegation"]
                    if deleg.get("target_agent") != "self":
                        st.info(
                            f"🔀 Delegated to: **{deleg['target_agent']}**\n\n"
                            f"Reason: {deleg.get('reason', 'N/A')}"
                        )

    # Chat input
    st.markdown("---")

    col1, col2 = st.columns([4, 1])

    with col1:
        query_type = st.radio(
            "Query Type",
            ["Symptom/Issue", "General Question"],
            horizontal=True,
            label_visibility="collapsed"
        )

    with col2:
        location = st.text_input(
            "Location",
            placeholder="e.g., Koumassi",
            label_visibility="collapsed"
        )

    if prompt := st.chat_input("Describe an infrastructure issue or ask a question..."):
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Send to Minister
        with st.chat_message("assistant"):
            with st.spinner("🔍 Consulting agents..."):
                is_symptom = query_type == "Symptom/Issue"
                response = send_query_to_minister(
                    prompt,
                    location=location or "unknown",
                    is_symptom=is_symptom
                )

            if response and response.success:
                card = response.response_card
                payload = card.payload

                # Format response based on query type
                if is_symptom:
                    risk_level = payload.get('risk_level', 'N/A')
                    risk_emoji = {
                        'critical': '🔴',
                        'high': '🟠',
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(risk_level.lower(), '⚪')

                    response_text = f"""
### Risk Assessment: {risk_emoji} {risk_level.upper()}

**Violated SLAs:**
{payload.get('violated_slas', 'None identified')}

**Recommended Actions:**
{payload.get('recommended_actions', 'No immediate actions required')}
                    """
                else:
                    response_text = f"""
### Answer

{payload.get('answer', 'Unable to determine answer')}

**Confidence:** {payload.get('confidence', 'N/A')}
                    """

                st.markdown(response_text)

                # Store message with metadata
                delegation = payload.get('delegation', {})
                sources = [
                    {"source": doc.source, "file_name": doc.file_name}
                    for doc in card.documents
                ]

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources,
                    "delegation": delegation
                })

                # Display sources
                if card.documents:
                    with st.expander("📚 View Sources", expanded=False):
                        for doc in card.documents:
                            st.markdown(f"- **{doc.source}**: {doc.file_name}")

                # Display delegation
                if delegation.get('target_agent') and delegation['target_agent'] != 'self':
                    st.info(
                        f"🔀 **Delegation:** This query has been forwarded to "
                        f"**{delegation['target_agent']}** for specialized analysis.\n\n"
                        f"*Reason: {delegation.get('reason', 'Requires specialist expertise')}*"
                    )

                # Display specialist findings if available
                specialist_findings = payload.get('specialist_findings')
                if specialist_findings:
                    with st.expander("🔬 Specialist Analysis", expanded=True):
                        spec_card = specialist_findings.get('response_card', {})
                        spec_payload = spec_card.get('payload', {})
                        spec_agent = spec_payload.get('specialist_agent', 'specialist')

                        # Agent icon mapping
                        agent_icons = {
                            'siemens_technician': '🔧',
                            'illigo_operator': '⚡'
                        }
                        icon = agent_icons.get(spec_agent, '🔍')

                        st.markdown(f"### {icon} {spec_agent.replace('_', ' ').title()}")

                        # Display key specialist findings
                        if spec_payload.get('diagnosis'):
                            st.markdown(f"**Diagnosis:** {spec_payload['diagnosis']}")
                        if spec_payload.get('severity'):
                            st.markdown(f"**Severity:** {spec_payload['severity']}")
                        if spec_payload.get('diagnostic_steps'):
                            st.markdown(f"**Diagnostic Steps:** {spec_payload['diagnostic_steps']}")
                        if spec_payload.get('root_cause'):
                            st.markdown(f"**Root Cause:** {spec_payload['root_cause']}")
                        if spec_payload.get('impact'):
                            st.markdown(f"**Impact:** {spec_payload['impact']}")
                        if spec_payload.get('corrective_actions'):
                            st.markdown(f"**Corrective Actions:** {spec_payload['corrective_actions']}")
                        if spec_payload.get('answer'):
                            st.markdown(f"**Analysis:** {spec_payload['answer']}")
                        if spec_payload.get('common_issues'):
                            st.markdown(f"**Common Issues:** {spec_payload['common_issues']}")
                        if spec_payload.get('recommended_solutions'):
                            st.markdown(f"**Recommended Solutions:** {spec_payload['recommended_solutions']}")

                        # Processing time from specialist
                        spec_time = specialist_findings.get('processing_time_ms', 0)
                        if spec_time > 0:
                            st.caption(f"⏱️ Specialist response: {spec_time:.0f}ms")

                # Display timing
                st.caption(f"⏱️ Total response time: {response.processing_time_ms:.0f}ms")

            else:
                error_msg = response.error if response else "Failed to get response from agent"
                st.error(f"❌ Error: {error_msg}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {error_msg}"
                })


def render_footer():
    """Render footer with system info."""
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption("🏗️ Architecture: Tripartite MAS")

    with col2:
        st.caption("🧠 Brain: DSPy + Groq/Llama3-70B")

    with col3:
        st.caption(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")


# ============================================================
# Main Application
# ============================================================


def main():
    """Main application entry point."""
    render_header()
    render_sidebar()
    render_chat_interface()
    render_footer()


if __name__ == "__main__":
    main()
