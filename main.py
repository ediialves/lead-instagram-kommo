import os
import re
import logging

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KOMMO_API_TOKEN = os.environ.get("KOMMO_API_TOKEN", "")
KOMMO_BASE_URL = "https://allinimportsjlle.kommo.com"
PIPELINE_ID = 10334455
STATUS_ID = 102403275

app = FastAPI(title="Lead Instagram → Kommo")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    body = exc.body
    safe_errors = [
        {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg"), "input": e.get("input")}
        for e in exc.errors()
    ]
    logger.warning("Validação falhou — body recebido: %s | erros: %s", body, safe_errors)
    return JSONResponse(
        status_code=422,
        content={"detail": safe_errors},
    )


PHONE_WITH_COUNTRY = re.compile(r"^\+55\d{10,11}$")
PHONE_LOCAL = re.compile(r"^\d{10,11}$")
TEMPLATE_VAR = re.compile(r"\{\{.+?\}\}")

TEMPLATE_ERROR = (
    "variável não foi substituída corretamente — "
    "verifique a configuração do Request body na Suvvy"
)


class LeadPayload(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if TEMPLATE_VAR.search(v):
            raise ValueError(TEMPLATE_ERROR)
        v = v.strip()
        if not v:
            raise ValueError("nome não pode ser vazio")
        return v.split()[0]

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        if TEMPLATE_VAR.search(v):
            raise ValueError(TEMPLATE_ERROR)
        v = re.sub(r"[\s\-\(\)]", "", v)
        if PHONE_WITH_COUNTRY.match(v):
            return v
        if PHONE_LOCAL.match(v):
            return f"+55{v}"
        raise ValueError(
            "telefone inválido — use DDD+número (ex: 47999998888) ou +55DDNNNNNNNNN"
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook/novo-lead")
async def novo_lead(payload: LeadPayload):
    if not KOMMO_API_TOKEN:
        logger.error("KOMMO_API_TOKEN não configurado")
        raise HTTPException(status_code=500, detail="Token do Kommo não configurado")

    body = [
        {
            "name": payload.name,
            "pipeline_id": PIPELINE_ID,
            "status_id": STATUS_ID,
            "_embedded": {
                "tags": [{"name": "bot-instagram"}],
                "contacts": [
                    {
                        "first_name": payload.name,
                        "custom_fields_values": [
                            {
                                "field_code": "PHONE",
                                "values": [
                                    {"value": payload.phone, "enum_code": "MOB"}
                                ],
                            }
                        ],
                    }
                ]
            },
        }
    ]

    headers = {
        "Authorization": f"Bearer {KOMMO_API_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                f"{KOMMO_BASE_URL}/api/v4/leads/complex",
                json=body,
                headers=headers,
            )
        except httpx.RequestError as e:
            logger.error("Erro de conexão com Kommo: %s", e)
            raise HTTPException(status_code=502, detail="Falha ao conectar no Kommo")

    if resp.status_code not in (200, 201):
        logger.error(
            "Kommo retornou %s: %s", resp.status_code, resp.text
        )
        raise HTTPException(
            status_code=502,
            detail=f"Kommo respondeu com status {resp.status_code}",
        )

    data = resp.json()
    lead_id = data[0].get("id") if isinstance(data, list) and data else None
    logger.info("Lead criado com sucesso — id=%s, nome=%s", lead_id, payload.name)

    return {"success": True, "lead_id": lead_id}
