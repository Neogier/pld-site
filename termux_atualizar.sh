#!/data/data/com.termux/files/usr/bin/bash
# Atualizacao manual pelo Termux (plano B, se o GitHub Actions nao atualizar).
#
# Uso: bash ~/pld-site/termux_atualizar.sh   (ou pelo atalho do Termux:Widget)
#
# Sempre sincroniza com o GitHub antes de rodar, entao este script e o
# atualizar_dados.py ficam atualizados sozinhos. O clone do celular serve so
# para isso: alteracoes locais nao commitadas sao descartadas.

# As chaves fazem o bash ler o script inteiro antes de executar; assim o
# "git reset" abaixo pode atualizar este proprio arquivo sem problema.
{
set -u
cd "$(dirname "$0")" || exit 1

echo "== Sincronizando com o GitHub..."
git fetch origin || { echo "Sem conexao com o GitHub."; exit 1; }
git reset --hard origin/main

echo "== Consultando a CCEE..."
if ! python atualizar_dados.py; then
    echo "Falha ao consultar a CCEE."
    exit 1
fi

git add dados.json
if git diff --cached --quiet; then
    echo "== Site ja estava atualizado (o robo do GitHub ja publicou)."
else
    git commit -m "Atualizacao manual por Sergio"
    # Se o robo publicou no meio do caminho, junta e tenta de novo.
    git push || { git pull --rebase -X theirs origin main && git push; } || {
        echo "Falha no push."
        exit 1
    }
    echo "== Publicado. O site atualiza em 1-2 minutos."
fi

termux-open-url "https://neogier.github.io/pld-site/"
exit 0
}
