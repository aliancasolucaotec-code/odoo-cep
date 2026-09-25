"""Recebe um lead do Odoo, consulta o ViaCEP e devolve o endereço ao Odoo."""

import logging
import os
import re
import secrets

import httpx
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
log = logging.getLogger("odoo_cep")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/consultar-cep/{token}")
async def consultar_cep(token: str, request: Request):
    expected = os.getenv("WEBHOOK_TOKEN", "")
    callback = os.getenv("ODOO_WEBHOOK_URL", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(403, "Acesso negado")
    if not callback.startswith("https://"):
        raise HTTPException(503, "Configure ODOO_WEBHOOK_URL com a URL HTTPS do Odoo")

    try:
        data = await request.json()
    except ValueError:
        raise HTTPException(400, "Envie JSON válido")
    if not isinstance(data, dict) or data.get("_model") != "crm.lead":
        raise HTTPException(400, "Esperado um lead do modelo crm.lead")
    try:
        record_id = int(data.get("_id") or data.get("id"))
    except (ValueError, TypeError):
        raise HTTPException(400, "ID do lead ausente")
    if record_id <= 0:
        raise HTTPException(400, "ID do lead inválido")

    cep = re.sub(r"\D", "", str(data.get("zip") or ""))
    if len(cep) != 8:
        raise HTTPException(422, "CEP deve ter 8 dígitos")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await client.get(f"https://viacep.com.br/ws/{cep}/json/")
            result.raise_for_status()
            address = result.json()
            if address.get("erro") is True:
                raise HTTPException(404, "CEP não encontrado")
            payload = {
                "_model": "crm.lead",
                "_id": record_id,
                "zip": cep,
                "street": address.get("logradouro") or "",
                "city": address.get("localidade") or "",
                "uf": address.get("uf") or "",
                "bairro": address.get("bairro") or "",
            }
            response = await client.post(callback, json=payload)
            response.raise_for_status()
    except httpx.HTTPError:
        log.exception("Falha ao consultar CEP ou retornar dados ao Odoo: lead=%s", record_id)
        raise HTTPException(502, "Falha na consulta ou na atualização do Odoo")

    log.info("CEP processado e enviado ao Odoo: lead=%s", record_id)
    return {"status": "enviado_ao_odoo", "lead_id": record_id}
