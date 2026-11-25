import os
import random
import hmac
import hashlib
import json
import urllib.request
import urllib.error
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

def mp_request(url: str, data: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(err_body)
        except Exception:
            return {"message": err_body or str(e)}

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

        # MODO TESTE AUTOMÁTICO (ENQUANTO NÃO COLOCA O TOKEN REAL)
        if not MP_ACCESS_TOKEN or "SEU_TOKEN_AQUI" in MP_ACCESS_TOKEN:
            fake_id = str(random.randint(100000, 999999))
            url_teste = f"/checkout-teste?nick={nick}&plano={plano}&id={fake_id}"
            return Response(json.dumps({"checkout_url": url_teste}), content_type="application/json")

        # MODO PRODUÇÃO REAL (MERCADO PAGO)
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

        res_json = mp_request("https://mercadopago.com", payload)

        if "init_point" in res_json:
            return Response(json.dumps({"checkout_url": res_json["init_point"]}), content_type="application/json")
        else:
            detalhe = res_json.get("message", "Token do Mercado Pago inválido.")
            return Response(json.dumps({"erro": f"Mercado Pago: {detalhe}"}), status=400, content_type="application/json")
    except Exception as e:
        return Response(json.dumps({"erro": f"Erro interno: {str(e)}"}), status=500, content_type="application/json")

def pagina_checkout_teste(request):
    nick = str(request.params.get("nick", "Jogador")).strip()
    plano = str(request.params.get("plano", "normal")).strip().lower()
    pay_id = str(request.params.get("id", "123456")).strip()

    nome_plano = "VIP PREMIUM (30 DIAS)" if plano == "premium" else "VIP NORMAL (30 DIAS)"
    valor = "R$ 29,90" if plano == "premium" else "R$ 8,00"
    cor = "#facc15" if plano == "premium" else "#10b981"

    codigo = gerar_codigo_vip(nick, plano, pay_id)
    PAGAMENTOS_APROVADOS[f"{nick.lower()}:{plano}"] = codigo

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ZORVANYX • Checkout VIP</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    body {{
      background: #060b08; color: #f8fafc; min-height: 100vh;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    }}
    .box {{
      background: #0b1410; border: 1px solid {cor}; border-radius: 20px;
      max-width: 460px; width: 100%; padding: 28px; box-shadow: 0 0 40px rgba(16,185,129,0.18);
    }}
    .tag-teste {{
      background: rgba(250,204,21,0.15); border: 1px solid #facc15; color: #facc15;
      font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 6px; display: inline-block; margin-bottom: 12px;
    }}
    h2 {{ font-size: 1.5rem; color: {cor}; margin-bottom: 4px; }}
    .resumo {{ color: #94a3b8; font-size: 0.92rem; margin-bottom: 18px; }}
    .tabs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
    .tab {{
      padding: 10px; border-radius: 10px; border: 1px solid #1e293b; background: #050907;
      color: #cbd5e1; font-weight: 700; cursor: pointer; text-align: center;
    }}
    .tab.active {{ border-color: {cor}; color: {cor}; background: rgba(16,185,129,0.1); }}
    .card-form input {{
      width: 100%; padding: 11px; border-radius: 8px; border: 1px solid #1e293b;
      background: #040806; color: #fff; margin-bottom: 10px;
    }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .qr-area {{ text-align: center; padding: 14px; background: #050907; border-radius: 12px; border: 1px dashed #334155; }}
    .btn-pay {{
      width: 100%; padding: 14px; border: none; border-radius: 12px; margin-top: 16px;
      background: {cor}; color: #04100a; font-weight: 800; font-size: 1rem; cursor: pointer;
    }}
    .btn-voltar {{
      width: 100%; padding: 10px; border: 1px solid #334155; border-radius: 10px; margin-top: 10px;
      background: transparent; color: #94a3b8; cursor: pointer;
    }}
  </style>
</head>
<body>
  <div class="box">
    <div class="tag-teste">⚡ CHECKOUT DE TESTE DA GUI</div>
    <h2>{nome_plano} • {valor}</h2>
    <p class="resumo">Jogador: <strong>{nick}</strong> • Duração: 30 dias únicos</p>

    <div class="tabs">
      <div class="tab active" id="tPix" onclick="mudar('pix')">⚡ PIX INSTANTÂNEO</div>
      <div class="tab" id="tCard" onclick="mudar('card')">💳 CARTÃO DE CRÉDITO</div>
    </div>

    <div id="areaPix" class="qr-area">
      <img src="https://qrserver.com{pay_id}" alt="QR Teste" style="border-radius:10px; margin-bottom:10px;" />
      <p style="font-size:0.82rem; color:#94a3b8;">Escaneie o QR Code ou clique abaixo para simular a aprovação:</p>
    </div>

    <div id="areaCard" class="card-form" style="display:none;">
      <input type="text" placeholder="Número do Cartão (Ex: 4532 •••• •••• 1234)" />
      <input type="text" placeholder="Nome impresso no cartão" />
      <div class="row">
        <input type="text" placeholder="Validade (MM/AA)" />
        <input type="text" placeholder="CVV" />
      </div>
    </div>

    <button class="btn-pay" onclick="window.location.href='/?status=aprovado&nick={nick}&plano={plano}'">
      ✔ SIMULAR PAGAMENTO APROVADO
    </button>
    <button class="btn-voltar" onclick="window.location.href='/'">⬅ Voltar para a Loja</button>
  </div>
  <script>
    function mudar(m) {{
      document.getElementById('tPix').classList.toggle('active', m === 'pix');
      document.getElementById('tCard').classList.toggle('active', m === 'card');
      document.getElementById('areaPix').style.display = m === 'pix' ? 'block' : 'none';
      document.getElementById('areaCard').style.display = m === 'card' ? 'block' : 'none';
    }}
  </script>
</body>
</html>"""
    return Response(html, content_type="text/html", charset="utf-8")

def webhook_mp(request):
    try:
        payment_id = request.params.get("data.id") or request.params.get("id")
        if not payment_id and request.body:
            body = request.json_body
            payment_id = body.get("data", {}).get("id")

        if payment_id:
            pagamento = mp_request(f"https://mercadopago.com{payment_id}")
            if pagamento.get("status") == "approved":
                ref = pagamento.get("external_reference", "")
                if "|" in ref:
                    partes = ref.split("|")
                    nick = partes[0]
                    plano = partes[1]
                    codigo = gerar_codigo_vip(nick, plano, str(payment_id))
                    PAGAMENTOS_APROVADOS[f"{nick.lower()}:{plano}"] = codigo
    except Exception:
        pass
    return Response("OK", status=200)

def consultar_codigo(request):
    nick = str(request.params.get("nick", "")).strip().lower()
    plano = str(request.params.get("plano", "normal")).strip().lower()
    payment_id = str(request.params.get("payment_id", "")).strip()

    if payment_id and MP_ACCESS_TOKEN.startswith("APP_USR") and "SEU_TOKEN_AQUI" not in MP_ACCESS_TOKEN:
        try:
            pag = mp_request(f"https://mercadopago.com{payment_id}")
            if pag.get("status") == "approved":
                ref = pag.get("external_reference", "")
                if "|" in ref:
                    partes = ref.split("|")
                    p_nick = partes[0]
                    p_plano = partes[1]
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
        config.add_route("teste", "/checkout-teste")
        config.add_route("webhook", "/webhook")
        config.add_route("codigo", "/api/codigo")

        config.add_view(pagina_loja, route_name="home")
        config.add_view(pagina_loja, route_name="plano")
        config.add_view(criar_pagamento, route_name="pagar", request_method="POST")
        config.add_view(pagina_checkout_teste, route_name="teste")
        config.add_view(webhook_mp, route_name="webhook")
        config.add_view(consultar_codigo, route_name="codigo")
        app = config.make_wsgi_app()

    porta = int(os.environ.get("PORT", 8080))
    server = make_server("0.0.0.0", porta, app)
    server.serve_forever()
