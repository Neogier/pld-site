const URL_DADOS = "./dados.json";
const SUBMERCADOS_DESEJADOS = ["NORDESTE", "SUDESTE", "SUL"];

const statusEl = document.getElementById("status");
const infoHojeEl = document.getElementById("infoHoje");
const infoAmanhaEl = document.getElementById("infoAmanha");
const debugEl = document.getElementById("debug");
const tbodyHojeEl = document.getElementById("tbody-hoje");
const tbodyAmanhaEl = document.getElementById("tbody-amanha");
const btnAtualizar = document.getElementById("btnAtualizar");
const btnBaixarHoje = document.getElementById("btnBaixarHoje");
const btnBaixarAmanha = document.getElementById("btnBaixarAmanha");
const cardHoje = document.getElementById("card-hoje");
const cardAmanha = document.getElementById("card-amanha");

btnAtualizar.addEventListener("click", carregarDados);
btnBaixarHoje.addEventListener("click", () => baixarTabelaComoImagem(cardHoje, "tabela-hoje"));
btnBaixarAmanha.addEventListener("click", () => baixarTabelaComoImagem(cardAmanha, "tabela-proximo-dia"));
document.addEventListener("DOMContentLoaded", carregarDados);

function setStatus(texto, classe = "") {
  statusEl.textContent = texto;
  statusEl.className = classe;
}

function limparTabela(tbody) {
  tbody.innerHTML = "";
}

function limparTudo() {
  limparTabela(tbodyHojeEl);
  limparTabela(tbodyAmanhaEl);
  infoHojeEl.textContent = "";
  infoAmanhaEl.textContent = "";
  debugEl.textContent = "";
}

function formatarNumeroBR(valor) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return "";
  }

  return Number(valor).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function obterMenoresPorColuna(linhas, coluna) {
  const valoresMenoresQue150 = linhas
    .map((l) => l[coluna])
    .filter((v) => v !== null && v < 150)
    .sort((a, b) => a - b);

  if (valoresMenoresQue150.length === 0) {
    return new Set();
  }

  const indiceCorte = Math.min(2, valoresMenoresQue150.length - 1);
  const valorCorte = valoresMenoresQue150[indiceCorte];

  return new Set(
    linhas
      .filter(
        (l) =>
          l[coluna] !== null &&
          l[coluna] < 150 &&
          l[coluna] <= valorCorte
      )
      .map((l) => l.Hora)
  );
}

function obterTop3PorColuna(linhas, coluna) {
  const valores = linhas
    .map((l) => l[coluna])
    .filter((v) => v !== null)
    .sort((a, b) => b - a);

  const top3 = [...new Set(valores)].slice(0, 3);

  return new Set(
    linhas
      .filter((l) => l[coluna] !== null && top3.includes(l[coluna]))
      .map((l) => l.Hora)
  );
}

function renderizarTabela(linhas, tbody) {
  limparTabela(tbody);

  const destaque = {
    NORDESTE: {
      menores: obterMenoresPorColuna(linhas, "NORDESTE"),
      maiores: obterTop3PorColuna(linhas, "NORDESTE")
    },
    SUDESTE: {
      menores: obterMenoresPorColuna(linhas, "SUDESTE"),
      maiores: obterTop3PorColuna(linhas, "SUDESTE")
    },
    SUL: {
      menores: obterMenoresPorColuna(linhas, "SUL"),
      maiores: obterTop3PorColuna(linhas, "SUL")
    }
  };

  for (const linha of linhas) {
    const tr = document.createElement("tr");

    const tdHora = document.createElement("td");
    tdHora.textContent = linha.Hora;
    tdHora.className = "hora";
    tr.appendChild(tdHora);

    for (const coluna of SUBMERCADOS_DESEJADOS) {
      const td = document.createElement("td");
      td.textContent = linha[coluna] === null ? "" : formatarNumeroBR(linha[coluna]);

      if (destaque[coluna].maiores.has(linha.Hora)) {
        td.classList.add("maior");
      } else if (destaque[coluna].menores.has(linha.Hora)) {
        td.classList.add("menor");
      }

      tr.appendChild(td);
    }

    tbody.appendChild(tr);
  }
}

async function baixarTabelaComoImagem(elemento, nomeArquivo) {
  try {
    const canvas = await html2canvas(elemento, {
      backgroundColor: "#ffffff",
      scale: 2,
      useCORS: true
    });

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = `${nomeArquivo}.png`;
    link.click();
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível gerar a imagem da tabela.");
  }
}

async function carregarDados() {
  setStatus("Carregando dados...", "");
  limparTudo();

  try {
    const resposta = await fetch(`${URL_DADOS}?v=${Date.now()}`, {
      cache: "no-store"
    });

    debugEl.textContent += `URL dados:\n${URL_DADOS}\n\n`;
    debugEl.textContent += `HTTP Status: ${resposta.status}\n`;
    debugEl.textContent += `Content-Type: ${resposta.headers.get("content-type") || "não informado"}\n\n`;

    if (!resposta.ok) {
      const textoErro = await resposta.text();
      debugEl.textContent += `Corpo do erro:\n${textoErro}\n\n`;
      throw new Error(`Falha HTTP: ${resposta.status}`);
    }

    const json = await resposta.json();

    debugEl.textContent += JSON.stringify(json, null, 2).slice(0, 4000);

    const hoje = json.hoje || {};
    const amanha = json.amanha || {};

    const linhasHoje = Array.isArray(hoje.linhas) ? hoje.linhas : [];
    const linhasAmanha = Array.isArray(amanha.linhas) ? amanha.linhas : [];

    renderizarTabela(linhasHoje, tbodyHojeEl);
    renderizarTabela(linhasAmanha, tbodyAmanhaEl);

    infoHojeEl.textContent =
      `Hoje: ${hoje.data_br || "-"} | Registros encontrados: ${hoje.total_registros ?? 0}`;

    infoAmanhaEl.textContent =
      `Próximo dia: ${amanha.data_br || "-"} | Registros encontrados: ${amanha.total_registros ?? 0}`;

    if ((hoje.total_registros ?? 0) === 0 && (amanha.total_registros ?? 0) === 0) {
      setStatus("Nenhum registro encontrado para hoje e próximo dia.", "vazio");
      return;
    }

    if ((hoje.total_registros ?? 0) > 0 && (amanha.total_registros ?? 0) === 0) {
      setStatus("Hoje carregado com sucesso. Próximo dia ainda sem registros.", "ok");
      return;
    }

    if ((hoje.total_registros ?? 0) === 0 && (amanha.total_registros ?? 0) > 0) {
      setStatus("Próximo dia carregado com sucesso. Hoje sem registros.", "ok");
      return;
    }

    setStatus("Hoje e próximo dia carregados com sucesso.", "ok");
  } catch (erro) {
    console.error(erro);
    setStatus(`Erro ao carregar: ${erro.message}`, "erro");

    if (!debugEl.textContent) {
      debugEl.textContent = String(erro?.stack || erro?.message || erro);
    }
  }
}