import os
import re
import logging

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KOMMO_API_TOKEN = os.environ.get("KOMMO_API_TOKEN", "")
KOMMO_BASE_URL = "https://allinimportsjlle.kommo.com"
PIPELINE_ID = 10334455
STATUS_ID = 102403275

app = FastAPI(title="Lead Instagram → Kommo")

PHONE_RE = re.compile(r"^\+55\d{10,11}$")


class LeadPayload(BaseModel):
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome não pode ser vazio")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        v = re.sub(r"[\s\-\(\)]", "", v)
        if not PHONE_RE.match(v):
            raise ValueError(
                "telefone inválido — use formato +55DDNNNNNNNNN (ex: +5511999998888)"
            )
        return v


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
