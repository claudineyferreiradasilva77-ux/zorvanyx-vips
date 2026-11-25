import os
import hmac
import hashlib
import json
import requests
from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

# ==========================================
# CONFIGURAÇÃO MERCADO PAGO E CHAVE DE CÓDIGOS
# ==========================================
MP_ACCESS_TOKEN = "APP_USR-SEU_TOKEN_AQUI"
SITE_URL = "https://onrender.com"
CHAVE_ASSINATURA = "ZORVANYX_2026_KEY"

PAGAMENTOS_APROVADOS = {}

def gerar_codigo_vip(nick: str, plano: str, payment_id: str) -> str:
    prefixo = "P" if plano == "premium" else "N"
    base = f"{nick.lower()}:{plano}:{payment_id}:{CHAVE_ASSINATURA}".encode("utf-8")
    assinatura = hmac.new(CHAVE_ASSINATURA.encode("utf-8"), base, hashlib.sha256).hexdigest()[:6].upper()
    num = "".join(c for c in str(payment_id) if c.isdigit())[-4:].zfill(4)
    return f"ZVX-{prefixo}-{num}-{assinatura}"

def pagina_loja(request):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return Response(html, content_type="text/html", charset="utf-8")

def criar_pagamento(request):
    try:
        dados = request.json_body
        nick = str(dados.get("nick", "")).strip()
        launcher = str(dados.get("launcher", "original")).strip()
        plano = str(dados.get("plano", "normal")).lower()

        if not nick or len(nick) < 3:
            return Response(json.dumps({"erro": "Digite um nick válido do Minecraft!"}), status=400, content_type="application/json")

        if plano == "premium":
            titulo = f"VIP Premium 30 Dias ({nick})"
            preco = 29.90
        else:
            plano = "normal"
            titulo = f"VIP Normal 30 Dias ({nick})"
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
            "external_reference": f"{nick}|{plano}|{launcher}",
            "notification_url": f"{SITE_URL}/webhook",
            "back_urls": {
                "success": f"{SITE_URL}/?status=aprovado&nick={nick}&plano={plano}",
                "failure": f"{SITE_URL}/?status=erro",
                "pending": f"{SITE_URL}/?status=pendente&nick={nick}&plano={plano}"
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
                    partes = ref.split("|")
                    nick, plano = partes[0], partes[1]
                    codigo = gerar_codigo_vip(nick, plano, str(payment_id))
                    PAGAMENTOS_APROVADOS[f"{nick.lower()}:{plano}"] = codigo
    except Exception:
        pass
    return Response("OK", status=200)

def consultar_codigo(request):
    nick = str(request.params.get("nick", "")).strip().lower()
    plano = str(request.params.get("plano", "normal")).strip().lower()
    payment_id = str(request.params.get("payment_id", "")).strip()

    if payment_id and MP_ACCESS_TOKEN.startswith("APP_USR"):
        try:
            headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
            r = requests.get(f"https://mercadopago.com{payment_id}", headers=headers, timeout=10)
            pag = r.json()
            if pag.get("status") == "approved":
                ref = pag.get("external_reference", "")
                if "|" in ref:
                    p_nick, p_plano = ref.split("|")[:2]
                    cod = gerar_codigo_vip(p_nick, p_plano, payment_id)
                    PAGAMENTOS_APROVADOS[f"{p_nick.lower()}:{p_plano}"] = cod
        except Exception:
            pass

    cod_salvo = PAGAMENTOS_APROVADOS.get(f"{nick}:{plano}")
    if cod_salvo:
        return Response(json.dumps({"aprovado": True, "codigo": cod_salvo}), content_type="application/json")
    return Response(json.dumps({"aprovado": False}), content_type="application/json")

if __name__ == "__main__":
    with Configurator() as config:
        config.add_route("home", "/")
        config.add_route("plano", "/vip-{plano}")
        config.add_route("pagar", "/api/pagar")
        config.add_route("webhook", "/webhook")
        config.add_route("codigo", "/api/codigo")

        config.add_view(pagina_loja, route_name="home")
        config.add_view(pagina_loja, route_name="plano")
        config.add_view(criar_pagamento, route_name="pagar", request_method="POST")
        config.add_view(webhook_mp, route_name="webhook")
        config.add_view(consultar_codigo, route_name="codigo")
        app = config.make_wsgi_app()

    porta = int(os.environ.get("PORT", 8080))
    server = make_server("0.0.0.0", porta, app)
    server.serve_forever()
