import json
from datetime import datetime, timedelta
from pathlib import Path

import requests


RESOURCE_ID = "3f279d6b-1069-42f7-9b0a-217b084729c4"
BASE_URL = "https://dadosabertos.ccee.org.br/api/3/action/datastore_search"
SUBMERCADOS_DESEJADOS = ["NORDESTE", "SUDESTE", "SUL"]
LIMITE = 32000

ARQUIVO_SAIDA = Path("dados.json")


def formatar_data_br(data_obj: datetime) -> str:
    return data_obj.strftime("%d/%m/%Y")


def formatar_data_iso(data_obj: datetime) -> str:
    return data_obj.strftime("%Y-%m-%d")


def obter_hoje() -> datetime:
    agora = datetime.now()
    return datetime(agora.year, agora.month, agora.day)


def obter_amanha() -> datetime:
    return obter_hoje() + timedelta(days=1)


def padronizar_submercado(valor: str) -> str:
    texto = str(valor or "").strip().upper()

    if "SUDESTE" in texto:
        return "SUDESTE"
    if "SUL" in texto:
        return "SUL"
    if "NORDESTE" in texto:
        return "NORDESTE"
    if "NORTE" in texto:
        return "NORTE"

    return texto


def normalizar_numero(valor):
    if valor is None or valor == "":
        return None

    try:
        return float(valor)
    except (ValueError, TypeError):
        return None


def buscar_lote_recente():
    params = {
        "resource_id": RESOURCE_ID,
        "limit": LIMITE
    }

    with requests.Session() as sessao:
        sessao.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Referer": "https://dadosabertos.ccee.org.br/",
            "Origin": "https://dadosabertos.ccee.org.br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })

        response = sessao.get(BASE_URL, params=params, timeout=60)

        print("URL final:", response.url)
        print("Status HTTP:", response.status_code)
        print("Headers resposta:", dict(response.headers))

        if response.status_code != 200:
            print("Corpo do erro:")
            print(response.text[:5000])

        response.raise_for_status()

        payload = response.json()

    if not payload.get("success"):
        raise RuntimeError("A API da CCEE retornou success=false.")

    registros = payload.get("result", {}).get("records", [])

    return [
        item
        for item in registros
        if padronizar_submercado(item.get("SUBMERCADO")) in SUBMERCADOS_DESEJADOS
    ]


def montar_data_registro(item):
    mes_referencia = str(item.get("MES_REFERENCIA", "")).strip()
    dia = str(item.get("DIA", "")).strip().zfill(2)

    if len(mes_referencia) != 6 or not mes_referencia.isdigit():
        return None

    if len(dia) == 0 or not dia.isdigit():
        return None

    ano = int(mes_referencia[:4])
    mes = int(mes_referencia[4:6])
    dia_num = int(dia)

    try:
        return datetime(ano, mes, dia_num)
    except ValueError:
        return None


def enriquecer_registros(registros):
    enriquecidos = []

    for item in registros:
        data_obj = montar_data_registro(item)
        if data_obj is None:
            continue

        enriquecidos.append(
            {
                **item,
                "DATA_ISO": formatar_data_iso(data_obj),
                "DATA_BR": formatar_data_br(data_obj),
                "SUBMERCADO_PADRAO": padronizar_submercado(item.get("SUBMERCADO")),
                "PLD_HORA_NUM": normalizar_numero(item.get("PLD_HORA")),
            }
        )

    return enriquecidos


def filtrar_por_data_iso(registros, data_iso: str):
    return [item for item in registros if item.get("DATA_ISO") == data_iso]


def montar_matriz_horaria(registros):
    matriz = {
        hora: {
            "Hora": hora,
            "NORDESTE": None,
            "SUDESTE": None,
            "SUL": None,
        }
        for hora in range(24)
    }

    for item in registros:
        try:
            hora = int(item.get("HORA"))
        except (ValueError, TypeError):
            continue

        if hora < 0 or hora > 23:
            continue

        submercado = item.get("SUBMERCADO_PADRAO")
        valor = item.get("PLD_HORA_NUM")

        if submercado not in SUBMERCADOS_DESEJADOS:
            continue

        if valor is None:
            continue

        matriz[hora][submercado] = valor

    return [matriz[hora] for hora in sorted(matriz.keys())]


def gerar_saida():
    hoje = obter_hoje()
    amanha = obter_amanha()

    hoje_iso = formatar_data_iso(hoje)
    amanha_iso = formatar_data_iso(amanha)

    hoje_br = formatar_data_br(hoje)
    amanha_br = formatar_data_br(amanha)

    registros_brutos = buscar_lote_recente()
    registros = enriquecer_registros(registros_brutos)

    registros_hoje = filtrar_por_data_iso(registros, hoje_iso)
    registros_amanha = filtrar_por_data_iso(registros, amanha_iso)

    linhas_hoje = montar_matriz_horaria(registros_hoje)
    linhas_amanha = montar_matriz_horaria(registros_amanha)

    saida = {
        "atualizado_em": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fonte": {
            "base_url": BASE_URL,
            "resource_id": RESOURCE_ID,
            "limite": LIMITE,
        },
        "hoje": {
            "data_iso": hoje_iso,
            "data_br": hoje_br,
            "total_registros": len(registros_hoje),
            "linhas": linhas_hoje,
        },
        "amanha": {
            "data_iso": amanha_iso,
            "data_br": amanha_br,
            "total_registros": len(registros_amanha),
            "linhas": linhas_amanha,
        },
    }

    ARQUIVO_SAIDA.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Arquivo gerado com sucesso: {ARQUIVO_SAIDA.resolve()}")
    print(f"Hoje ({hoje_br}): {len(registros_hoje)} registro(s)")
    print(f"Amanhã ({amanha_br}): {len(registros_amanha)} registro(s)")


if __name__ == "__main__":
    gerar_saida()