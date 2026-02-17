import requests
import json
import uuid
from datetime import datetime
import time

url = "http://localhost:8001/consult"

# MRI healthcare query that should trigger delegation to Hardware Agent
test_query = (
    "Customer mr200103 is experiencing recurring thermal shutdowns on their MAGNETOM Sola "
    "every 90 minutes. The gradient coil temperature sensor readings are drifting. "
    "Is this a known hardware failure mode, and what are the safety implications?"
)

payload = {
    "card": {
        "message_id": str(uuid.uuid4()),
        "sender": "orchestrator",
        "recipient": "governance_agent",
        "intent": "diagnose",
        "priority": "high",
        "payload": {
            "query": test_query,
            "is_symptom": True,
            "location": "Munich",
            "customer_id": "mr200103"
        },
        "documents": [],
        "timestamp": datetime.utcnow().isoformat()
    }
}

print(f"Sending request to {url}...")
print(f"Query: {test_query}")

start_time = time.time()
try:
    response = requests.post(url, json=payload, timeout=60)
    duration = time.time() - start_time
    print(f"Request completed in {duration:.2f} seconds.")
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        response_card = data.get("response_card", {})
        resp_payload = response_card.get("payload", {})

        print("\n" + "=" * 50)
        print("RESPONSE FROM GOVERNANCE AGENT (The Anthropologist)")
        print("=" * 50)

        # Check Risk Level
        print(f"Risk Level: {resp_payload.get('risk_level')}")
        print(f"Contextual Explanation: {resp_payload.get('contextual_explanation', '')[:200]}")

        # Check Delegation
        delegation = resp_payload.get("delegation", {})
        target_agent = delegation.get("target_agent")

        print("\n--- Delegation Decision ---")
        print(f"Target Agent: {target_agent}")
        print(f"Reason: {delegation.get('reason')}")

        # Check Specialist Findings
        specialist_findings = resp_payload.get("specialist_findings", {})
        print("\n--- Specialist Findings (Delegation Result) ---")
        if specialist_findings:
            spec_card = specialist_findings.get("response_card", {})
            spec_payload = spec_card.get("payload", {})
            print(f"Diagnosis: {spec_payload.get('diagnosis', 'N/A')}")
            print(f"Severity: {spec_payload.get('severity', 'N/A')}")
            print(f"Affected Component: {spec_payload.get('affected_component', 'N/A')}")
            print(f"Requires Service: {spec_payload.get('requires_service', 'N/A')}")
        else:
            print("No specialist findings returned.")

        # Check reasoning chain visualization
        viz = resp_payload.get("reasoning_chain_visualization", {})
        if viz:
            print("\n--- Reasoning Chain ---")
            print(f"Graph Notation: {viz.get('graph_notation', 'N/A')}")
            print(f"Emergence Score: {viz.get('emergence_score', 'N/A')}")

        # Integration result
        if resp_payload.get("integration_performed"):
            print("\n--- Integrated Analysis ---")
            print(f"Root Cause: {resp_payload.get('root_cause', 'N/A')}")
            print(f"Integrated Actions: {resp_payload.get('recommended_actions', 'N/A')}")

        if target_agent and target_agent not in ["self", "None"]:
            if specialist_findings and not specialist_findings.get("error"):
                print("\n[+] SUCCESS: End-to-End Delegation verified.")
            else:
                print("\n[!] Delegation attempted but failed or returned error.")
        else:
            print("\n[-] NOTE: No delegation was triggered.")

    else:
        print(f"Error Response: {response.text}")

except Exception as e:
    print(f"Exception occurred: {e}")
