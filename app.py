import os
from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.response import Response

# ==========================================
# CONFIGURAÇÕES DA SUA CONTA PIX (EDITE AQUI)
# ==========================================
CHAVE_PIX = "SUA_CHAVE_PIX_AQUI"          # Coloque seu e-mail, CPF, telefone ou chave aleatória
NOME_RECEBEDOR = "ZORVANYX SERVER"        # Máximo 25 letras sem acento
CIDADE_RECEBEDOR = "CACU"                 # Máximo 15 letras sem acento
DISCORD_LINK = "https://discord.gg"

def calcular_crc16(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def gerar_payload_pix(chave: str, nome: str, cidade: str, valor: float, txid: str = "ZORVANYX") -> str:
    def campo(id_campo: str, conteudo: str) -> str:
        return f"{id_campo}{len(conteudo):02d}{conteudo}"

    gui = campo("00", "br.gov.bcb.pix")
    chave_campo = campo("01", chave.strip())
    merchant_account = campo("26", gui + chave_campo)
    valor_str = f"{valor:.2f}"
    txid_limpo = "".join(c for c in txid if c.isalnum())[:25] or "ZORVANYX"
    adicional = campo("62", campo("05", txid_limpo))

    sem_crc = (
        campo("00", "01")
        + merchant_account
        + campo("52", "0000")
        + campo("53", "986")
        + campo("54", valor_str)
        + campo("58", "BR")
        + campo("59", nome[:25].upper())
        + campo("60", cidade[:15].upper())
        + adicional
        + "6304"
    )
    return sem_crc + calcular_crc16(sem_crc)

def pagina_loja(request):
    plano_inicial = request.matchdict.get("plano", "normal")
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    pix_normal = gerar_payload_pix(CHAVE_PIX, NOME_RECEBEDOR, CIDADE_RECEBEDOR, 8.00, "VIPNORMAL")
    pix_premium = gerar_payload_pix(CHAVE_PIX, NOME_RECEBEDOR, CIDADE_RECEBEDOR, 29.90, "VIPPREMIUM")

    html = html.replace("__PLANO_INICIAL__", plano_inicial)
    html = html.replace("__PIX_NORMAL__", pix_normal)
    html = html.replace("__PIX_PREMIUM__", pix_premium)
    html = html.replace("__DISCORD_LINK__", DISCORD_LINK)
    return Response(html, content_type="text/html", charset="utf-8")

if __name__ == "__main__":
    with Configurator() as config:
        config.add_route("home", "/")
        config.add_route("plano", "/vip-{plano}")
        config.add_view(pagina_loja, route_name="home")
        config.add_view(pagina_loja, route_name="plano")
        app = config.make_wsgi_app()

    porta = int(os.environ.get("PORT", 8080))
    print(f"Servidor Pylons/Pyramid ZORVANYX rodando na porta {porta}...")
    server = make_server("0.0.0.0", porta, app)
    server.serve_forever()
