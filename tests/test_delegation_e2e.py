import requests
import json
import uuid
from datetime import datetime
import time

url = "http://localhost:8001/consult"

# Query that should trigger delegation to Siemens (Hardware) or Illigo (Logs)
# Telekom Minister handles "High Latency" (SLA) but needs root cause from others.
test_query = "Telekom reports high latency at the Koumassi microgrid. Is there a hardware fault explaining this?"

payload = {
    "card": {
        "message_id": str(uuid.uuid4()),
        "sender": "orchestrator",
        "recipient": "telekom_minister",
        "intent": "diagnose",
        "priority": "high",
        "payload": {
            "query": test_query,
            "is_symptom": True,
            "location": "Koumassi"
        },
        "documents": [],
        "timestamp": datetime.utcnow().isoformat()
    }
}

print(f"Sending request to {url}...")
print(f"Query: {test_query}")

start_time = time.time()
try:
    response = requests.post(url, json=payload, timeout=60) # Increased timeout for delegation
    duration = time.time() - start_time
    print(f"Request completed in {duration:.2f} seconds.")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        # Pretty print key parts
        response_card = data.get("response_card", {})
        resp_payload = response_card.get("payload", {})
        
        print("\n" + "="*50)
        print("RESPONSE FROM TELEKOM MINISTER")
        print("="*50)
        
        # Check Risk Level (Telekom's domain)
        print(f"Risk Level: {resp_payload.get('risk_level')}")
        print(f"Violated SLAs: {resp_payload.get('violated_slas')}")
        
        # Check Delegation
        delegation = resp_payload.get("delegation", {})
        target_agent = delegation.get("target_agent")
        
        print("\n--- Delegation Decision ---")
        print(f"Target Agent: {target_agent}")
        print(f"Reason: {delegation.get('reason')}")
        
        # Check Specialist Findings
        specialist_findings = resp_payload.get("specialist_findings", {})
        print("\n--- Specialist Findings (Delegation Result) ---")
        print(json.dumps(specialist_findings, indent=2))
        
        if target_agent and target_agent not in ["self", "None"]:
            if specialist_findings.get("error"):
                print("\n[!] Delegation attempted but failed.")
            else:
                print("\n[+] SUCCESS: End-to-End Delegation verified.")
        else:
            print("\n[-] NOTE: No delegation was triggered. The agent might have answered it alone.")
            
    else:
        print(f"Error Response: {response.text}")

except Exception as e:
    print(f"Exception occurred: {e}")