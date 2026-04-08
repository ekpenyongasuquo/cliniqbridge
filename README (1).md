# 🏥 CliniqBridge

**An MCP-powered FHIR Patient Context Tool for Clinical Summary & History Retrieval**

> Built for the *Agents Assemble: The Healthcare AI Endgame* Hackathon on Prompt Opinion.

---

## What It Does

CliniqBridge is a SHARP-compliant MCP server that connects to any FHIR R4 server and exposes four clinical tools:

| Tool | Description |
|---|---|
| `get_patient_summary` | Name, DOB, gender, address |
| `get_conditions` | Active diagnoses & conditions |
| `get_medications` | Current medication list |
| `get_encounters` | Recent clinical visits |

---

## SHARP Context Support

CliniqBridge supports Prompt Opinion's SHARP extension spec. Pass patient context via headers:

| Header | Description |
|---|---|
| `x-patient-id` | FHIR Patient resource ID |
| `x-fhir-base-url` | Base URL of the FHIR server |
| `x-fhir-token` | Bearer token (if auth required) |

If headers are not provided, `patient_id` can be passed as a query parameter and the default HAPI FHIR public server is used.

---

## Quick Start (Local)

```bash
git clone https://github.com/YOUR_USERNAME/cliniqbridge.git
cd cliniqbridge
pip install -r requirements.txt
uvicorn main:app --reload
```

Visit: http://localhost:8000

---

## API Endpoints

### MCP Manifest
```
GET /.well-known/mcp.json
```

### Tools
```
GET /tools/get_patient_summary?patient_id=592
GET /tools/get_conditions?patient_id=592
GET /tools/get_medications?patient_id=592
GET /tools/get_encounters?patient_id=592
```

### With SHARP Headers
```
GET /tools/get_patient_summary
Headers:
  x-patient-id: 592
  x-fhir-base-url: https://hapi.fhir.org/baseR4
```

### Health Check
```
GET /health
```

---

## Deployment (Render.com)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml` and deploys

---

## Tech Stack

- **Python 3.11** + **FastAPI**
- **HTTPX** for async FHIR requests
- **HAPI FHIR R4** public test server
- **SHARP** context header propagation
- **Render.com** for deployment

---

## License

MIT — built for the Agents Assemble Hackathon 2026.
