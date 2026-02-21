"""
DSPy Configuration - Multi-Model LLM Setup for All Agents

Two-tier model strategy:
  - Router (classification/routing): OpenAI GPT-4.1-nano ($0.10/$0.40 per MTok)
  - Reasoner (all reasoning): Anthropic Claude 3.5 Haiku ($0.80/$4.00 per MTok)

The reasoner (Haiku) is set as the global default. Router is used explicitly
via dspy.context(lm=router_lm) for EvaluateRequest and DelegateToSpecialist calls.
"""

import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
import dspy

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LMConfig:
    """Holds configured LM instances for the two-tier strategy."""
    router: dspy.LM      # Cheap model for classification
    reasoner: dspy.LM    # Claude model for all reasoning (global default)


def configure_dspy() -> LMConfig:
    """
    Configure DSPy with two-tier model strategy.

    Tier 1 (Router): openai/gpt-4.1-nano - cheap classification
    Tier 2 (Reasoner): anthropic/claude-3-5-haiku-20241022 - Claude reasoning

    Returns:
        LMConfig with both LM instances
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not anthropic_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment.")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not found in environment.")

    # Tier 1: Cheap router for classification tasks
    router_lm = dspy.LM(
        model="openai/gpt-4.1-nano",
        api_key=openai_key,
        temperature=0.0,
        max_tokens=500
    )

    # Tier 2: Claude reasoner for all substantive reasoning
    reasoner_lm = dspy.LM(
        model="anthropic/claude-3-5-haiku-20241022",
        api_key=anthropic_key,
        temperature=0.1,
        max_tokens=2000
    )

    # Set Claude as global default — all ChainOfThought calls use this
    dspy.configure(lm=reasoner_lm)

    logger.info("DSPy configured: Router=GPT-4.1-nano, Reasoner=Claude-3.5-Haiku")
    return LMConfig(router=router_lm, reasoner=reasoner_lm)


def get_dspy_lm() -> dspy.LM:
    """Get the configured default (reasoner) LM instance."""
    if dspy.settings.lm is None:
        raise RuntimeError("DSPy not configured. Call configure_dspy() first.")
    return dspy.settings.lm


def test_dspy_connection() -> bool:
    """
    Test the DSPy connection with both models.

    Returns:
        True if both connections are successful, False otherwise
    """
    try:
        lm_config = configure_dspy()

        class TestQuery(dspy.Signature):
            """Test query to verify DSPy connection."""
            question: str = dspy.InputField()
            answer: str = dspy.OutputField()

        test_module = dspy.Predict(TestQuery)

        # Test reasoner (Claude Haiku - global default)
        result = test_module(question="What is 2+2?")
        logger.info(f"Reasoner (Claude Haiku) test passed: {result.answer}")

        # Test router (GPT-4.1-nano)
        with dspy.context(lm=lm_config.router):
            result = test_module(question="What is 3+3?")
            logger.info(f"Router (GPT-4.1-nano) test passed: {result.answer}")

        return True

    except Exception as e:
        logger.error(f"DSPy connection test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Testing DSPy configuration...")
    success = test_dspy_connection()

    if success:
        logger.info("DSPy is ready for use! Both models verified.")
    else:
        logger.error("DSPy configuration failed. Check your API keys.")
