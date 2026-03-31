#!/usr/bin/env python3
"""
Test Azure API Connection
Verifies that the Azure endpoint and deployment names are correctly configured.
"""

import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def test_azure_config():
    """Test Azure configuration from environment variables."""
    print("=" * 60)
    print("Azure API Configuration Test")
    print("=" * 60)
    
    # Check environment variables
    azure_key = os.getenv("AZURE_API_KEY")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")
    azure_api_version = os.getenv("AZURE_API_VERSION")
    azure_gpt = os.getenv("AZURE_DEPLOYMENT_GPT")
    azure_haiku = os.getenv("AZURE_DEPLOYMENT_HAIKU")
    azure_sonnet = os.getenv("AZURE_DEPLOYMENT_SONNET")
    
    print("\n✓ Environment Variables:")
    print(f"  AZURE_ENDPOINT:            {azure_endpoint}")
    print(f"  AZURE_API_VERSION:         {azure_api_version}")
    print(f"  AZURE_API_KEY:             {'✓ Set' if azure_key else '✗ Missing'}")
    print(f"  AZURE_DEPLOYMENT_GPT:      {azure_gpt}")
    print(f"  AZURE_DEPLOYMENT_HAIKU:    {azure_haiku}")
    print(f"  AZURE_DEPLOYMENT_SONNET:   {azure_sonnet}")
    
    if not all([azure_key, azure_endpoint, azure_api_version]):
        print("\n✗ Missing required Azure environment variables!")
        return False
    
    # Test DSPy configuration
    print("\n" + "=" * 60)
    print("Testing DSPy Configuration...")
    print("=" * 60)
    
    try:
        from agents.shared.dspy_config import test_dspy_connection
        success = test_dspy_connection()
        
        if success:
            print("\n" + "=" * 60)
            print("✓ SUCCESS! Azure API is properly configured.")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("✗ FAILED! Check the error messages above.")
            print("=" * 60)
            return False
            
    except Exception as e:
        print(f"\n✗ Error testing DSPy connection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_azure_config()
    sys.exit(0 if success else 1)
