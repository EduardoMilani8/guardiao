// Protótipo do launcher: recebe os eventos da varredura e anima os guardiões.
// O servidor manda os eventos o mais rápido possível; esta página os coloca
// numa fila e define o próprio ritmo, para as reações serem visíveis.

const QUEM_PEGOU = { hash: "guardiao", yara: "arqueira", heuristica: "vidente" };
const INSPETORES = ["guardiao", "arqueira", "vidente"];   // ordem das camadas no motor
const NOMES = { guardiao: "Guardião", arqueira: "Arqueira", vidente: "Vidente", carcereiro: "Carcereiro" };

const $ = (seletor) => document.querySelector(seletor);
const espera = (ms) => new Promise((ok) => setTimeout(ok, ms));

const estado = {
  fonte: null,
  fila: [],
  processando: false,
  total: 0,
  vistos: 0,
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
  estado.total = ev.total;
  $(".progresso").hidden = false;
  falar("guardiao", `Todos a postos! Patrulhando: ${ev.alvo}.`);
  falar("arqueira", ev.yara ? "Flecha no arco." : "Estou sem flechas: yara-x não instalado.");
  falar("vidente", "Minha bola de cristal está acesa.");
  falar("carcereiro", "Celas abertas, esperando.");
  ["guardiao", "arqueira", "vidente", "carcereiro"].forEach((q) => animar(q, "ativo", 700));
  await espera(900);
  trabalhando(true);
}

async function aoArquivo(ev) {
  estado.vistos++;
  $(".preenchido").style.width = `${(100 * estado.vistos) / Math.max(estado.total, 1)}%`;
  $(".atual").textContent = `Examinando: ${ev.caminho}`;

  if (ev.veredito === "limpo") {
    // Todo arquivo passa pelas três camadas: um pulso de luz percorre os três
    // em revezamento e os balões mostram o trabalho acumulado.
    animar(INSPETORES[(estado.vistos - 1) % INSPETORES.length], "ativo", 300);
    atualizar("guardiao", `Conferi ${estado.vistos} de ${estado.total} rostos.`);
    atualizar("arqueira", `${estado.vistos} arquivos na mira.`);
    atualizar("vidente", `Observei ${estado.vistos} arquivos.`);
    // Quanto mais arquivos, mais rápido: a parte limpa leva uns 2,5 s no total.
    await espera(Math.max(12, Math.min(140, 2500 / Math.max(estado.total, 1))));
    return;
  }

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
  trabalhando(false);
  $(".preenchido").style.width = "100%";
  $(".atual").textContent = `Patrulha concluída: ${estado.total} arquivos.`;

  if (ev.ameaca === 0 && ev.suspeito === 0) {
    falar("guardiao", `Tudo limpo! ${estado.total} arquivos patrulhados.`);
    falar("arqueira", "Nenhum alvo hoje.");
    falar("vidente", "O futuro parece tranquilo.");
    animar("carcereiro", "ronda", 1500);
    falar("carcereiro", "Ronda feita: celas vazias. Assim que eu gosto.");
    registrar("limpo", "Guarda", "Nenhuma ameaça", `${estado.total} arquivos verificados`);
  } else {
    falar("guardiao", `Patrulha feita: ${ev.ameaca} ameaça(s), ${ev.suspeito} suspeito(s).`);
    if (ev.ameaca > 0) {
      animar("carcereiro", "alerta", 1500);
      animar("carcereiro", "ativo", 2500);
      falar("carcereiro", `Separei ${ev.ameaca} para trancar. No launcher final, é só um clique.`);
    }
  }
  encerrar();
}

// --- fluxo ------------------------------------------------------------------------

async function processar() {
  estado.processando = true;
  while (estado.fila.length) {
    const ev = estado.fila.shift();
    if (ev.tipo === "inicio") await aoIniciar(ev);
    else if (ev.tipo === "arquivo") await aoArquivo(ev);
    else if (ev.tipo === "erro") registrar("suspeito", "Guarda", ev.caminho, `Não consegui ler: ${ev.mensagem}`);
    else if (ev.tipo === "fim") await aoTerminar(ev);
  }
  estado.processando = false;
}

function reiniciar() {
  estado.fila = [];
  estado.total = estado.vistos = 0;
  for (const quem in estado.contadores) {
    estado.contadores[quem] = 0;
    const contador = $(`#${quem} .contador`);
    contador.textContent = "0";
    contador.classList.remove("tem");
  }
  $("#lista").replaceChildren();
  $(".vazio").hidden = false;
  $(".preenchido").style.width = "0";
}

function iniciar(alvo) {
  if (estado.fonte) return;
  reiniciar();
  document.querySelectorAll(".botao").forEach((b) => (b.disabled = true));

  const fonte = new EventSource(`/api/varrer?alvo=${alvo}`);
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

function encerrar() {
  trabalhando(false);
  estado.fonte = null;
  document.querySelectorAll(".botao").forEach((b) => (b.disabled = false));
}

$("#btn-downloads").addEventListener("click", () => iniciar("downloads"));
$("#btn-demo").addEventListener("click", () => iniciar("demo"));
