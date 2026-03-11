const RESOURCE_ID = "3f279d6b-1069-42f7-9b0a-217b084729c4";
const BASE_URL = "https://dadosabertos.ccee.org.br/api/3/action/datastore_search";

const SUBMERCADOS_DESEJADOS = ["NORDESTE", "SUDESTE", "SUL"];

const statusEl = document.getElementById("status");
const infoHojeEl = document.getElementById("infoHoje");
const infoAmanhaEl = document.getElementById("infoAmanha");
const debugEl = document.getElementById("debug");
const tbodyHojeEl = document.getElementById("tbody-hoje");
const tbodyAmanhaEl = document.getElementById("tbody-amanha");
const btnAtualizar = document.getElementById("btnAtualizar");

btnAtualizar.addEventListener("click", carregarDados);
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

function formatarDataISO(data) {
  const ano = data.getFullYear();
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

function formatarDataBR(data) {
  const dia = String(data.getDate()).padStart(2, "0");
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const ano = data.getFullYear();
  return `${dia}/${mes}/${ano}`;
}

function obterHoje() {
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  return hoje;
}

function obterAmanha() {
  const amanha = obterHoje();
  amanha.setDate(amanha.getDate() + 1);
  return amanha;
}

function normalizarNumero(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return null;
  }

  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : null;
}

function formatarNumeroBR(valor) {
  if (valor === null || valor === undefined || Number.isNaN(valor)) {
    return "";
  }

  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function padronizarSubmercado(valor) {
  const texto = String(valor || "").trim().toUpperCase();

  if (texto.includes("SUDESTE")) return "SUDESTE";
  if (texto.includes("SUL")) return "SUL";
  if (texto.includes("NORDESTE")) return "NORDESTE";
  if (texto.includes("NORTE")) return "NORTE";

  return texto;
}

function montarDataRegistro(item) {
  const mesReferencia = String(item.MES_REFERENCIA || "").trim();
  const dia = String(item.DIA || "").trim().padStart(2, "0");

  if (!/^\d{6}$/.test(mesReferencia) || !/^\d{2}$/.test(dia)) {
    return null;
  }

  const ano = Number(mesReferencia.slice(0, 4));
  const mes = Number(mesReferencia.slice(4, 6));

  const data = new Date(ano, mes - 1, Number(dia));
  data.setHours(0, 0, 0, 0);

  if (Number.isNaN(data.getTime())) {
    return null;
  }

  return data;
}

function enriquecerRegistros(registros) {
  return registros
    .map((item) => {
      const dataObj = montarDataRegistro(item);
      if (!dataObj) return null;

      return {
        ...item,
        DATA_OBJ: dataObj,
        DATA_ISO: formatarDataISO(dataObj),
        DATA_BR: formatarDataBR(dataObj)
      };
    })
    .filter(Boolean);
}

function montarMatrizHoraria(registros) {
  const matriz = {};

  for (let hora = 0; hora <= 23; hora++) {
    matriz[hora] = {
      Hora: hora,
      NORDESTE: null,
      SUDESTE: null,
      SUL: null
    };
  }

  for (const item of registros) {
    const hora = Number(item.HORA);
    const submercado = padronizarSubmercado(item.SUBMERCADO);
    const valor = normalizarNumero(item.PLD_HORA);

    if (!Number.isInteger(hora) || hora < 0 || hora > 23) continue;
    if (!SUBMERCADOS_DESEJADOS.includes(submercado)) continue;
    if (valor === null) continue;

    matriz[hora][submercado] = valor;
  }

  return Object.values(matriz).sort((a, b) => a.Hora - b.Hora);
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

async function buscarLoteRecente() {
  const url = new URL(BASE_URL);
  url.searchParams.set("resource_id", RESOURCE_ID);
  url.searchParams.set("limit", "32000");

  debugEl.textContent += `URL lote recente:\n${url.toString()}\n\n`;

  const resposta = await fetch(url.toString());

  debugEl.textContent += `HTTP Status lote: ${resposta.status}\n`;
  debugEl.textContent += `Content-Type lote: ${resposta.headers.get("content-type") || "não informado"}\n\n`;

  if (!resposta.ok) {
    const textoErro = await resposta.text();
    debugEl.textContent += `Corpo do erro lote:\n${textoErro}\n\n`;
    throw new Error(`Falha HTTP: ${resposta.status}`);
  }

  const json = await resposta.json();
  debugEl.textContent += `Resposta lote:\n${JSON.stringify(json, null, 2).slice(0, 3000)}\n\n`;

  if (!json.success) {
    throw new Error("A API retornou success=false.");
  }

  const registrosBrutos = json.result?.records || [];

  return registrosBrutos.filter((item) =>
    SUBMERCADOS_DESEJADOS.includes(padronizarSubmercado(item.SUBMERCADO))
  );
}

function filtrarPorDataISO(registros, dataISO) {
  return registros.filter((item) => item.DATA_ISO === dataISO);
}

function obterDatasDisponiveisCompletas(registros) {
  return [...new Set(registros.map((item) => item.DATA_ISO))].sort((a, b) => b.localeCompare(a));
}

async function carregarDados() {
  setStatus("Carregando dados...", "");
  limparTudo();

  try {
    const hoje = obterHoje();
    const amanha = obterAmanha();

    const hojeISO = formatarDataISO(hoje);
    const amanhaISO = formatarDataISO(amanha);

    const registrosBrutos = await buscarLoteRecente();
    const registros = enriquecerRegistros(registrosBrutos);

    if (registros.length === 0) {
      setStatus("Nenhum registro retornado pela API.", "vazio");
      return;
    }

    const datasDisponiveis = obterDatasDisponiveisCompletas(registros);

    debugEl.textContent += `Datas completas encontradas:\n${datasDisponiveis.join(", ")}\n\n`;

    const registrosHoje = filtrarPorDataISO(registros, hojeISO);
    const registrosAmanha = filtrarPorDataISO(registros, amanhaISO);

    const linhasHoje = montarMatrizHoraria(registrosHoje);
    const linhasAmanha = montarMatrizHoraria(registrosAmanha);

    renderizarTabela(linhasHoje, tbodyHojeEl);
    renderizarTabela(linhasAmanha, tbodyAmanhaEl);

    infoHojeEl.textContent = `Hoje: ${formatarDataBR(hoje)} | Registros encontrados: ${registrosHoje.length}`;
    infoAmanhaEl.textContent = `Próximo dia: ${formatarDataBR(amanha)} | Registros encontrados: ${registrosAmanha.length}`;

    if (registrosHoje.length === 0 && registrosAmanha.length === 0) {
      setStatus("Nenhum registro encontrado para hoje e próximo dia.", "vazio");
      return;
    }

    if (registrosHoje.length > 0 && registrosAmanha.length === 0) {
      setStatus("Hoje carregado com sucesso. Próximo dia ainda sem registros.", "ok");
      return;
    }

    if (registrosHoje.length === 0 && registrosAmanha.length > 0) {
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