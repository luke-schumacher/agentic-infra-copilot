"""
Streamlit Orchestrator - Multi-Agent System UI

HTTP client that orchestrates the distributed MAS architecture.
IMPORTANT: Does NOT import agent code directly - communicates only via HTTP.

Features:
- Chat interface with example prompts (Discoverability)
- Visible labels and input panels (Affordances + Signifiers)
- Confidence badges and response type indicators (Feedback)
- Reasoning chain visualization (Conceptual Model)
- Customer ID validation (Constraints)
- Double-submit guard (Constraints)
- Friendly error messages (Feedback)
- Rich source display (Signifiers)

Usage:
    streamlit run src/ui/app.py

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import re
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
GOVERNANCE_URL = os.getenv(
    "GOVERNANCE_AGENT_URL",
    os.getenv("TELEKOM_MINISTER_URL", "http://localhost:8001")
)
HARDWARE_URL = os.getenv(
    "HARDWARE_AGENT_URL",
    os.getenv("SIEMENS_TECHNICIAN_URL", "http://localhost:8002")
)
TELEMETRY_URL = os.getenv(
    "TELEMETRY_AGENT_URL",
    os.getenv("ILLIGO_OPERATOR_URL", "http://localhost:8003")
)

AGENT_ENDPOINTS = {
    "Workflow & Context (The Anthropologist)": {
        "url": GOVERNANCE_URL,
        "role": AgentRole.GOVERNANCE_AGENT,
        "description": "Institution profiling, workload analysis, operational context",
        "port": 8001,
        "legacy_name": "Governance Agent"
    },
    "Diagnostic & Technical (The Specialist)": {
        "url": HARDWARE_URL,
        "role": AgentRole.HARDWARE_AGENT,
        "description": "DICOM conformance, MRI hardware diagnostics, SOP Class analysis",
        "port": 8002,
        "legacy_name": "Hardware Agent"
    },
    "Safety & Compliance (The Auditor)": {
        "url": TELEMETRY_URL,
        "role": AgentRole.TELEMETRY_AGENT,
        "description": "MRI safety SOPs, Zone I-IV compliance, regulatory auditing",
        "port": 8003,
        "legacy_name": "Telemetry Agent"
    }
}

# I6: Consistent agent naming
AGENT_DISPLAY_NAMES = {
    'governance_agent': 'The Anthropologist (Workflow & Context)',
    'hardware_agent': 'The Specialist (Diagnostic & Technical)',
    'telemetry_agent': 'The Auditor (Safety & Compliance)',
    'siemens_technician': 'The Specialist (Diagnostic & Technical)',
    'illigo_operator': 'The Auditor (Safety & Compliance)',
    'diagnostic_specialist': 'The Specialist (Diagnostic & Technical)',
    'safety_auditor': 'The Auditor (Safety & Compliance)',
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
# CSS Injection (Chakra UI-inspired visual overhaul)
# ============================================================


def inject_custom_css():
    """Inject comprehensive CSS overrides for a Chakra UI-inspired look."""
    st.markdown("""<style>
    /* --- Hide Streamlit chrome --- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent; height: 0;}
    .stDeployButton {display: none;}

    /* --- Typography --- */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    }
    h1 { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
    h2 { font-size: 1.375rem; font-weight: 600; }
    h3 { font-size: 1.125rem; font-weight: 600; }
    p, li, span { font-size: 0.9375rem; line-height: 1.625; }

    /* --- Buttons --- */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.08);
        background-color: rgba(255,255,255,0.04);
        color: #E2E8F0;
        font-weight: 500;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background-color: rgba(49,130,206,0.15);
        border-color: rgba(49,130,206,0.4);
    }

    /* --- Chat messages --- */
    [data-testid="stChatMessage"] {
        background-color: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
    }

    /* --- Expanders --- */
    [data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 8px;
        background-color: rgba(255,255,255,0.02);
    }
    [data-testid="stExpander"] summary {
        font-weight: 500;
        font-size: 0.875rem;
    }

    /* --- Metrics --- */
    [data-testid="stMetric"] {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #A0AEC0;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 700;
    }

    /* --- Input fields --- */
    .stTextInput > div > div > input,
    .stSelectbox > div > div {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.12);
        background-color: rgba(255,255,255,0.04);
    }
    .stTextInput > div > div > input:focus {
        border-color: #3182CE;
        box-shadow: 0 0 0 1px #3182CE;
    }

    /* --- Sidebar --- */
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    [data-testid="stSidebar"] .stMarkdown p {
        font-size: 0.8125rem;
    }

    /* --- Radio buttons (pill style) --- */
    .stRadio > div {
        gap: 0.5rem;
    }
    .stRadio > div > label {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 0.375rem 1rem;
        font-size: 0.8125rem;
    }

    /* --- Dividers --- */
    hr {
        border: none;
        border-top: 1px solid rgba(255,255,255,0.06);
        margin: 1.5rem 0;
    }

    /* --- Chat input --- */
    [data-testid="stChatInput"] textarea {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        background-color: rgba(255,255,255,0.04);
    }

    /* --- Scrollbar --- */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
    </style>""", unsafe_allow_html=True)


# ============================================================
# Helper Functions
# ============================================================


def _get_agent_display_name(raw_name: str) -> str:
    """Map raw agent role strings to human-readable display names."""
    return AGENT_DISPLAY_NAMES.get(raw_name, raw_name.replace('_', ' ').title())


def _validate_customer_id(customer_id: str) -> bool:
    """Validate customer ID format: mr followed by 5+ digits."""
    if not customer_id:
        return True  # Empty is valid (optional field)
    return bool(re.match(r'^mr\d{5,}$', customer_id))


def check_agent_health(agent_name: str, agent_config: Dict) -> Optional[AgentHealthStatus]:
    """Check health of a single agent via HTTP."""
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


def send_query_to_anthropologist(
    query: str,
    location: str = "unknown",
    is_symptom: bool = True,
    customer_id: str = "",
    scanner_model: str = "",
    institution_type: str = ""
) -> Optional[ConsultResponse]:
    """Send a query to the Workflow Anthropologist (entry point for all workflows)."""
    payload = {
        "query": query,
        "location": location,
        "is_symptom": is_symptom
    }
    if customer_id:
        payload["customer_id"] = customer_id
    if scanner_model:
        payload["scanner_model"] = scanner_model
    if institution_type:
        payload["institution_type"] = institution_type

    card = AgentCard(
        sender=AgentRole.ORCHESTRATOR,
        recipient=AgentRole.GOVERNANCE_AGENT,
        intent=IntentType.QUERY,
        priority=Priority.NORMAL,
        payload=payload
    )

    request = ConsultRequest(card=card)

    anthropologist_url = AGENT_ENDPOINTS["Workflow & Context (The Anthropologist)"]["url"]

    try:
        response = httpx.post(
            f"{anthropologist_url}/consult",
            json=request.model_dump(),
            timeout=60.0
        )

        if response.status_code == 200:
            return ConsultResponse(**response.json())
        else:
            st.error(f"Agent returned error {response.status_code}: {response.text}")
    except httpx.TimeoutException:
        st.error("Request timed out. The agents may be busy or starting up. Please try again.")
    except httpx.ConnectError:
        st.error("Could not connect to the agent service. Please ensure the agents are running.")
    except Exception as e:
        st.error(f"Failed to contact agents: {e}")

    return None


# ============================================================
# UI Components
# ============================================================


def render_sidebar():
    """Render sidebar with agent status and controls."""
    st.sidebar.title("Agent Status")
    st.sidebar.markdown("---")

    for agent_name, config in AGENT_ENDPOINTS.items():
        with st.sidebar.expander(agent_name, expanded=True):
            health = check_agent_health(agent_name, config)

            if health:
                status_dot = {
                    "healthy": '<span style="color:#48BB78;">&#9679;</span>',
                    "degraded": '<span style="color:#ECC94B;">&#9679;</span>',
                    "unhealthy": '<span style="color:#FC8181;">&#9679;</span>'
                }.get(health.status, '<span style="color:#718096;">&#9679;</span>')

                st.markdown(f"{status_dot} {health.status.upper()}", unsafe_allow_html=True)
                st.markdown(f"**Documents:** {health.document_count:,}")

                ready = '<span style="color:#48BB78;">Ready</span>'
                not_ready = '<span style="color:#FC8181;">Not ready</span>'
                st.markdown(f"**DSPy:** {ready if health.dspy_ready else not_ready}", unsafe_allow_html=True)
                st.markdown(f"**Vector Store:** {ready if health.vector_store_ready else not_ready}", unsafe_allow_html=True)

                if health.uptime_seconds > 0:
                    uptime_min = health.uptime_seconds / 60
                    st.markdown(f"**Uptime:** {uptime_min:.1f} min")
            else:
                st.markdown(
                    '<span style="color:#FC8181;">&#9679;</span> OFFLINE',
                    unsafe_allow_html=True
                )
                st.caption(f"Port {config['port']} not responding")

            st.caption(config["description"])

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Quick Actions")

    if st.sidebar.button("Refresh Status"):
        st.rerun()

    if st.sidebar.button("Index Documents"):
        with st.spinner("Indexing..."):
            try:
                anthropologist_url = AGENT_ENDPOINTS["Workflow & Context (The Anthropologist)"]["url"]
                response = httpx.post(
                    f"{anthropologist_url}/index",
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
    st.markdown(
        '<h1 style="margin-bottom:0.25rem;">Agentic Infra Co-Pilot</h1>'
        '<p style="color:#A0AEC0;font-size:0.9rem;margin-top:0;">'
        'Multi-Agent System for MRI Operations Analysis</p>',
        unsafe_allow_html=True
    )


def render_welcome_state():
    """I1: Show welcome banner with example prompts when chat is empty."""
    st.markdown(
        '<p style="color:#A0AEC0;font-size:0.9rem;margin-bottom:1.5rem;">'
        'Ask about MRI operations, hardware diagnostics, or safety compliance.</p>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            '<p style="font-weight:600;font-size:0.8125rem;color:#A0AEC0;'
            'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">'
            'Hardware Diagnostics</p>', unsafe_allow_html=True
        )
        if st.button("Gradient thermal errors for mr176430", key="ex_hw1"):
            st.session_state.example_prompt = "Customer mr176430 is experiencing gradient thermal shutdown events. What could be causing this?"
        if st.button("DICOM transfer failures", key="ex_hw2"):
            st.session_state.example_prompt = "We're seeing DICOM C-STORE transfer failures between our MAGNETOM Sola and PACS. What SOP class mismatches could cause this?"

    with col2:
        st.markdown(
            '<p style="font-weight:600;font-size:0.8125rem;color:#A0AEC0;'
            'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">'
            'Workflow & Operations</p>', unsafe_allow_html=True
        )
        if st.button("Error rate analysis", key="ex_wf1"):
            st.session_state.example_prompt = "Analyze the error rates across our MRI fleet. Which customers have the highest error frequencies?"
        if st.button("Workload bottlenecks", key="ex_wf2"):
            st.session_state.example_prompt = "What are the peak usage hours and workload bottlenecks for high-volume academic medical centers?"

    with col3:
        st.markdown(
            '<p style="font-weight:600;font-size:0.8125rem;color:#A0AEC0;'
            'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.5rem;">'
            'Safety & Compliance</p>', unsafe_allow_html=True
        )
        if st.button("Zone IV recalibration safety", key="ex_sf1"):
            st.session_state.example_prompt = "Is it safe to recalibrate thermal sensors in Zone IV while the magnet is at field? What personnel are required?"
        if st.button("Personnel requirements", key="ex_sf2"):
            st.session_state.example_prompt = "What are the minimum personnel requirements for MRI maintenance procedures per ACR guidelines?"


def render_chat_interface():
    """Render main chat interface."""

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "example_prompt" not in st.session_state:
        st.session_state.example_prompt = None

    # I1: Welcome state when no messages
    if not st.session_state.messages:
        render_welcome_state()

    # Chat container
    chat_container = st.container()

    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                # Display sources if available
                if message.get("sources"):
                    with st.expander("View Sources", expanded=False):
                        for source in message["sources"]:
                            snippet = source.get('snippet', '')
                            score = source.get('relevance_score', '')
                            score_str = f" (relevance: {score:.2f})" if score else ""
                            st.markdown(
                                f"- **{source['source']}**: {source['file_name']}{score_str}"
                            )
                            if snippet:
                                st.caption(snippet[:200])

                # Display delegation info if available
                if message.get("delegation"):
                    deleg = message["delegation"]
                    if deleg.get("target_agent") and deleg["target_agent"] != "self":
                        agent_name = _get_agent_display_name(deleg['target_agent'])
                        st.markdown(
                            f'<p style="font-size:0.8125rem;color:#A0AEC0;margin-bottom:0.5rem;">'
                            f'Consulted {agent_name}</p>',
                            unsafe_allow_html=True
                        )

    # I2: Visible labels + input panel
    st.markdown("---")

    with st.expander("Query Context (optional)", expanded=False):
        ctx_col1, ctx_col2, ctx_col3, ctx_col4 = st.columns(4)

        with ctx_col1:
            customer_id = st.text_input(
                "Customer ID",
                placeholder="e.g., mr176430",
                help="Siemens customer ID in format: mr followed by 5+ digits"
            )
            # I7: Customer ID validation
            if customer_id and not _validate_customer_id(customer_id):
                st.warning("Customer ID should be in format 'mr' followed by 5+ digits (e.g., mr176430)")

        with ctx_col2:
            scanner_model = st.selectbox(
                "Scanner Model",
                options=["", "MAGNETOM Sola", "MAGNETOM Vida", "MAGNETOM Altea", "MAGNETOM Free.Max"],
                index=0,
                help="MRI scanner model for context-specific analysis"
            )

        with ctx_col3:
            institution_type = st.selectbox(
                "Institution Type",
                options=["", "academic", "private", "cancer_center"],
                index=0,
                help="Type of medical institution"
            )

        with ctx_col4:
            location = st.text_input(
                "Location",
                placeholder="e.g., Munich",
                help="Geographic location of the institution"
            )

    query_type = st.radio(
        "Query Type",
        ["Symptom/Issue", "General Question"],
        horizontal=True,
    )

    # Handle example prompt
    prompt = None
    if st.session_state.example_prompt:
        prompt = st.session_state.example_prompt
        st.session_state.example_prompt = None

    # I8: Double-submit guard
    if not prompt:
        prompt = st.chat_input(
            "Describe an MRI operations issue or ask a question...",
            disabled=st.session_state.processing
        )

    if prompt:
        # I8: Set processing flag
        st.session_state.processing = True

        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Send to Anthropologist
        with st.chat_message("assistant"):
            with st.spinner("Consulting agents..."):
                is_symptom = query_type == "Symptom/Issue"
                response = send_query_to_anthropologist(
                    prompt,
                    location=location or "unknown",
                    is_symptom=is_symptom,
                    customer_id=customer_id or "",
                    scanner_model=scanner_model or "",
                    institution_type=institution_type or ""
                )

            if response and response.success:
                card = response.response_card
                payload = card.payload

                # I5: Show delegation BEFORE response (compact caption)
                delegation = payload.get('delegation', {})
                if delegation.get('target_agent') and delegation['target_agent'] != 'self':
                    agent_name = _get_agent_display_name(delegation['target_agent'])
                    st.markdown(
                        f'<p style="font-size:0.8125rem;color:#A0AEC0;margin-bottom:0.5rem;">'
                        f'Consulted {agent_name}</p>',
                        unsafe_allow_html=True
                    )

                    # Show multi-hop if applicable
                    agents_involved = payload.get('agents_involved', [])
                    if len(agents_involved) > 1:
                        agent_names = [_get_agent_display_name(a) for a in agents_involved]
                        st.markdown(
                            f'<p style="font-size:0.8125rem;color:#A0AEC0;margin-bottom:0.5rem;">'
                            f'Multi-hop: {" &rarr; ".join(agent_names)}</p>',
                            unsafe_allow_html=True
                        )

                # Format response based on query type
                if is_symptom:
                    risk_level = payload.get('risk_level', 'N/A')
                    risk_colors = {
                        'critical': '#FC8181', 'high': '#F6AD55',
                        'medium': '#ECC94B', 'low': '#48BB78'
                    }
                    color = risk_colors.get(str(risk_level).lower(), '#A0AEC0')

                    response_text = (
                        f'<div style="display:inline-block;background:{color}20;color:{color};'
                        f'padding:0.25rem 0.75rem;border-radius:20px;font-size:0.8125rem;font-weight:600;'
                        f'margin-bottom:1rem;">{risk_level.upper()}</div>\n\n'
                    )

                    if payload.get('contextual_explanation'):
                        response_text += f"#### Context\n{payload['contextual_explanation']}\n\n"
                    if payload.get('institution_profile'):
                        response_text += f"#### Institution Profile\n{payload['institution_profile']}\n\n"
                    if payload.get('risk_factors'):
                        response_text += f"#### Risk Factors\n{payload['risk_factors']}\n\n"
                    if payload.get('recommended_actions'):
                        response_text += f"#### Recommended Actions\n{payload['recommended_actions']}\n\n"
                else:
                    answer = payload.get('answer', 'Unable to determine answer')
                    response_text = f"### Answer\n\n{answer}\n\n"

                    if payload.get('sources_used'):
                        response_text += f"**Sources:** {payload['sources_used']}\n\n"
                    if payload.get('follow_up'):
                        response_text += f"**Follow-up:** {payload['follow_up']}\n\n"
                    if payload.get('workload_assessment'):
                        response_text += f"**Workload Assessment:** {payload['workload_assessment']}\n\n"
                    if payload.get('peak_periods'):
                        response_text += f"**Peak Periods:** {payload['peak_periods']}\n\n"
                    if payload.get('bottleneck_analysis'):
                        response_text += f"**Bottleneck Analysis:** {payload['bottleneck_analysis']}\n\n"
                    if payload.get('optimization_suggestions'):
                        response_text += f"**Optimization Suggestions:** {payload['optimization_suggestions']}\n\n"

                st.markdown(response_text, unsafe_allow_html=True)

                # Show integrated root cause when delegation occurred
                if payload.get('integration_performed'):
                    st.success(f"**Root Cause:** {payload.get('root_cause', 'N/A')}")

                # I3: Confidence + Response Type badges
                badge_col1, badge_col2, badge_col3 = st.columns(3)
                with badge_col1:
                    conf_pct = f"{card.confidence * 100:.0f}%" if card.confidence else "N/A"
                    st.metric("Confidence", conf_pct)
                with badge_col2:
                    rt_value = card.response_type.value if card.response_type else "N/A"
                    st.metric("Response Type", rt_value)
                with badge_col3:
                    st.metric("Processing Time", f"{response.processing_time_ms:.0f}ms")

                # Show warning for partial responses
                if card.response_type and card.response_type.value == "PARTIAL":
                    st.warning("This is a partial response. Additional information may be needed for a complete answer.")

                # Show customer_id in response if present
                if payload.get('customer_id'):
                    st.caption(f"Customer: {payload['customer_id']}")

                # Store message with metadata
                sources = [
                    {
                        "source": doc.source,
                        "file_name": doc.file_name,
                        "snippet": doc.content_snippet[:200] if doc.content_snippet else "",
                        "relevance_score": doc.relevance_score
                    }
                    for doc in card.documents
                ]

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "sources": sources,
                    "delegation": delegation
                })

                # I10: Rich source display
                if card.documents:
                    with st.expander("View Sources", expanded=False):
                        for doc in card.documents:
                            score_str = f" (relevance: {doc.relevance_score:.2f})" if doc.relevance_score else ""
                            st.markdown(f"- **{doc.source}**: {doc.file_name}{score_str}")
                            if doc.content_snippet:
                                st.caption(doc.content_snippet[:200])

                # Display specialist findings if available
                specialist_findings = payload.get('specialist_findings')
                if specialist_findings:
                    with st.expander("Specialist Analysis", expanded=True):
                        spec_card = specialist_findings.get('response_card', {})
                        spec_payload = spec_card.get('payload', {})
                        spec_agent = spec_payload.get('specialist_agent', 'specialist')

                        display_name = _get_agent_display_name(spec_agent)

                        st.markdown(f"**{display_name}**")

                        if spec_payload.get('diagnosis'):
                            st.markdown(f"**Diagnosis:** {spec_payload['diagnosis']}")
                        if spec_payload.get('severity'):
                            st.markdown(f"**Severity:** {spec_payload['severity']}")
                        if spec_payload.get('diagnostic_steps'):
                            st.markdown(f"**Diagnostic Steps:** {spec_payload['diagnostic_steps']}")
                        if spec_payload.get('root_cause'):
                            st.markdown(f"**Root Cause:** {spec_payload['root_cause']}")
                        if spec_payload.get('safety_assessment'):
                            st.markdown(f"**Safety Assessment:** {spec_payload['safety_assessment']}")
                        if spec_payload.get('answer'):
                            st.markdown(f"**Analysis:** {spec_payload['answer']}")
                        if spec_payload.get('sources_used'):
                            st.markdown(f"**Sources Used:** {spec_payload['sources_used']}")
                        if spec_payload.get('follow_up'):
                            st.markdown(f"**Follow-up:** {spec_payload['follow_up']}")

                        spec_time = specialist_findings.get('processing_time_ms', 0)
                        if spec_time > 0:
                            st.caption(f"Specialist response: {spec_time:.0f}ms")

                # Second specialist findings (multi-hop)
                second_specialist = payload.get('second_specialist_findings')
                if second_specialist:
                    with st.expander("Second Specialist Analysis", expanded=True):
                        sec_card = second_specialist.get('response_card', {})
                        sec_payload = sec_card.get('payload', {})
                        sec_agent = sec_payload.get('specialist_agent', 'specialist')

                        display_name = _get_agent_display_name(sec_agent)

                        st.markdown(f"**{display_name}**")

                        if sec_payload.get('diagnosis'):
                            st.markdown(f"**Diagnosis:** {sec_payload['diagnosis']}")
                        if sec_payload.get('safety_assessment'):
                            st.markdown(f"**Safety Assessment:** {sec_payload['safety_assessment']}")
                        if sec_payload.get('answer'):
                            st.markdown(f"**Analysis:** {sec_payload['answer']}")

                # I4: Reasoning chain visualization
                reasoning_chain = payload.get('reasoning_chain_visualization')
                if reasoning_chain:
                    with st.expander("Reasoning Chain", expanded=False):
                        rounds = reasoning_chain.get('rounds', [])
                        for r in rounds:
                            round_num = r.get('round_number', '?')
                            agent = _get_agent_display_name(r.get('agent', 'unknown'))
                            rt = r.get('response_type', 'N/A')
                            conf = r.get('confidence', 0)
                            st.markdown(
                                f"**Round {round_num}** — {agent} | "
                                f"Type: {rt} | Confidence: {conf:.0%}"
                            )

                # Display timing
                st.caption(f"Total response time: {response.processing_time_ms:.0f}ms")

            else:
                # I9: Friendly error messages
                if response:
                    error_msg = response.error or "Unknown error occurred"
                else:
                    error_msg = "Failed to get response from agents"

                st.error(f"Unable to process your query. Please try again or rephrase your question.")
                with st.expander("Error Details", expanded=False):
                    st.code(error_msg)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {error_msg}"
                })

        # I8: Clear processing flag
        st.session_state.processing = False


def render_footer():
    """Render footer with system info."""
    st.markdown(
        '<p style="text-align:center;color:#4A5568;font-size:0.75rem;margin-top:2rem;">'
        'Tripartite MAS &middot; DSPy + Claude 3.5 Haiku / GPT-4.1-nano &middot; '
        f'{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        unsafe_allow_html=True
    )


# ============================================================
# Main Application
# ============================================================


def main():
    """Main application entry point."""
    inject_custom_css()
    render_header()
    render_sidebar()
    render_chat_interface()
    render_footer()


if __name__ == "__main__":
    main()
