import os
import random
import hmac
import hashlib
import json
import urllib.request
from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response
from pyramid.httpexceptions import HTTPFound

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
        return Response(f.read(), content_type="text/html", charset="utf-8")

def pagina_checkout(request):
    nick = str(request.params.get("nick", "Jogador")).strip()
    plano = str(request.params.get("plano", "normal")).strip().lower()
    launcher = str(request.params.get("launcher", "original")).strip()

    if plano == "premium":
        nome_plano, valor, preco, cor = "VIP PREMIUM (30 DIAS)", "R$ 29,90", 29.90, "#facc15"
    else:
        plano = "normal"
        nome_plano, valor, preco, cor = "VIP NORMAL (30 DIAS)", "R$ 8,00", 8.00, "#10b981"

    # SE TIVER TOKEN REAL DO MERCADO PAGO, REDIRECIONA PARA O PAGAMENTO REAL
    if MP_ACCESS_TOKEN.startswith("APP_USR") and "SEU_TOKEN_AQUI" not in MP_ACCESS_TOKEN:
        payload = {
            "items": [{"title": f"{nome_plano} - {nick}", "quantity": 1, "currency_id": "BRL", "unit_price": preco}],
            "external_reference": f"{nick}|{plano}|{launcher}",
            "notification_url": f"{SITE_URL}/webhook",
            "back_urls": {
                "success": f"{SITE_URL}/?status=aprovado&nick={nick}&plano={plano}",
                "failure": f"{SITE_URL}/?status=erro",
                "pending": f"{SITE_URL}/?status=pendente&nick={nick}&plano={plano}"
            },
            "auto_return": "approved"
        }
        req = urllib.request.Request(
            "https://mercadopago.com",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if "init_point" in res:
                return HTTPFound(location=res["init_point"])

    # MODO TESTE DA GUI (EXIBE PIX E CARTÃO NA TELA)
    pay_id = str(random.randint(100000, 999999))
    codigo = gerar_codigo_vip(nick, plano, pay_id)
    PAGAMENTOS_APROVADOS[f"{nick.lower()}:{plano}"] = codigo

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ZORVANYX • Checkout VIP</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    body {{ background: #060b08; color: #f8fafc; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
    .box {{ background: #0b1410; border: 1px solid {cor}; border-radius: 20px; max-width: 460px; width: 100%; padding: 28px; box-shadow: 0 0 40px rgba(16,185,129,0.18); }}
    .tag {{ background: rgba(250,204,21,0.15); border: 1px solid #facc15; color: #facc15; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }}
    h2 {{ font-size: 1.5rem; color: {cor}; margin-bottom: 4px; }}
    .resumo {{ color: #94a3b8; font-size: 0.92rem; margin-bottom: 18px; }}
    .tabs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
    .tab {{ padding: 10px; border-radius: 10px; border: 1px solid #1e293b; background: #050907; color: #cbd5e1; font-weight: 700; cursor: pointer; text-align: center; }}
    .tab.active {{ border-color: {cor}; color: {cor}; background: rgba(16,185,129,0.1); }}
    .card-form input {{ width: 100%; padding: 11px; border-radius: 8px; border: 1px solid #1e293b; background: #040806; color: #fff; margin-bottom: 10px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .qr-area {{ text-align: center; padding: 14px; background: #050907; border-radius: 12px; border: 1px dashed #334155; }}
    .btn-pay {{ width: 100%; padding: 14px; border: none; border-radius: 12px; margin-top: 16px; background: {cor}; color: #04100a; font-weight: 800; font-size: 1rem; cursor: pointer; }}
    .btn-voltar {{ width: 100%; padding: 10px; border: 1px solid #334155; border-radius: 10px; margin-top: 10px; background: transparent; color: #94a3b8; cursor: pointer; }}
  </style>
</head>
<body>
  <div class="box">
    <div class="tag">⚡ CHECKOUT OFICIAL • ZORVANYX</div>
    <h2>{nome_plano} • {valor}</h2>
    <p class="resumo">Jogador: <strong>{nick}</strong> ({launcher.upper()}) • 30 dias únicos</p>
    <div class="tabs">
      <div class="tab active" id="tPix" onclick="mudar('pix')">⚡ PIX INSTANTÂNEO</div>
      <div class="tab" id="tCard" onclick="mudar('card')">💳 CARTÃO DE CRÉDITO</div>
    </div>
    <div id="areaPix" class="qr-area">
      <img src="https://qrserver.com{pay_id}" alt="QR Code" style="border-radius:10px; margin-bottom:10px;" />
      <p style="font-size:0.82rem; color:#94a3b8;">Escaneie o QR Code ou clique no botão abaixo para simular a aprovação:</p>
    </div>
    <div id="areaCard" class="card-form" style="display:none;">
      <input type="text" placeholder="Número do Cartão (Ex: 4532 •••• •••• 1234)" />
      <input type="text" placeholder="Nome impresso no cartão" />
      <div class="row"><input type="text" placeholder="Validade (MM/AA)" /><input type="text" placeholder="CVV" /></div>
    </div>
    <button class="btn-pay" onclick="window.location.href='/?status=aprovado&nick={nick}&plano={plano}'">✔ CONFIRMAR PAGAMENTO</button>
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

def consultar_codigo(request):
    nick = str(request.params.get("nick", "")).strip().lower()
    plano = str(request.params.get("plano", "normal")).strip().lower()
    cod_salvo = PAGAMENTOS_APROVADOS.get(f"{nick}:{plano}")
    if not cod_salvo:
        cod_salvo = gerar_codigo_vip(nick, plano, "9999")
    return Response(json.dumps({"aprovado": True, "codigo": cod_salvo}), content_type="application/json")

if __name__ == "__main__":
    with Configurator() as config:
        config.add_route("home", "/")
        config.add_route("checkout", "/checkout")
        config.add_route("codigo", "/api/codigo")
        config.add_view(pagina_loja, route_name="home")
        config.add_view(pagina_checkout, route_name="checkout")
        config.add_view(consultar_codigo, route_name="codigo")
        app = config.make_wsgi_app()

    porta = int(os.environ.get("PORT", 8080))
    make_server("0.0.0.0", porta, app).serve_forever()
