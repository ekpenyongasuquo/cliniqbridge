"""
CliniqBridge - MCP Server (JSON-RPC 2.0 compliant)
Prompt Opinion FHIR Context Extension Compliant
Updated for MaternaFlow - UiPath AgentHack 2026
"""
 
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from typing import Optional
from datetime import datetime
 
app = FastAPI(title="CliniqBridge MCP Server", version="1.1.0")
 
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
    },
    {
        "name": "get_observations",
        "description": "Returns lab results and clinical observations for a patient from FHIR Observation resources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "category": {"type": "string", "description": "Observation category: laboratory, vital-signs, etc. (optional)"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id"]
        }
    },
    {
        "name": "create_observation",
        "description": "Creates a new clinical observation or ANC visit finding in the FHIR server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "The FHIR Patient resource ID"},
                "code": {"type": "string", "description": "LOINC or SNOMED code for the observation"},
                "display": {"type": "string", "description": "Human-readable name of the observation"},
                "value": {"type": "string", "description": "The observed value (e.g. 110/70, 12.5)"},
                "unit": {"type": "string", "description": "Unit of measurement (e.g. mmHg, g/dL)"},
                "status": {"type": "string", "description": "Observation status: final, preliminary (optional, defaults to final)"},
                "fhir_base_url": {"type": "string", "description": "Base URL of the FHIR server (optional)"}
            },
            "required": ["patient_id", "code", "display", "value"]
        }
    }
]
 
# -------------------------------------------
# FHIR Helpers
# -------------------------------------------
 
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
 
async def fhir_post(path: str, fhir_base: str, body: dict, token: Optional[str] = None):
    headers = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{fhir_base.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=body, headers=headers)
        if response.status_code not in [200, 201]:
            return {"error": f"FHIR error {response.status_code}", "url": url}
        return response.json()
 
# -------------------------------------------
# Tool Implementations
# -------------------------------------------
 
async def tool_get_patient_summary(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Patient/{pid}", fhir_base, token)
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
 
 
async def tool_get_conditions(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Condition?patient={pid}&clinical-status=active&_sort=-onset-date&_count=20", fhir_base, token)
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
 
 
async def tool_get_medications(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"MedicationRequest?patient={pid}&status=active&_count=20", fhir_base, token)
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
 
 
async def tool_get_encounters(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    if not pid:
        return {"error": "patient_id is required"}
    data = await fhir_get(f"Encounter?patient={pid}&_sort=-date&_count=10", fhir_base, token)
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
 
 
async def tool_get_observations(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    category = params.get("category", "laboratory")
    if not pid:
        return {"error": "patient_id is required"}
    path = f"Observation?patient={pid}&category={category}&_sort=-date&_count=20"
    data = await fhir_get(path, fhir_base, token)
    if "error" in data:
        return data
    observations = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        codings = code_obj.get("coding", [{}])
        display = codings[0].get("display") or code_obj.get("text", "Unknown")
        value_quantity = resource.get("valueQuantity", {})
        value = value_quantity.get("value", resource.get("valueString", "N/A"))
        unit = value_quantity.get("unit", "")
        ref_range = resource.get("referenceRange", [{}])
        low = ref_range[0].get("low", {}).get("value", "") if ref_range else ""
        high = ref_range[0].get("high", {}).get("value", "") if ref_range else ""
        interpretation = resource.get("interpretation", [{}])
        interp_code = interpretation[0].get("coding", [{}])[0].get("code", "") if interpretation else ""
        abnormal = interp_code in ["H", "L", "HH", "LL", "A", "AA"]
        observations.append({
            "observation": display,
            "value": f"{value} {unit}".strip(),
            "reference_range": f"{low}–{high} {unit}".strip() if low and high else "N/A",
            "abnormal": abnormal,
            "date": resource.get("effectiveDateTime", "Unknown"),
            "status": resource.get("status", "unknown")
        })
    return {
        "patient_id": pid,
        "category": category,
        "count": len(observations),
        "observations": observations or [{"observation": "No observations found"}]
    }
 
 
async def tool_create_observation(params: dict, req_headers: dict) -> dict:
    pid = params.get("patient_id") or req_headers.get("x-patient-id")
    fhir_base = params.get("fhir_base_url") or req_headers.get("x-fhir-server-url") or DEFAULT_FHIR_BASE
    token = req_headers.get("x-fhir-access-token")
    if not pid:
        return {"error": "patient_id is required"}
    for required_field in ["code", "display", "value"]:
        if not params.get(required_field):
            return {"error": f"{required_field} is required"}
    observation_resource = {
        "resourceType": "Observation",
        "status": params.get("status", "final"),
        "category": [{
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "laboratory",
                "display": "Laboratory"
            }]
        }],
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": params.get("code"),
                "display": params.get("display")
            }],
            "text": params.get("display")
        },
        "subject": {"reference": f"Patient/{pid}"},
        "effectiveDateTime": datetime.utcnow().isoformat() + "Z",
        "valueQuantity": {
            "value": params.get("value"),
            "unit": params.get("unit", ""),
            "system": "http://unitsofmeasure.org"
        }
    }
    data = await fhir_post("Observation", fhir_base, observation_resource, token)
    if "error" in data:
        return data
    return {
        "success": True,
        "observation_id": data.get("id"),
        "patient_id": pid,
        "observation": params.get("display"),
        "value": f"{params.get('value')} {params.get('unit', '')}".strip(),
        "recorded_at": datetime.utcnow().isoformat()
    }
 
# -------------------------------------------
# JSON-RPC 2.0 Dispatcher
# -------------------------------------------
 
async def handle_jsonrpc(body: dict, req_headers: dict) -> dict:
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
            "capabilities": {
                "tools": {},
                "extensions": {
                    "ai.promptopinion/fhir-context": {}
                }
            },
            "serverInfo": {"name": "CliniqBridge", "version": "1.1.0"}
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
            "get_observations": tool_get_observations,
            "create_observation": tool_create_observation,
        }
        if tool_name not in tool_map:
            return err(-32601, f"Tool not found: {tool_name}")
        result = await tool_map[tool_name](tool_params, req_headers)
        return ok({"content": [{"type": "text", "text": str(result)}], "result": result})
 
    return err(-32601, f"Method not found: {method}")
 
# -------------------------------------------
# Routes
# -------------------------------------------
 
async def process_request(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
    req_headers = {k.lower(): v for k, v in request.headers.items()}
    result = await handle_jsonrpc(body, req_headers)
    return JSONResponse(result)
 
@app.get("/")
async def root():
    return {
        "name": "CliniqBridge",
        "version": "1.1.0",
        "description": "MCP server for FHIR patient summary, history retrieval, and observation recording",
        "sharp_compliant": True,
        "prompt_opinion_extension": "ai.promptopinion/fhir-context",
        "tools": [t["name"] for t in TOOLS]
    }
 
@app.post("/")
async def root_post(request: Request):
    return await process_request(request)
 
@app.get("/mcp")
async def mcp_get(request: Request):
    return JSONResponse({
        "name": "CliniqBridge",
        "version": "1.1.0",
        "description": "MCP server for FHIR patient summary, history retrieval, and observation recording",
        "tools": [t["name"] for t in TOOLS]
    })
 
@app.post("/mcp")
async def mcp_post(request: Request):
    return await process_request(request)
 
@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    return {
        "schema_version": "1.0",
        "name": "CliniqBridge",
        "description": "Retrieve structured patient summaries, clinical history, and record observations from FHIR R4 servers.",
        "endpoint": "/mcp",
        "transport": "http",
        "extensions": {"ai.promptopinion/fhir-context": {}},
        "tools": TOOLS
    }
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "CliniqBridge", "version": "1.1.0", "timestamp": datetime.utcnow().isoformat()}
 