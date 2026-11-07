# Prompt para o Claude Design: painel e avisos da Guarnição

> Anexe junto com este texto as imagens do painel atual:
> `docs/imagens/carcereiro.png` e `docs/imagens/demonstracao.gif`.

---

Quero redesenhar a interface de um antivírus para Linux chamado **Guarnição** (o nome
antigo era Guardião; está mudando agora, então o logo e a marca são novos). Preciso
de ajuda com a parte visual: direção de arte, telas e componentes. O código vem
depois, então não se preocupe com implementação.

## O que é a Guarnição

Um antivírus de código aberto para Linux, em português do Brasil. Ela trabalha quase
todo o tempo sozinho, em segundo plano:

- **Protetor:** analisa cada programa no instante em que alguém tenta executá-lo e
  bloqueia se for uma ameaça.
- **Monitor:** analisa cada arquivo que termina de baixar e percebe processos agindo
  como invasores (acesso remoto escondido, mineração de criptomoeda).
- **Atualização das bases:** baixa assinaturas de malware novas de hora em hora.
- **Varredura rápida:** todo dia, nos lugares onde malware costuma ficar.
- **Varredura completa:** todo domingo, no disco inteiro.

Quando acha algo, ela avisa. Mover um arquivo para a **quarentena** (isolar) é
sempre decisão da pessoa, com um clique.

Quem usa: pessoas que usam Linux no dia a dia, de estudantes a programadores. Não
são necessariamente especialistas em segurança.

## O que precisa de design

### 1. O painel

Uma página local, aberta no navegador do próprio computador. Hoje ela tem:

- os botões **Varredura rápida**, **Varredura completa**, **Escolher pasta** e
  **Simular ataque** (cria arquivos de teste inofensivos para mostrar o antivírus
  agindo);
- o andamento da varredura ao vivo, com o botão de **parar**;
- o **registro** do que foi encontrado, cada ameaça com o botão **Trancar** (mandar
  para a quarentena) e um **Trancar todas** quando há várias;
- as **últimas varreduras**: quando foram, quantos arquivos, quanto tempo levaram e o
  resultado;
- ameaças achadas pelas varreduras automáticas que ainda não foram tratadas.

O painel atual tem um tema medieval com quatro personagens de RPG em estilo cartoon.
Fundo azul-marinho estrelado, dourado, fonte com serifa clássica. Funciona, mas parece
**projeto de escola**, não um produto em que se confia para proteger o computador.

**O nome vem desses personagens.** Guarnição é o grupo de soldados que defende uma
fortaleza: o computador é a fortaleza, e os quatro são a guarnição. Cada um é uma forma
diferente de reconhecer ou tratar uma ameaça, da mais certa para a menos certa:

| Personagem | O que faz | Em uma frase |
|---|---|---|
| **Cavaleiro** | Reconhece ameaças já conhecidas pela "impressão digital" do arquivo (bases de assinaturas) | "Esse eu conheço, é procurado." |
| **Arqueira** | Procura padrões dentro do arquivo; pega ameaças novas parecidas com famílias conhecidas | "Nunca vi esse, mas tem o jeito daquela quadrilha." |
| **Vidente** | Intuição: soma sinais estranhos e marca como *suspeito*, sem certeza; percebe programas agindo como invasores | "Não sei o que é, mas não deveria estar aqui." |
| **Carcereiro** | Tranca o arquivo na quarentena quando a pessoa manda, até ela decidir; pode soltar de volta | "Fica preso até o juiz decidir." |

O Cavaleiro e a Arqueira dizem **ameaça**; o Vidente diz **suspeito**. O Carcereiro não
detecta nada: ele age, e só quando a pessoa clica.

### 2. Os avisos

A filosofia é: **o antivírus precisa lembrar que existe e está funcionando, sem
cansar.** Se avisar demais, a pessoa aprende a fechar sem ler e um dia ignora o aviso
que importa. Se nunca avisar, ela esquece que está protegida.

| Situação | Como avisa |
|---|---|
| Ameaça encontrada | Aviso forte, que fica na tela até a pessoa agir |
| Varredura automática terminou limpa | Resumo discreto, que some sozinho em poucos segundos, no máximo um por dia. Ex.: "Varredura rápida concluída: 305 arquivos, tudo limpo" |
| Download limpo | Nenhum aviso |

Os avisos vão aparecer no **canto da tela**, desenhados com a mesma arte do painel
(serão uma extensão do GNOME, o ambiente gráfico do Ubuntu).

### 3. O ícone na barra de cima do GNOME

Um pequeno escudo na barra superior que mostra o estado num relance:

- tudo certo;
- algo pede atenção (por exemplo, a base de assinaturas está desatualizada);
- ameaça encontrada e não tratada.

Ao clicar, abre um menu curto: última varredura, estado da proteção, botões
"Varredura rápida" e "Abrir painel". O ícone precisa funcionar em 16 px, monocromático,
como os ícones do sistema (estilo "symbolic" do GNOME), nos temas claro e escuro.

## O tom que eu quero

- **Sério e confiável**, de produto, não de brincadeira. Calmo, que passe segurança.
- **Simples e claro.** Quem abre precisa entender em dois segundos: "estou protegido?".
- **Sem emoji.**
- Evite os clichês de "hacker" (letras verdes estilo Matrix, caveiras, cadeados por
  todo lado) e o medo como estratégia (tudo vermelho, alarmes piscando). Vermelho só
  para ameaça de verdade.
- **Os quatro personagens ficam**, porque o nome depende deles, mas precisam de
  acabamento profissional: pense em ilustração de produto ou emblema heráldico, não em
  cartoon infantil. Podem aparecer como retrato, emblema ou ícone, conforme o lugar (no
  escudo de 16 px, por exemplo, não cabem personagens).
- A escala de certeza (ameaça, suspeito, limpo) pode aparecer no visual.

## O que eu gostaria de receber

1. **Duas ou três direções de arte** bem diferentes entre si, cada uma com: logo da
   Guarnição, paleta, tipografia, estilo de ícones, os quatro personagens nesse estilo
   e uma tela principal de exemplo.
2. Depois que eu escolher uma, as telas e os estados:
   - painel em repouso, tudo limpo ("Você está protegido", última varredura, bases em
     dia);
   - varredura em andamento (progresso, arquivo atual, botão de parar);
   - ameaça encontrada, com Trancar e Trancar todas;
   - algo pede atenção (base desatualizada, serviço de atualização parado);
   - histórico das varreduras;
   - os dois avisos do canto (ameaça e resumo discreto);
   - o escudo da barra de cima nos três estados e o menu aberto.
3. **Tema claro e tema escuro.**
4. Funcionar bem numa janela de notebook e também estreita (celular), porque a página
   abre no navegador.

## Restrições

- Tudo em **português do Brasil**.
- **Fontes que possam ser embutidas no projeto** (licença livre, como SIL Open Font
  License). Um antivírus não deve buscar nada em servidores de terceiros ao abrir o
  painel, nem fontes.
- **Acessibilidade:** bom contraste, nada que dependa só da cor (ameaça, atenção e
  limpo também se diferenciam por ícone e texto), legível para quem usa zoom.
- Nada de animação exagerada. Movimento só para indicar que algo está acontecendo
  (varredura rodando) ou para chamar atenção a uma ameaça.

## Textos de exemplo, com dados reais

- "Você está protegido"
- "Última varredura rápida: hoje, 12:30 · 305 arquivos · tudo limpo"
- "Última varredura completa: domingo"
- "Bases atualizadas há 3 minutos"
- "Ameaça encontrada: fatura-novembro.pdf.exe (EICAR-Test-File)"
- "Encontrado na varredura das 12:30 · Trancar"
- "O serviço que atualiza as assinaturas do ClamAV está parado"
- "1 ameaça · 0 suspeitos · 1,8 s"
- "Varredura rápida concluída: 305 arquivos, tudo limpo"
