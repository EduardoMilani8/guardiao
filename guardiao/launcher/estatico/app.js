// Protótipo do launcher: recebe os eventos da varredura e anima os guardiões.
// O servidor manda o progresso de tempos em tempos e um evento só para cada
// ameaça ou suspeito; esta página os coloca numa fila e define o próprio ritmo,
// para as reações serem visíveis.

const QUEM_PEGOU = { hash: "guardiao", yara: "arqueira", heuristica: "vidente" };
const INSPETORES = ["guardiao", "arqueira", "vidente"];   // ordem das camadas no motor
const NOMES = { guardiao: "Guardião", arqueira: "Arqueira", vidente: "Vidente", carcereiro: "Carcereiro" };
const MINIMO_MS = 2000;   // tempo mínimo de patrulha na tela

const $ = (seletor) => document.querySelector(seletor);
const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));
const n = (x) => x.toLocaleString("pt-BR");

const estado = {
  fonte: null,
  fila: [],
  processando: false,
  total: 0,
  vistos: 0,
  pulso: 0,
  inicio: 0,
  contadores: { guardiao: 0, arqueira: 0, vidente: 0, carcereiro: 0 },
};

// --- personagens -------------------------------------------------------------

function falar(quem, texto) {
  const balao = $(`#${quem} .balao`);
  balao.textContent = texto;          // textContent, nunca innerHTML: nomes de arquivo vêm de fora
  balao.classList.remove("nova");
  void balao.offsetWidth;             // reinicia a animação
  balao.classList.add("nova");
}

// Troca o texto sem a animação de entrada: para contadores que mudam a cada arquivo.
function atualizar(quem, texto) {
  $(`#${quem} .balao`).textContent = texto;
}

function trabalhando(ligado) {
  INSPETORES.forEach((q) => $(`#${q}`).classList.toggle("trabalhando", ligado));
}

function animar(quem, classe, ms) {
  const el = $(`#${quem}`);
  el.classList.remove(classe);
  void el.offsetWidth;
  el.classList.add(classe);
  setTimeout(() => el.classList.remove(classe), ms);
}

function contar(quem) {
  const contador = $(`#${quem} .contador`);
  contador.textContent = ++estado.contadores[quem];
  contador.classList.add("tem");
}

// --- registro ------------------------------------------------------------------

function registrar(classe, quem, arquivo, detalhe) {
  $(".vazio").hidden = true;
  const item = document.createElement("li");
  item.className = `achado ${classe}`;
  for (const [cls, texto] of [["quem", quem], ["arquivo", arquivo], ["detalhe", detalhe]]) {
    const span = document.createElement("span");
    span.className = cls;
    span.textContent = texto;
    item.append(span);
  }
  $("#lista").prepend(item);
}

// --- reações a cada evento -----------------------------------------------------

async function aoIniciar(ev) {
  $(".progresso").hidden = false;
  $(".atual").textContent = "Preparando a patrulha…";
  falar("guardiao", `Todos a postos! Patrulhando ${ev.alvo}.`);
  falar("arqueira", ev.yara ? "Flecha no arco." : "Estou sem flechas: yara-x não instalado.");
  falar("vidente", "Minha bola de cristal está acesa.");
  falar("carcereiro", "Celas abertas, esperando.");
  ["guardiao", "arqueira", "vidente", "carcereiro"].forEach((q) => animar(q, "ativo", 700));
  estado.inicio = Date.now();
  await espera(900);
  if (estado.fonte) trabalhando(true);   // a pessoa pode ter apertado Parar nesse meio-tempo
}

function aoProgresso(ev) {
  estado.vistos = ev.vistos;
  estado.total = ev.total;
  const listando = ev.fase === "listando";
  $(".barra").classList.toggle("listando", listando);
  // Todo arquivo passa pelas três camadas: um pulso de luz percorre os três
  // em revezamento e os balões mostram o trabalho acumulado.
  animar(INSPETORES[estado.pulso++ % INSPETORES.length], "ativo", 300);

  if (listando) {
    $(".preenchido").style.width = "30%";
    $(".atual").textContent = `Contando arquivos… ${n(ev.vistos)} até agora`;
    atualizar("guardiao", `Reunindo os suspeitos de sempre: ${n(ev.vistos)} arquivos.`);
    atualizar("arqueira", "Escolhendo os alvos.");
    atualizar("vidente", "Sinto muitos arquivos por aí…");
    return;
  }
  $(".preenchido").style.width = `${(100 * ev.vistos) / Math.max(ev.total, 1)}%`;
  $(".atual").textContent = ev.atual ? `Examinando: ${ev.atual}` : `${n(ev.vistos)} de ${n(ev.total)} arquivos`;
  atualizar("guardiao", `Conferi ${n(ev.vistos)} de ${n(ev.total)} rostos.`);
  atualizar("arqueira", `${n(ev.vistos)} arquivos na mira.`);
  atualizar("vidente", `Observei ${n(ev.vistos)} arquivos.`);
}

async function aoArquivo(ev) {
  const quem = QUEM_PEGOU[ev.camada] || "vidente";
  contar(quem);
  animar(quem, "ativo", 1600);

  if (ev.veredito === "ameaca") {
    const nome = ev.ameaca.replace(" (YARA)", "");
    if (quem === "guardiao") {
      animar("guardiao", "alerta", 1000);
      falar("guardiao", `Alto lá! Conheço esse rosto: ${nome}.`);
    } else {
      animar("arqueira", "disparando", 1100);
      falar("arqueira", `Na mira! ${ev.nome}: ${nome}.`);
    }
    contar("carcereiro");
    falar("carcereiro", `Mais um para a cela. Já são ${estado.contadores.carcereiro}.`);
    registrar("ameaca", NOMES[quem], ev.caminho, `Ameaça: ${nome}`);
    await espera(1900);
  } else {
    const motivo = ev.motivos[0] || "algo não está certo";
    if (quem === "vidente") {
      animar("vidente", "alerta", 2100);
      falar("vidente", `Sinto algo errado em ${ev.nome}…`);
    } else {
      animar("arqueira", "disparando", 1100);
      falar("arqueira", `Padrão estranho em ${ev.nome}. De olho nele.`);
    }
    registrar("suspeito", NOMES[quem], ev.caminho, `Suspeito (${ev.pontuacao}/100): ${motivo}`);
    await espera(1500);
  }
}

async function aoTerminar(ev) {
  // Com o cache, uma varredura pode acabar em instantes: os guardiões
  // trabalham um pouco na tela para a patrulha não parecer que nem começou.
  await espera(Math.max(0, MINIMO_MS - (Date.now() - estado.inicio)));
  trabalhando(false);
  $(".barra").classList.remove("listando");
  $(".preenchido").style.width = "100%";
  const conhecidos = ev.em_cache ? `, ${n(ev.em_cache)} sem mudanças desde a última vez` : "";
  $(".atual").textContent = `Patrulha concluída em ${ev.segundos}s: ${n(ev.total)} arquivos${conhecidos}.`;

  if (ev.ameaca === 0 && ev.suspeito === 0) {
    falar("guardiao", `Tudo limpo! ${n(ev.total)} arquivos patrulhados.`);
    falar("arqueira", "Nenhum alvo hoje.");
    falar("vidente", "O futuro parece tranquilo.");
    animar("carcereiro", "ronda", 1500);
    falar("carcereiro", "Ronda feita: celas vazias. Assim que eu gosto.");
    registrar("limpo", "Guarda", "Nenhuma ameaça", `${n(ev.total)} arquivos verificados`);
  } else {
    falar("guardiao", `Patrulha feita: ${ev.ameaca} ameaça(s), ${ev.suspeito} suspeito(s).`);
    if (ev.ameaca > 0) {
      animar("carcereiro", "alerta", 1500);
      animar("carcereiro", "ativo", 2500);
      falar("carcereiro", `Separei ${ev.ameaca} para trancar. No launcher final, é só um clique.`);
    }
  }
  const fora = [];
  if (ev.sem_permissao) fora.push(`${n(ev.sem_permissao)} itens sem permissão de leitura (rode pelo terminal com sudo para incluí-los)`);
  if (ev.grandes) fora.push(`${n(ev.grandes)} arquivos acima do limite de tamanho`);
  if (fora.length) registrar("info", "Guarda", "Fora do alcance", fora.join("; "));
  encerrar();
}

// --- fluxo ------------------------------------------------------------------------

async function processar() {
  estado.processando = true;
  while (estado.fila.length) {
    const ev = estado.fila.shift();
    if (ev.tipo === "inicio") await aoIniciar(ev);
    // Do progresso só importa o mais recente: se outro já chegou, este está velho.
    else if (ev.tipo === "progresso") { if (!estado.fila.some((e) => e.tipo === "progresso")) aoProgresso(ev); }
    else if (ev.tipo === "arquivo") await aoArquivo(ev);
    else if (ev.tipo === "fim") await aoTerminar(ev);
  }
  estado.processando = false;
}

function reiniciar() {
  estado.fila = [];
  estado.total = estado.vistos = estado.pulso = 0;
  for (const quem in estado.contadores) {
    estado.contadores[quem] = 0;
    const contador = $(`#${quem} .contador`);
    contador.textContent = "0";
    contador.classList.remove("tem");
  }
  $("#lista").replaceChildren();
  $(".vazio").hidden = false;
  $(".preenchido").style.width = "0";
  $(".barra").classList.remove("listando");
}

function botoes(ocupado, comParar = ocupado) {
  document.querySelectorAll(".acoes .botao:not(#btn-parar)").forEach((b) => (b.disabled = ocupado));
  $("#btn-parar").hidden = !comParar;
}

function iniciar(consulta) {
  if (estado.fonte) return;
  reiniciar();
  botoes(true);

  const fonte = new EventSource(`/api/varrer?${consulta}`);
  estado.fonte = fonte;
  fonte.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    // Fecha ao receber o fim: senão o EventSource reconecta e varre de novo.
    if (ev.tipo === "fim") fonte.close();
    estado.fila.push(ev);
    if (!estado.processando) processar();
  };
  fonte.onerror = () => {
    if (fonte.readyState === EventSource.CLOSED) return;
    fonte.close();
    falar("guardiao", "Perdi contato com o motor do Guardião. Ele ainda está rodando?");
    encerrar();
  };
}

async function escolherPasta() {
  if (estado.fonte) return;
  botoes(true, false);
  falar("guardiao", "Qual pasta devemos patrulhar? Escolha na janela que abriu.");
  try {
    // O seletor abre do lado do servidor (zenity); a página só recebe um id.
    const resposta = await fetch("/api/escolher-pasta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!resposta.ok) throw new Error(resposta.status === 501 ? "sem zenity" : `HTTP ${resposta.status}`);
    const dados = await resposta.json();
    botoes(false);
    if (dados.cancelado) falar("guardiao", "Tudo bem, fica para outra hora.");
    else iniciar(`alvo=pasta&id=${encodeURIComponent(dados.id)}`);
  } catch (erro) {
    botoes(false);
    falar("guardiao", erro.message === "sem zenity"
      ? "Não achei o seletor de pastas. Instale o zenity."
      : "Não consegui abrir o seletor de pastas.");
  }
}

function parar() {
  if (!estado.fonte) return;
  estado.fonte.close();   // o servidor percebe a conexão fechada e encerra os processos de análise
  estado.fila = [];
  $(".barra").classList.remove("listando");
  $(".atual").textContent = "Patrulha interrompida.";
  falar("guardiao", "Patrulha interrompida. Descansar, guarda!");
  encerrar();
}

function encerrar() {
  trabalhando(false);
  estado.fonte = null;
  botoes(false);
}

$("#btn-rapida").addEventListener("click", () => iniciar("alvo=rapida"));
$("#btn-completa").addEventListener("click", () => iniciar("alvo=completa"));
$("#btn-pasta").addEventListener("click", escolherPasta);
$("#btn-demo").addEventListener("click", () => iniciar("alvo=demo"));
$("#btn-parar").addEventListener("click", parar);
