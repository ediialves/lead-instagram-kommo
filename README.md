# Lead Instagram → Kommo

Webhook que recebe leads do Instagram e cria no Kommo CRM.

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export KOMMO_API_TOKEN="seu_token_aqui"
uvicorn main:app --reload
```

Testar:

```bash
curl -X POST http://localhost:8000/webhook/novo-lead \
  -H "Content-Type: application/json" \
  -d '{"name": "João Silva", "phone": "+5511999998888"}'
```

## Deploy no Railway

1. Crie um projeto no [Railway](https://railway.app) e conecte este repositório.
2. Adicione a variável de ambiente `KOMMO_API_TOKEN` nas settings do serviço.
3. O Railway detecta o `Procfile` automaticamente — sem configuração extra.

## Endpoint

**POST** `/webhook/novo-lead`

| Campo   | Tipo   | Exemplo            |
|---------|--------|--------------------|
| `name`  | string | `"João Silva"`     |
| `phone` | string | `"+5511999998888"` |

Telefone deve estar no formato `+55DDNNNNNNNNN`.
