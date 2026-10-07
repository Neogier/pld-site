import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from curl_cffi import requests


API_URL = "https://dadosabertos.ccee.org.br/api/3/action/"
BASE_URL = API_URL + "datastore_search"

# A CCEE publica um recurso por ano dentro do pacote "pld_horario"
# (pld_horario_2025, pld_horario_2026, ...). O ID e descoberto em tempo de
# execucao; esta tabela so e usada se a consulta ao pacote falhar.
PACOTE_PLD = "pld_horario"
RESOURCE_IDS_CONHECIDOS = {
    2025: "2a180a6b-f092-43eb-9f82-a48798b803dc",
    2026: "3f279d6b-1069-42f7-9b0a-217b084729c4",
}

SUBMERCADOS_DESEJADOS = ["NORDESTE", "SUDESTE", "SUL"]
LIMITE = 500  # um dia tem 96 registros (24 horas x 4 submercados)

ARQUIVO_SAIDA = Path("dados.json")

# O GitHub Actions roda em UTC; as datas precisam ser as de Brasilia.
try:
    from zoneinfo import ZoneInfo

    FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")
except Exception:
    # Windows sem o pacote tzdata. Brasil nao tem horario de verao desde 2019.
    FUSO_BRASILIA = timezone(timedelta(hours=-3))


def formatar_data_br(data_obj: datetime) -> str:
    return data_obj.strftime("%d/%m/%Y")


def formatar_data_iso(data_obj: datetime) -> str:
    return data_obj.strftime("%Y-%m-%d")


def obter_hoje() -> datetime:
    agora = datetime.now(FUSO_BRASILIA)
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


def criar_sessao():
    sessao = requests.Session()
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
    return sessao


def consultar_api(sessao, acao: str, params: dict) -> dict:
    # impersonate="chrome" faz a conexao parecer um navegador; sem isso o WAF
    # da CCEE devolve a pagina "Acesso bloqueado".
    response = sessao.get(API_URL + acao, params=params, timeout=60, impersonate="chrome")

    print(f"{acao}: HTTP {response.status_code}")

    if response.status_code != 200:
        print("Corpo do erro:")
        print(response.text[:5000])

    response.raise_for_status()

    payload = response.json()

    if not payload.get("success"):
        raise RuntimeError(f"A API da CCEE retornou success=false em {acao}: {payload.get('error')}")

    return payload.get("result", {})


def buscar_resource_ids(sessao) -> dict:
    try:
        pacote = consultar_api(sessao, "package_show", {"id": PACOTE_PLD})
    except Exception as erro:
        print(f"Aviso: nao foi possivel listar os recursos do pacote ({erro}). Usando IDs conhecidos.")
        return dict(RESOURCE_IDS_CONHECIDOS)

    ids = dict(RESOURCE_IDS_CONHECIDOS)
    for recurso in pacote.get("resources", []):
        achado = re.fullmatch(r"pld_horario_(\d{4})", str(recurso.get("name", "")).strip())
        if achado:
            ids[int(achado.group(1))] = recurso["id"]

    return ids


def buscar_registros_do_dia(sessao, resource_id, data_obj: datetime):
    if resource_id is None:
        print(f"Aviso: nenhum recurso da CCEE para o ano {data_obj.year} ainda.")
        return []

    filtros = {
        "MES_REFERENCIA": data_obj.strftime("%Y%m"),
        # A CCEE grava o dia sem zero a esquerda ("7"); "07" fica por seguranca.
        "DIA": [str(data_obj.day), data_obj.strftime("%d")],
    }

    resultado = consultar_api(sessao, "datastore_search", {
        "resource_id": resource_id,
        "filters": json.dumps(filtros),
        "limit": LIMITE,
    })

    return [
        item
        for item in resultado.get("records", [])
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


def gerar_bloco_do_dia(sessao, resource_ids: dict, data_obj: datetime) -> dict:
    data_iso = formatar_data_iso(data_obj)
    resource_id = resource_ids.get(data_obj.year)

    registros = enriquecer_registros(buscar_registros_do_dia(sessao, resource_id, data_obj))
    registros = filtrar_por_data_iso(registros, data_iso)

    return {
        "data_iso": data_iso,
        "data_br": formatar_data_br(data_obj),
        "resource_id": resource_id,
        "total_registros": len(registros),
        "linhas": montar_matriz_horaria(registros),
    }


def gerar_saida():
    hoje = obter_hoje()
    amanha = obter_amanha()

    with criar_sessao() as sessao:
        resource_ids = buscar_resource_ids(sessao)
        bloco_hoje = gerar_bloco_do_dia(sessao, resource_ids, hoje)
        bloco_amanha = gerar_bloco_do_dia(sessao, resource_ids, amanha)

    saida = {
        "atualizado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fonte": {
            "base_url": BASE_URL,
            "resource_id": bloco_hoje["resource_id"],
            "limite": LIMITE,
        },
        "hoje": bloco_hoje,
        "amanha": bloco_amanha,
    }

    print(f"Hoje ({bloco_hoje['data_br']}): {bloco_hoje['total_registros']} registro(s)")
    print(f"Amanha ({bloco_amanha['data_br']}): {bloco_amanha['total_registros']} registro(s)")

    # So regrava quando os dados mudam; assim o workflow nao gera um commit
    # (e um deploy do site) a cada execucao so por causa do atualizado_em.
    if dados_iguais_ao_arquivo_atual(saida):
        print("Dados iguais aos do dados.json atual. Nada a gravar.")
        return

    ARQUIVO_SAIDA.write_text(
        json.dumps(saida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Arquivo gerado com sucesso: {ARQUIVO_SAIDA.resolve()}")


def dados_iguais_ao_arquivo_atual(saida: dict) -> bool:
    try:
        atual = json.loads(ARQUIVO_SAIDA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False

    return all(atual.get(chave) == saida[chave] for chave in ("hoje", "amanha"))


if __name__ == "__main__":
    gerar_saida()
