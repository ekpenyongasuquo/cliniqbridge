"""
CliniqBridge - MCP Server for Patient Summary & History Retrieval
FHIR R4 + SHARP Context Compliant
"""

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import json
from typing import Optional
from datetime import datetime

app = FastAPI(
    title="CliniqBridge MCP Server",
    description="An MCP-powered FHIR patient context tool for clinical summary & history retrieval.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Default public FHIR test server
DEFAULT_FHIR_BASE = "https://hapi.fhir.org/baseR4"


# ─────────────────────────────────────────────
# SHARP Context Helper
# ─────────────────────────────────────────────

def extract_sharp_context(
    x_patient_id: Optional[str] = None,
    x_fhir_base_url: Optional[str] = None,
    x_fhir_token: Optional[str] = None,
):
    """Extract SHARP context from request headers."""
    return {
        "patient_id": x_patient_id,
        "fhir_base_url": x_fhir_base_url or DEFAULT_FHIR_BASE,
        "fhir_token": x_fhir_token,
    }


async def fhir_get(path: str, fhir_base: str, token: Optional[str] = None):
    """Make a FHIR API GET request."""
    headers = {"Accept": "application/fhir+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{fhir_base.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"FHIR resource not found: {url}")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"FHIR server error: {response.text}")
        return response.json()


# ─────────────────────────────────────────────
# MCP Manifest
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "CliniqBridge",
        "version": "1.0.0",
        "description": "MCP server for FHIR patient summary and history retrieval",
        "sharp_compliant": True,
        "tools": [
            "get_patient_summary",
            "get_conditions",
            "get_medications",
            "get_encounters"
        ]
    }


@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    """MCP discovery manifest."""
    return {
        "schema_version": "1.0",
        "name": "CliniqBridge",
        "description": "Retrieve structured patient summaries and clinical history from FHIR R4 servers.",
        "sharp": {
            "compliant": True,
            "context_headers": [
                "x-patient-id",
                "x-fhir-base-url",
                "x-fhir-token"
            ]
        },
        "tools": [
            {
                "name": "get_patient_summary",
                "description": "Returns core patient demographics: name, date of birth, gender, and address.",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID", "required": False}
                }
            },
            {
                "name": "get_conditions",
                "description": "Returns a list of active clinical conditions/diagnoses for the patient.",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID", "required": False}
                }
            },
            {
                "name": "get_medications",
                "description": "Returns the patient's current medication list from MedicationRequest resources.",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID", "required": False}
                }
            },
            {
                "name": "get_encounters",
                "description": "Returns a list of recent clinical encounters/visits for the patient.",
                "parameters": {
                    "patient_id": {"type": "string", "description": "FHIR Patient resource ID", "required": False}
                }
            }
        ]
    }


# ─────────────────────────────────────────────
# Tool 1: Patient Summary
# ─────────────────────────────────────────────

@app.get("/tools/get_patient_summary")
async def get_patient_summary(
    patient_id: Optional[str] = None,
    x_patient_id: Optional[str] = Header(default=None),
    x_fhir_base_url: Optional[str] = Header(default=None),
    x_fhir_token: Optional[str] = Header(default=None),
):
    """
    Tool: get_patient_summary
    Returns core demographics for a FHIR patient.
    Supports SHARP context via headers.
    """
    ctx = extract_sharp_context(x_patient_id, x_fhir_base_url, x_fhir_token)
    pid = patient_id or ctx["patient_id"]

    if not pid:
        raise HTTPException(status_code=400, detail="patient_id is required (query param or x-patient-id header)")

    data = await fhir_get(f"Patient/{pid}", ctx["fhir_base_url"], ctx["fhir_token"])

    # Parse name
    name = "Unknown"
    if data.get("name"):
        n = data["name"][0]
        given = " ".join(n.get("given", []))
        family = n.get("family", "")
        name = f"{given} {family}".strip()

    # Parse address
    address = "Not on record"
    if data.get("address"):
        a = data["address"][0]
        parts = a.get("line", []) + [a.get("city", ""), a.get("state", ""), a.get("country", "")]
        address = ", ".join(p for p in parts if p)

    return {
        "tool": "get_patient_summary",
        "patient_id": pid,
        "result": {
            "name": name,
            "date_of_birth": data.get("birthDate", "Unknown"),
            "gender": data.get("gender", "Unknown").capitalize(),
            "address": address,
            "active": data.get("active", True),
            "fhir_id": data.get("id"),
        },
        "sharp_context_used": bool(x_patient_id or x_fhir_base_url)
    }


# ─────────────────────────────────────────────
# Tool 2: Conditions
# ─────────────────────────────────────────────

@app.get("/tools/get_conditions")
async def get_conditions(
    patient_id: Optional[str] = None,
    x_patient_id: Optional[str] = Header(default=None),
    x_fhir_base_url: Optional[str] = Header(default=None),
    x_fhir_token: Optional[str] = Header(default=None),
):
    """
    Tool: get_conditions
    Returns active clinical conditions/diagnoses for the patient.
    """
    ctx = extract_sharp_context(x_patient_id, x_fhir_base_url, x_fhir_token)
    pid = patient_id or ctx["patient_id"]

    if not pid:
        raise HTTPException(status_code=400, detail="patient_id is required")

    data = await fhir_get(
        f"Condition?patient={pid}&clinical-status=active&_sort=-onset-date&_count=20",
        ctx["fhir_base_url"],
        ctx["fhir_token"]
    )

    conditions = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        code_obj = resource.get("code", {})
        codings = code_obj.get("coding", [{}])
        display = codings[0].get("display") or code_obj.get("text", "Unknown condition")
        onset = resource.get("onsetDateTime", resource.get("recordedDate", "Unknown date"))

        conditions.append({
            "condition": display,
            "onset": onset,
            "status": resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "unknown")
        })

    return {
        "tool": "get_conditions",
        "patient_id": pid,
        "count": len(conditions),
        "result": conditions or [{"condition": "No active conditions found", "onset": None, "status": "none"}],
        "sharp_context_used": bool(x_patient_id or x_fhir_base_url)
    }


# ─────────────────────────────────────────────
# Tool 3: Medications
# ─────────────────────────────────────────────

@app.get("/tools/get_medications")
async def get_medications(
    patient_id: Optional[str] = None,
    x_patient_id: Optional[str] = Header(default=None),
    x_fhir_base_url: Optional[str] = Header(default=None),
    x_fhir_token: Optional[str] = Header(default=None),
):
    """
    Tool: get_medications
    Returns current MedicationRequest resources for the patient.
    """
    ctx = extract_sharp_context(x_patient_id, x_fhir_base_url, x_fhir_token)
    pid = patient_id or ctx["patient_id"]

    if not pid:
        raise HTTPException(status_code=400, detail="patient_id is required")

    data = await fhir_get(
        f"MedicationRequest?patient={pid}&status=active&_count=20",
        ctx["fhir_base_url"],
        ctx["fhir_token"]
    )

    medications = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        med = resource.get("medicationCodeableConcept", {})
        codings = med.get("coding", [{}])
        name = codings[0].get("display") or med.get("text", "Unknown medication")

        dosage_list = resource.get("dosageInstruction", [{}])
        dosage_text = dosage_list[0].get("text", "See instructions") if dosage_list else "See instructions"

        medications.append({
            "medication": name,
            "dosage": dosage_text,
            "status": resource.get("status", "unknown"),
            "authored_on": resource.get("authoredOn", "Unknown date")
        })

    return {
        "tool": "get_medications",
        "patient_id": pid,
        "count": len(medications),
        "result": medications or [{"medication": "No active medications found", "dosage": None, "status": "none", "authored_on": None}],
        "sharp_context_used": bool(x_patient_id or x_fhir_base_url)
    }


# ─────────────────────────────────────────────
# Tool 4: Encounters
# ─────────────────────────────────────────────

@app.get("/tools/get_encounters")
async def get_encounters(
    patient_id: Optional[str] = None,
    x_patient_id: Optional[str] = Header(default=None),
    x_fhir_base_url: Optional[str] = Header(default=None),
    x_fhir_token: Optional[str] = Header(default=None),
):
    """
    Tool: get_encounters
    Returns recent clinical encounters/visits for the patient.
    """
    ctx = extract_sharp_context(x_patient_id, x_fhir_base_url, x_fhir_token)
    pid = patient_id or ctx["patient_id"]

    if not pid:
        raise HTTPException(status_code=400, detail="patient_id is required")

    data = await fhir_get(
        f"Encounter?patient={pid}&_sort=-date&_count=10",
        ctx["fhir_base_url"],
        ctx["fhir_token"]
    )

    encounters = []
    for entry in data.get("entry", []):
        resource = entry.get("resource", {})
        type_list = resource.get("type", [{}])
        codings = type_list[0].get("coding", [{}]) if type_list else [{}]
        enc_type = codings[0].get("display") or type_list[0].get("text", "Clinical Visit") if type_list else "Clinical Visit"

        period = resource.get("period", {})
        start = period.get("start", "Unknown date")

        encounters.append({
            "encounter_type": enc_type,
            "date": start,
            "status": resource.get("status", "unknown"),
            "class": resource.get("class", {}).get("display", resource.get("class", {}).get("code", "Unknown"))
        })

    return {
        "tool": "get_encounters",
        "patient_id": pid,
        "count": len(encounters),
        "result": encounters or [{"encounter_type": "No encounters found", "date": None, "status": "none", "class": None}],
        "sharp_context_used": bool(x_patient_id or x_fhir_base_url)
    }


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "CliniqBridge", "timestamp": datetime.utcnow().isoformat()}
