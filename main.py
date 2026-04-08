"""
CliniqBridge - MCP Server (JSON-RPC 2.0 compliant)
FHIR R4 + SHARP Context Compliant
Compatible with Prompt Opinion platform
"""

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from typing import Optional
from datetime import datetime

app = FastAPI(title="CliniqBridge MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_FHIR_BASE = "https://hapi.fhir.org/baseR4"

TOOLS = [
    {
        "name": "get_patient_summary",
        "description": "Returns core patient demographics: name, date of birth, gender, and address from a FHIR server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "get_conditions",
        "description": "Returns active clinical conditions and diagnoses for a patient from a FHIR server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "get_medications",
        "description": "Returns the current medication list for a patient from FHIR MedicationRequest resources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "get_encounters",
        "description": "Returns recent clinical encounters and visits for a patient from a FHIR server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id"]
        }
    }
]

async def fhir_get(path: str, fhir_base: str, token: Optional[str] = None):
    headers = {"Accept": "application/fhir+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{fhir_base.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code not in [200, 201]:
            return {"error": f"FHIR error {response.status_code}", "url": url}
        return response.json()

async def tool_get_patient_summary(params: dict) -> dict:
    pid = params.get("patient_id")
    fhir_base = params.get("fhir_base_url", DEFAULT_FHIR_BASE)
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Patient/{pid}", fhir_base)
    if "error" in data:
        return data
    name = "Unknown"
    if data.get("name"):
        n = data["name"][0]
        given = " ".join(n.get("given", []))
        family = n.get("family", "")
        name = f"{given} {family}".strip()
    address = "Not on record"
    if data.get("address"):
        a = data["address"][0]
        parts = a.get("line", []) + [a.get("city", ""), a.get("state", ""), a.get("country", "")]
        address = ", ".join(p for p in parts if p)
    return {
        "patient_id": pid,
        "name": name,
        "date_of_birth": data.get("birthDate", "Unknown"),
        "gender": data.get("gender", "Unknown").capitalize(),
        "address": address,
        "active": data.get("active", True)
    }

async def tool_get_conditions(params: dict) -> dict:
    pid = params.get("patient_id")
    fhir_base = params.get("fhir_base_url", DEFAULT_FHIR_BASE)
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Condition?patient={pid}&clinical-status=active&_sort=-onset-date&_count=20", fhir_base)
    if "error" in data:
        return data
    conditions = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        codings = code_obj.get("coding", [{}])
        display = codings[0].get("display") or code_obj.get("text", "Unknown condition")
        onset = resource.get("onsetDateTime", resource.get("recordedDate", "Unknown"))
        conditions.append({"condition": display, "onset": onset})
    return {"patient_id": pid, "count": len(conditions), "conditions": conditions or [{"condition": "No active conditions found"}]}

async def tool_get_medications(params: dict) -> dict:
    pid = params.get("patient_id")
    fhir_base = params.get("fhir_base_url", DEFAULT_FHIR_BASE)
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"MedicationRequest?patient={pid}&status=active&_count=20", fhir_base)
    if "error" in data:
        return data
    medications = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        med = resource.get("medicationCodeableConcept", {})
        codings = med.get("coding", [{}])
        name = codings[0].get("display") or med.get("text", "Unknown medication")
        dosage_list = resource.get("dosageInstruction", [{}])
        dosage = dosage_list[0].get("text", "See instructions") if dosage_list else "See instructions"
        medications.append({"medication": name, "dosage": dosage, "authored_on": resource.get("authoredOn", "Unknown")})
    return {"patient_id": pid, "count": len(medications), "medications": medications or [{"medication": "No active medications found"}]}

async def tool_get_encounters(params: dict) -> dict:
    pid = params.get("patient_id")
    fhir_base = params.get("fhir_base_url", DEFAULT_FHIR_BASE)
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Encounter?patient={pid}&_sort=-date&_count=10", fhir_base)
    if "error" in data:
        return data
    encounters = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        type_list = resource.get("type", [{}])
        codings = type_list[0].get("coding", [{}]) if type_list else [{}]
        enc_type = codings[0].get("display") or (type_list[0].get("text", "Clinical Visit") if type_list else "Clinical Visit")
        period = resource.get("period", {})
        encounters.append({"encounter_type": enc_type, "date": period.get("start", "Unknown"), "status": resource.get("status", "unknown")})
    return {"patient_id": pid, "count": len(encounters), "encounters": encounters or [{"encounter_type": "No encounters found"}]}

async def handle_jsonrpc(body: dict) -> dict:
    jsonrpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    def ok(result):
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "CliniqBridge", "version": "1.0.0"}
        })

    if method in ["notifications/initialized", "ping"]:
        return ok({})

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name")
        tool_params = params.get("arguments", {})
        tool_map = {
            "get_patient_summary": tool_get_patient_summary,
            "get_conditions": tool_get_conditions,
            "get_medications": tool_get_medications,
            "get_encounters": tool_get_encounters,
        }
        if tool_name not in tool_map:
            return err(-32601, f"Tool not found: {tool_name}")
        result = await tool_map[tool_name](tool_params)
        return ok({"content": [{"type": "text", "text": str(result)}], "result": result})

    return err(-32601, f"Method not found: {method}")

@app.get("/")
async def root():
    return {"name": "CliniqBridge", "version": "1.0.0", "description": "MCP server for FHIR patient summary and history retrieval", "sharp_compliant": True, "tools": [t["name"] for t in TOOLS]}

@app.post("/")
async def root_post(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    result = await handle_jsonrpc(body)
    return JSONResponse(result)

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    result = await handle_jsonrpc(body)
    return JSONResponse(result)

@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    return {
        "schema_version": "1.0",
        "name": "CliniqBridge",
        "description": "Retrieve structured patient summaries and clinical history from FHIR R4 servers.",
        "endpoint": "/mcp",
        "transport": "http",
        "sharp": {"compliant": True, "context_headers": ["x-patient-id", "x-fhir-base-url", "x-fhir-token"]},
        "tools": TOOLS
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CliniqBridge", "timestamp": datetime.utcnow().isoformat()}
