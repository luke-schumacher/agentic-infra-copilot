"""
DSPy Configuration - Shared LLM Setup for All Agents

Configures DSPy with Groq's Llama 3 70B model for all agents.
Replaces LangChain ChatGroq with native DSPy integration.

Author: Thesis Project - Agentic Infra Co-Pilot
"""

import os
import logging
from dotenv import load_dotenv

import dspy

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def configure_dspy() -> dspy.LM:
    """
    Configure DSPy with Groq backend.

    Uses groq/llama3-70b-8192 as the primary model.
    Must be called at agent startup before using any DSPy signatures.

    Returns:
        Configured DSPy LM instance
    """
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in environment. Please set it in .env file.")

    logger.info("Configuring DSPy with Groq/Llama3-70B-8192...")

    # Configure DSPy with Groq
    lm = dspy.LM(
        model="groq/llama3-70b-8192",
        api_key=groq_api_key,
        temperature=0.1,
        max_tokens=2000
    )

    dspy.configure(lm=lm)

    logger.info("DSPy configured successfully with Groq backend")
    return lm


def get_dspy_lm() -> dspy.LM:
    """
    Get the configured DSPy language model instance.

    Returns:
        Configured DSPy LM for direct use

    Raises:
        RuntimeError: If DSPy has not been configured yet
    """
    if dspy.settings.lm is None:
        raise RuntimeError(
            "DSPy has not been configured. Call configure_dspy() first."
        )
    return dspy.settings.lm


def test_dspy_connection() -> bool:
    """
    Test the DSPy connection with a simple query.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        configure_dspy()

        # Simple test signature
        class TestQuery(dspy.Signature):
            """Test query to verify DSPy connection."""
            question: str = dspy.InputField()
            answer: str = dspy.OutputField()

        test_module = dspy.Predict(TestQuery)
        result = test_module(question="What is 2+2?")

        logger.info(f"DSPy connection test successful. Response: {result.answer}")
        return True

    except Exception as e:
        logger.error(f"DSPy connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the configuration
    logger.info("Testing DSPy configuration...")
    success = test_dspy_connection()

    if success:
        logger.info("DSPy is ready for use!")
    else:
        logger.error("DSPy configuration failed. Check your GROQ_API_KEY.")
