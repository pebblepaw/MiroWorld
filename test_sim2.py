import requests

# 1. Create session
res = requests.post("http://localhost:8000/api/v2/console/session/create")
session_id = res.json()["session_id"]
print("Session:", session_id)

# 2. Upload doc
with open("Sample_Inputs/CNA SHrinking Birth Rate.docx", "rb") as f:
    res = requests.post(f"http://localhost:8000/api/v2/console/session/{session_id}/knowledge/upload", files={"file": f})
print("Upload:", res.status_code)

# 3. Generate agents
res = requests.post(f"http://localhost:8000/api/v2/console/session/{session_id}/sampling/preview", json={
    "sample_count": 4,
    "mode": "affected_groups",
    "instructions": ""
})
print("Sampling:", res.status_code)

# 4. Start simulation
res = requests.post(f"http://localhost:8000/api/v2/console/session/{session_id}/simulation/start", json={
    "policy_summary": "Test",
    "rounds": 3
})
print("Start sim:", res.status_code, res.text)
