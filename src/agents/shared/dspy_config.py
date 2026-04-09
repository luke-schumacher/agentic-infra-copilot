"""
DSPy Configuration - Multi-Model LLM Setup for All Agents

Three-tier model strategy:
  - Router (classification/routing): Azure GPT-4.1
  - Reasoner (agent brain): Claude Haiku 4.5 (global default, fast)
  - Judge/Synthesizer: Claude Sonnet 4.5 (higher quality for evaluation)

Three configuration modes (selected automatically from env vars):

  Mode 1 — Full Azure (AZURE_API_KEY + AZURE_ENDPOINT, no ANTHROPIC_API_KEY):
    All three models via Azure Cognitive Services endpoint.
    Requires Claude deployments on the Azure subscription.

  Mode 2 — Hybrid (AZURE_API_KEY + AZURE_ENDPOINT + ANTHROPIC_API_KEY):
    Router  → Azure GPT-4.1  (uses AZURE_ENDPOINT / AZURE_API_KEY)
    Reasoner + Judge → Direct Anthropic Haiku/Sonnet  (uses ANTHROPIC_API_KEY)
    Use this when Claude is not deployable on the Azure subscription (e.g. student accounts).

  Mode 3 — Direct APIs only (no AZURE_API_KEY):
    Router  → OpenAI GPT-4.1-nano  (uses OPENAI_API_KEY)
    Reasoner + Judge → Direct Anthropic Haiku/Sonnet  (uses ANTHROPIC_API_KEY)

The reasoner (Haiku) is set as the global default. Router is used explicitly
via dspy.context(lm=router_lm) for EvaluateRequest and DelegateToSpecialist calls.
Sonnet is available via get_lm_config().sonnet for judge and synthesis modules.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import dspy

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level cache so judge/synthesis can retrieve config after initial setup
_cached_config: Optional["LMConfig"] = None


@dataclass
class LMConfig:
    """Holds configured LM instances for the three-tier strategy."""
    router: dspy.LM      # Fast model for classification/routing
    reasoner: dspy.LM    # Claude Haiku for all agent brain reasoning (global default)
    sonnet: dspy.LM      # Claude Sonnet for judge and synthesis (higher quality)


def configure_dspy() -> LMConfig:
    """
    Configure DSPy with three-tier model strategy via Azure AI endpoint.

    Tier 1 (Router):     azure/gpt-4-1          — classification, temp=0.0
    Tier 2 (Reasoner):   azure/claude-haiku-4-5  — agent reasoning, global default
    Tier 3 (Sonnet):     azure/claude-sonnet-4-5 — judge + synthesis

    Falls back to direct OpenAI/Anthropic if Azure vars are absent.

    Returns:
        LMConfig with all three LM instances
    """
    global _cached_config

    azure_key = os.getenv("AZURE_API_KEY")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    azure_api_version = os.getenv("AZURE_API_VERSION", "2024-10-21")
    azure_gpt = os.getenv("AZURE_DEPLOYMENT_GPT", "gpt-4-1")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    use_azure_router = bool(azure_key and azure_endpoint)
    use_hybrid = use_azure_router and bool(anthropic_key)

    if use_hybrid:
        # Mode 2: Azure GPT-4.1 for routing + direct Anthropic for Claude tiers
        # Used when Claude deployments are not available on the Azure subscription.
        logger.info(f"Hybrid mode: Router via Azure ({azure_endpoint}), Claude via direct Anthropic API")

        router_lm = dspy.LM(
            model=f"azure/{azure_gpt}",
            api_key=azure_key,
            api_base=azure_endpoint,
            api_version=azure_api_version,
            temperature=0.0,
            max_tokens=500
        )

        reasoner_lm = dspy.LM(
            model="anthropic/claude-haiku-4-5-20251001",
            api_key=anthropic_key,
            temperature=0.1,
            max_tokens=2000
        )

        sonnet_lm = dspy.LM(
            model="anthropic/claude-sonnet-4-5",
            api_key=anthropic_key,
            temperature=0.1,
            max_tokens=4000
        )

        logger.info("DSPy configured: Router=Azure/GPT-4.1, Reasoner=Anthropic/Haiku-4.5, Judge=Anthropic/Sonnet-4.5")

    elif use_azure_router:
        # Mode 1: All three models via Azure Cognitive Services
        azure_haiku = os.getenv("AZURE_DEPLOYMENT_HAIKU", "claude-haiku-4-5")
        azure_sonnet = os.getenv("AZURE_DEPLOYMENT_SONNET", "claude-sonnet-4-5")

        logger.info(f"Full Azure mode: all models via {azure_endpoint}")

        router_lm = dspy.LM(
            model=f"azure/{azure_gpt}",
            api_key=azure_key,
            api_base=azure_endpoint,
            api_version=azure_api_version,
            temperature=0.0,
            max_tokens=500
        )

        reasoner_lm = dspy.LM(
            model=f"azure/{azure_haiku}",
            api_key=azure_key,
            api_base=azure_endpoint,
            api_version=azure_api_version,
            temperature=0.1,
            max_tokens=2000
        )

        sonnet_lm = dspy.LM(
            model=f"azure/{azure_sonnet}",
            api_key=azure_key,
            api_base=azure_endpoint,
            api_version=azure_api_version,
            temperature=0.1,
            max_tokens=4000
        )

        logger.info(
            f"DSPy configured via Azure: Router={azure_gpt}, "
            f"Reasoner={azure_haiku}, Judge/Synth={azure_sonnet}"
        )

    else:
        # Mode 3: Direct APIs only — no Azure configured
        logger.warning("Azure vars not set — using direct OpenAI + Anthropic APIs")

        if not anthropic_key:
            raise ValueError("No AZURE_API_KEY and no ANTHROPIC_API_KEY found. Set one of them.")
        if not openai_key:
            raise ValueError("No AZURE_API_KEY and no OPENAI_API_KEY found. Set one of them.")

        router_lm = dspy.LM(
            model="openai/gpt-4.1-nano",
            api_key=openai_key,
            temperature=0.0,
            max_tokens=500
        )

        reasoner_lm = dspy.LM(
            model="anthropic/claude-haiku-4-5-20251001",
            api_key=anthropic_key,
            temperature=0.1,
            max_tokens=2000
        )

        sonnet_lm = dspy.LM(
            model="anthropic/claude-sonnet-4-5",
            api_key=anthropic_key,
            temperature=0.1,
            max_tokens=4000
        )

        logger.info("DSPy configured: Router=OpenAI/GPT-4.1-nano, Reasoner=Anthropic/Haiku-4.5, Judge=Anthropic/Sonnet-4.5")

    # Set Haiku as global default — fast for all agent ChainOfThought calls
    dspy.configure(lm=reasoner_lm)

    _cached_config = LMConfig(router=router_lm, reasoner=reasoner_lm, sonnet=sonnet_lm)
    return _cached_config


def get_lm_config() -> Optional[LMConfig]:
    """
    Return the cached LMConfig after configure_dspy() has been called.
    Used by judge and synthesis modules to access the Sonnet LM.
    """
    return _cached_config


def get_dspy_lm() -> dspy.LM:
    """Get the configured default (reasoner) LM instance."""
    if dspy.settings.lm is None:
        raise RuntimeError("DSPy not configured. Call configure_dspy() first.")
    return dspy.settings.lm


def test_dspy_connection() -> bool:
    """
    Test the DSPy connection with all three models.

    Returns:
        True if all connections are successful, False otherwise
    """
    try:
        lm_config = configure_dspy()

        class TestQuery(dspy.Signature):
            """Test query to verify DSPy connection."""
            question: str = dspy.InputField()
            answer: str = dspy.OutputField()

        test_module = dspy.Predict(TestQuery)

        # Test reasoner/Haiku (global default)
        result = test_module(question="What is 2+2?")
        logger.info(f"Reasoner (Haiku) test passed: {result.answer}")

        # Test router (GPT-4.1)
        with dspy.context(lm=lm_config.router):
            result = test_module(question="What is 3+3?")
            logger.info(f"Router (GPT-4.1) test passed: {result.answer}")

        # Test sonnet
        with dspy.context(lm=lm_config.sonnet):
            result = test_module(question="What is 4+4?")
            logger.info(f"Sonnet test passed: {result.answer}")

        return True

    except Exception as e:
        logger.error(f"DSPy connection test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Testing DSPy configuration...")
    success = test_dspy_connection()

    if success:
        logger.info("DSPy is ready for use! All three models verified.")
    else:
        logger.error("DSPy configuration failed. Check your API keys.")
