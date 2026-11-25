import os
import json
import requests
from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

# ==========================================
# CONFIGURAÇÃO MERCADO PAGO (COLE SEU TOKEN REAL AQUI)
# ==========================================
MP_ACCESS_TOKEN = "APP_USR-SEU_TOKEN_AQUI"
SITE_URL = "https://onrender.com"
SEGREDO_API = "ZORVANYX_SECRET_2026"

ENTREGAS_PENDENTES = []

def pagina_loja(request):
    plano_inicial = request.matchdict.get("plano", "normal")
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__PLANO_INICIAL__", plano_inicial)
    return Response(html, content_type="text/html", charset="utf-8")

def criar_pagamento(request):
    try:
        dados = request.json_body
        nick = str(dados.get("nick", "")).strip()
        plano = str(dados.get("plano", "normal")).lower()

        if not nick or len(nick) < 3:
            return Response(json.dumps({"erro": "Digite um nick válido do Minecraft!"}), status=400, content_type="application/json")

        if plano == "premium":
            titulo = "VIP Premium (30 Dias) - ZORVANYX"
            preco = 29.90
        else:
            plano = "normal"
            titulo = "VIP Normal (30 Dias) - ZORVANYX"
            preco = 8.00

        payload = {
            "items": [
                {
                    "title": titulo,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": preco
                }
            ],
            "external_reference": f"{nick}|{plano}",
            "notification_url": f"{SITE_URL}/webhook",
            "back_urls": {
                "success": f"{SITE_URL}/?status=aprovado",
                "failure": f"{SITE_URL}/?status=erro",
                "pending": f"{SITE_URL}/?status=pendente"
            },
            "auto_return": "approved"
        }

        headers = {
            "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        resp = requests.post("https://mercadopago.com", json=payload, headers=headers, timeout=15)
        res_json = resp.json()

        if "init_point" in res_json:
            return Response(json.dumps({"checkout_url": res_json["init_point"]}), content_type="application/json")
        else:
            return Response(json.dumps({"erro": "Configure seu Access Token do Mercado Pago no app.py!"}), status=400, content_type="application/json")
    except Exception as e:
        return Response(json.dumps({"erro": str(e)}), status=500, content_type="application/json")

def webhook_mp(request):
    try:
        payment_id = request.params.get("data.id") or request.params.get("id")
        if not payment_id and request.body:
            body = request.json_body
            payment_id = body.get("data", {}).get("id")

        if payment_id:
            headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
            r = requests.get(f"https://mercadopago.com{payment_id}", headers=headers, timeout=10)
            pagamento = r.json()
            if pagamento.get("status") == "approved":
                ref = pagamento.get("external_reference", "")
                if "|" in ref:
                    nick, plano = ref.split("|", 1)
                    entrega = f"{nick}:{plano}"
                    if entrega not in ENTREGAS_PENDENTES:
                        ENTREGAS_PENDENTES.append(entrega)
    except Exception:
        pass
    return Response("OK", status=200)

def consultar_entregas(request):
    chave = request.params.get("key", "")
    if chave != SEGREDO_API:
        return Response("FORBIDDEN", status=403)
    if not ENTREGAS_PENDENTES:
        return Response("VAZIO", content_type="text/plain")
    lista = ";".join(ENTREGAS_PENDENTES)
    ENTREGAS_PENDENTES.clear()
    return Response(lista, content_type="text/plain")

if __name__ == "__main__":
    with Configurator() as config:
        config.add_route("home", "/")
        config.add_route("plano", "/vip-{plano}")
        config.add_route("pagar", "/api/pagar")
        config.add_route("webhook", "/webhook")
        config.add_route("entregas", "/api/entregas")

        config.add_view(pagina_loja, route_name="home")
        config.add_view(pagina_loja, route_name="plano")
        config.add_view(criar_pagamento, route_name="pagar", request_method="POST")
        config.add_view(webhook_mp, route_name="webhook")
        config.add_view(consultar_entregas, route_name="entregas")
        app = config.make_wsgi_app()

    porta = int(os.environ.get("PORT", 8080))
    server = make_server("0.0.0.0", porta, app)
    server.serve_forever()
