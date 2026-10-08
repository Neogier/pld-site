"""Envia por e-mail a tabela do PLD do proximo dia, uma vez por dia.

Le o dados.json gerado pelo atualizar_dados.py. Quando o "amanha" esta
completo e ainda nao foi enviado (controle em notificacao.json), gera a
imagem da tabela e manda pelo Gmail.

Variaveis de ambiente (no GitHub ficam em Settings > Secrets):
  EMAIL_REMETENTE      conta Gmail que envia
  EMAIL_SENHA_APP      senha de app do Gmail (nao a senha normal)
  EMAIL_DESTINATARIOS  lista separada por virgula
  FORCAR_ENVIO         "true" envia mesmo que ja tenha enviado (teste)
  EMAIL_TESTE          "true" envia a tabela de HOJE com assunto [TESTE], sem
                       registrar o envio (para testar antes do PLD sair)

Uso local: python enviar_email.py --so-imagem  (so gera o PNG, nao envia)
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ARQUIVO_DADOS = Path("dados.json")
ARQUIVO_ESTADO = Path("notificacao.json")
# Imagem do proximo dia, publicada no site para o bot do WhatsApp baixar.
# O .json ao lado diz de que dia e a imagem.
ARQUIVO_IMAGEM = Path("pld-proximo-dia.png")
ARQUIVO_IMAGEM_INFO = Path("pld-proximo-dia.json")
ARQUIVO_IMAGEM_TESTE = Path("pld-teste.png")

URL_SITE = "https://neogier.github.io/pld-site/"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORTA = 465

SUBMERCADOS = ["NORDESTE", "SUDESTE", "SUL"]
REGISTROS_DIA_COMPLETO = 24 * len(SUBMERCADOS)

# Mesmas cores do site (style.css / script.js).
COR_MENOR = "#fff200"
COR_MAIOR = "#cfe8f6"
COR_CABECALHO = "#efefef"
COR_HORA = "#f8f8f8"
COR_BORDA = "#7c7c7c"
COR_TEXTO = "#111827"
COR_SUBTITULO = "#4b5563"


# =========================
# DESTAQUES (mesma regra do script.js)
# =========================
def obter_menores_por_coluna(linhas, coluna):
    valores = sorted(
        l[coluna] for l in linhas if l[coluna] is not None and l[coluna] < 150
    )

    if not valores:
        return set()

    valor_corte = valores[min(2, len(valores) - 1)]

    return {
        l["Hora"]
        for l in linhas
        if l[coluna] is not None and l[coluna] < 150 and l[coluna] <= valor_corte
    }


def obter_top3_por_coluna(linhas, coluna):
    distintos = sorted({l[coluna] for l in linhas if l[coluna] is not None}, reverse=True)
    top3 = set(distintos[:3])

    return {l["Hora"] for l in linhas if l[coluna] is not None and l[coluna] in top3}


def calcular_destaques(linhas):
    return {
        coluna: (obter_top3_por_coluna(linhas, coluna), obter_menores_por_coluna(linhas, coluna))
        for coluna in SUBMERCADOS
    }


def cor_da_celula(destaques, coluna, hora):
    maiores, menores = destaques[coluna]

    if hora in maiores:
        return COR_MAIOR
    if hora in menores:
        return COR_MENOR
    return None


def formatar_numero_br(valor):
    if valor is None:
        return ""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =========================
# IMAGEM
# =========================
def carregar_fonte(tamanho, negrito=False):
    candidatas = (
        ["arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if negrito
        else ["arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )

    for nome in candidatas:
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            continue

    return ImageFont.load_default(size=tamanho)


def gerar_imagem(bloco, destino: Path, rotulo="Próximo Dia"):
    linhas = bloco["linhas"]
    destaques = calcular_destaques(linhas)

    escala = 2
    margem = 20 * escala
    largura_tabela = 940 * escala
    largura_hora = 110 * escala
    largura_valor = (largura_tabela - largura_hora) // len(SUBMERCADOS)
    altura_linha = 46 * escala

    fonte_titulo = carregar_fonte(28 * escala, negrito=True)
    fonte_subtitulo = carregar_fonte(16 * escala)
    fonte_celula = carregar_fonte(22 * escala)
    fonte_negrito = carregar_fonte(22 * escala, negrito=True)

    altura_topo = 80 * escala
    largura = largura_tabela + 2 * margem
    altura = margem + altura_topo + altura_linha * (len(linhas) + 1) + margem

    imagem = Image.new("RGB", (largura, altura), "#ffffff")
    desenho = ImageDraw.Draw(imagem)

    desenho.text((margem, margem), f"PLD - {rotulo} ({bloco['data_br']})", font=fonte_titulo, fill=COR_TEXTO)
    desenho.text(
        (margem, margem + 44 * escala),
        # Sem horario de geracao: a mesma tabela gera sempre o mesmo arquivo, e o
        # workflow nao faz commit da imagem a cada execucao.
        "Fonte: CCEE - dadosabertos.ccee.org.br",
        font=fonte_subtitulo,
        fill=COR_SUBTITULO,
    )

    def celula(x, y, w, texto, fundo, fonte):
        desenho.rectangle([x, y, x + w, y + altura_linha], fill=fundo or "#ffffff", outline=COR_BORDA, width=escala)
        desenho.text((x + w / 2, y + altura_linha / 2), texto, font=fonte, fill=COR_TEXTO, anchor="mm")

    y = margem + altura_topo
    x = margem
    celula(x, y, largura_hora, "Hora", COR_CABECALHO, fonte_negrito)
    for i, submercado in enumerate(SUBMERCADOS):
        celula(x + largura_hora + i * largura_valor, y, largura_valor, submercado, COR_CABECALHO, fonte_negrito)

    for linha in linhas:
        y += altura_linha
        celula(x, y, largura_hora, str(linha["Hora"]), COR_HORA, fonte_negrito)
        for i, submercado in enumerate(SUBMERCADOS):
            celula(
                x + largura_hora + i * largura_valor,
                y,
                largura_valor,
                formatar_numero_br(linha[submercado]),
                cor_da_celula(destaques, submercado, linha["Hora"]),
                fonte_celula,
            )

    imagem.save(destino)
    return destino


# =========================
# E-MAIL
# =========================
def montar_html(bloco, rotulo="próximo dia"):
    linhas = bloco["linhas"]
    destaques = calcular_destaques(linhas)
    estilo_celula = f"border:1px solid {COR_BORDA};padding:4px 10px;text-align:center;"

    cabecalho = "".join(
        f'<th style="{estilo_celula}background:{COR_CABECALHO};">{s}</th>' for s in ["Hora"] + SUBMERCADOS
    )

    corpo = ""
    for linha in linhas:
        corpo += f'<tr><td style="{estilo_celula}background:{COR_HORA};font-weight:bold;">{linha["Hora"]}</td>'
        for submercado in SUBMERCADOS:
            fundo = cor_da_celula(destaques, submercado, linha["Hora"])
            estilo_fundo = f"background:{fundo};" if fundo else ""
            corpo += f'<td style="{estilo_celula}{estilo_fundo}">{formatar_numero_br(linha[submercado])}</td>'
        corpo += "</tr>"

    return f"""\
<div style="font-family:Arial,Helvetica,sans-serif;color:{COR_TEXTO};">
  <p>PLD horário de {rotulo} (<b>{bloco['data_br']}</b>) publicado pela CCEE.</p>
  <p>A imagem da tabela segue em anexo. Site: <a href="{URL_SITE}">{URL_SITE}</a></p>
  <table style="border-collapse:collapse;font-size:14px;">
    <thead><tr>{cabecalho}</tr></thead>
    <tbody>{corpo}</tbody>
  </table>
  <p style="color:{COR_SUBTITULO};font-size:12px;">
    Amarelo: menores valores abaixo de R$ 150. Azul: 3 maiores valores.<br>
    E-mail automático enviado pelo GitHub Actions.
  </p>
</div>"""


def enviar_email(bloco, imagem: Path, remetente, senha, destinatarios, rotulo="próximo dia", prefixo_assunto=""):
    mensagem = EmailMessage()
    mensagem["Subject"] = f"{prefixo_assunto}PLD {bloco['data_br']} publicado"
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(destinatarios)
    mensagem.set_content(
        f"PLD horário de {rotulo} ({bloco['data_br']}) publicado. "
        f"A tabela segue em anexo e está no site: {URL_SITE}"
    )
    mensagem.add_alternative(montar_html(bloco, rotulo), subtype="html")
    mensagem.add_attachment(
        imagem.read_bytes(),
        maintype="image",
        subtype="png",
        filename=f"PLD-{bloco['data_iso']}.png",
    )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORTA, timeout=60) as smtp:
        smtp.login(remetente, senha)
        smtp.send_message(mensagem)


# =========================
# CONTROLE DE ENVIO
# =========================
def carregar_estado():
    try:
        return json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar_estado(data_iso):
    estado = {
        "ultimo_envio_data": data_iso,
        "enviado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ARQUIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def ler_config_email():
    remetente = os.environ.get("EMAIL_REMETENTE", "").strip()
    senha = os.environ.get("EMAIL_SENHA_APP", "").strip()
    destinatarios = [e.strip() for e in os.environ.get("EMAIL_DESTINATARIOS", "").split(",") if e.strip()]

    if not (remetente and senha and destinatarios):
        print("Aviso: secrets de e-mail não configurados (EMAIL_REMETENTE, EMAIL_SENHA_APP, EMAIL_DESTINATARIOS). Nada enviado.")
        return None

    return remetente, senha, destinatarios


def publicar_imagem(amanha):
    imagem = gerar_imagem(amanha, ARQUIVO_IMAGEM)
    info = {"data_iso": amanha["data_iso"], "data_br": amanha["data_br"]}
    ARQUIVO_IMAGEM_INFO.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return imagem


def enviar_teste(hoje):
    config = ler_config_email()
    if config is None:
        sys.exit(1)

    remetente, senha, destinatarios = config
    imagem = gerar_imagem(hoje, ARQUIVO_IMAGEM_TESTE, rotulo="Hoje")
    enviar_email(hoje, imagem, remetente, senha, destinatarios, rotulo="hoje", prefixo_assunto="[TESTE] ")

    print(f"E-mail de TESTE ({hoje['data_br']}) enviado para {len(destinatarios)} destinatário(s).")


def main():
    so_imagem = "--so-imagem" in sys.argv
    forcar = os.environ.get("FORCAR_ENVIO", "").strip().lower() == "true"
    teste = os.environ.get("EMAIL_TESTE", "").strip().lower() == "true"

    dados = json.loads(ARQUIVO_DADOS.read_text(encoding="utf-8"))
    amanha = dados.get("amanha", {})

    if so_imagem:
        print(f"Imagem gerada: {gerar_imagem(amanha, ARQUIVO_IMAGEM).resolve()}")
        return

    if teste:
        enviar_teste(dados.get("hoje", {}))
        return

    if amanha.get("total_registros", 0) < REGISTROS_DIA_COMPLETO:
        print(f"Próximo dia ({amanha.get('data_br')}) ainda incompleto: {amanha.get('total_registros', 0)} registro(s).")
        return

    # Publica a imagem antes de tudo: o bot do WhatsApp depende dela mesmo que
    # o e-mail ja tenha saido ou nao esteja configurado.
    imagem = publicar_imagem(amanha)

    if carregar_estado().get("ultimo_envio_data") == amanha["data_iso"] and not forcar:
        print(f"E-mail de {amanha['data_br']} já foi enviado.")
        return

    config = ler_config_email()
    if config is None:
        return

    remetente, senha, destinatarios = config
    enviar_email(amanha, imagem, remetente, senha, destinatarios)
    salvar_estado(amanha["data_iso"])

    print(f"E-mail de {amanha['data_br']} enviado para {len(destinatarios)} destinatário(s).")


if __name__ == "__main__":
    main()
