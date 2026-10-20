"""Confere o PLD de um dia contra os limites da ANEEL (limites_pld.json).

Fora do mínimo ou do máximo horário, ou com hora faltando, o valor não pode ser
real (ex.: 18/10/2026 publicado com 1, 2 e 3). O enviar_email.py não manda o
e-mail nesse caso e espera a correção.

Os limites mudam todo ano (despacho da ANEEL de dezembro): acrescente o ano novo
em limites_pld.json. Sem ele, vale o último ano cadastrado, com um aviso.
"""

import json
from pathlib import Path

ARQUIVO_LIMITES = Path(__file__).with_name("limites_pld.json")
SUBMERCADOS = ["NORDESTE", "SUDESTE", "SUL"]
TOLERANCIA = 0.01  # arredondamento (o piso vem como 57,31 exato)


def reais(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def limites_do_ano(ano):
    limites = json.loads(ARQUIVO_LIMITES.read_text(encoding="utf-8"))
    if str(ano) in limites:
        return limites[str(ano)]
    anos = sorted(int(a) for a in limites)
    anterior = max((a for a in anos if a <= ano), default=anos[0])
    print(f"Aviso: sem limites do PLD de {ano} em limites_pld.json; usando os de {anterior}.")
    return limites[str(anterior)]


def problemas_do_dia(bloco):
    """Lista de problemas do dia (vazia = tudo dentro dos limites)."""
    limites = limites_do_ano(int(bloco["data_iso"][:4]))
    valores = [linha.get(s) for linha in bloco.get("linhas", []) for s in SUBMERCADOS]
    numeros = [v for v in valores if isinstance(v, (int, float))]
    abaixo = [v for v in numeros if v < limites["minimo"] - TOLERANCIA]
    acima = [v for v in numeros if v > limites["maximo_horario"] + TOLERANCIA]
    faltando = len(valores) - len(numeros)

    problemas = []
    if abaixo:
        problemas.append(f"valores abaixo do mínimo da ANEEL ({reais(min(abaixo))}; mínimo {reais(limites['minimo'])})")
    if acima:
        problemas.append(f"valores acima do máximo da ANEEL ({reais(max(acima))}; máximo "
                         f"{reais(limites['maximo_horario'])})")
    if faltando:
        problemas.append(f"{faltando} valor(es) faltando")
    return problemas
