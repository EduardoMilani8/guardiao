# Guia dos retratos da Guarnição

Aprovado em 2026-11-04, a partir do Cavaleiro. Use este guia para fazer a Arqueira, o Vidente e o Carcereiro.

## Referência

- **Retrato aprovado:** `cav-espada3.svg`. Para ver, abra `cavaleiro-gravura-espada-revisada.html`.
- **No canvas:** está em `Retrato.dc.html`, que é usado em todas as telas.
- **Versões guardadas:** ficam no quadro "Cavaleiro · versões". Não apague nenhuma.

## Os personagens

| Personagem | O que representa | Como está hoje (v3) |
|---|---|---|
| Cavaleiro | assinaturas | pronto, gravura |
| Arqueira | regras (YARA) | capuz com bainha dourada, trança, ombreira de folhas, aljava; pinheiros, névoa, vaga-lumes |
| Vidente | sinais suspeitos | olhos que brilham, barba presa em ouro, manto de estrelas, cajado com orbe; lua, runas |
| Carcereiro | quarentena | cicatriz, barba trançada com anéis de ferro, gola de pele, molho de chaves e lanterna; masmorra com tocha |

Mantenha os mesmos elementos, mas redesenhados no estilo de gravura.

## Estilo: gravura colorida

- **Contorno:**
  - uma linha grossa só por fora da figura, com `stroke-width` 3.4;
  - linhas finas por dentro, com 0.9.
- **Ordem de desenho:**
  - cada peça leva o preenchimento e a linha juntos;
  - desenhe de trás para a frente, para que o que está atrás fique escondido.
- **Nunca uma passada de linhas por cima de tudo.** Ela mostra as bordas escondidas, e foi isso que deixou a figura com cara de "componentes encaixados" e de "boneco de IA".
- **Sombra:**
  - em hachura, nunca em degradê;
  - nas juntas entre peças, uma sombra escura (opacidade 0.55).
- **Cor:** chapada, com poucas cores.
- **Brilho:** um traço branco fino.
- **Pose e moldura:**
  - de frente e simétrico;
  - a mesma moldura e o mesmo arco do Cavaleiro;
  - a cena fica ao fundo.

## O que não funcionou

- **Degradê em tudo (v3):** ficou com cara de boneco de IA, peças montadas umas sobre as outras.
- **Estilo Howard Pyle, com giro de 3/4 e traço tremido:** ficou quebrado, com um braço maior que o outro.

## Checklist ao terminar cada retrato

Faça esta revisão antes de mostrar. São os pontos que foram corrigidos no Cavaleiro.

1. **Centro:** o eixo da figura cai em x=120 (cabeça, peito, peça central e emblema). Confira pelos números, não a olho. No Cavaleiro, o "quadrado azul" estava 2 unidades fora.
2. **Nada saindo para fora:** brilhos, frisos e detalhes ficam dentro do contorno da peça. No Cavaleiro, uma linha branca saía do capacete.
3. **Juntas** (cotovelo, ombro, pulso): uma peça só, desenhada por cima da junta e dentro da silhueta do braço. Uma concha com aba separada virou "orelha".
4. **Mãos e braços:**
   - os dois lados com o mesmo tamanho;
   - mão ligada ao antebraço;
   - dedos arredondados;
   - nada quadrado.
5. **Tudo ligado:** nenhuma parte parece colada por cima, e não aparece nenhuma borda escondida.
6. **Harmonia:** renderize ao lado da versão anterior e veja de perto a metade de cima e a de baixo.

7. **Objetos presos ao corpo:** um arco ou acessório sozinho na borda do quadro parece solto. Passe por trás do ombro ou coloque na mão (foi o caso do arco da Arqueira).
8. **Sem "domo":** marque os ombros e deixe as laterais retas. Manto e peito em forma de cúpula ficam muito redondos.
9. **Capuz:** pontudo não parece capuz. Na Arqueira ficou baixado no pescoço, com o cabelo à mostra.
10. **Proporção:** a cabeça fica na mesma altura da do Cavaleiro, e os ombros medem umas 2,3 larguras de cabeça. Um corpo largo demais parece "um cara grande".
11. **Equipamento junto e discreto:** arco e aljava ficam do mesmo lado e aparecem pouco acima do ombro. Um item em cada ombro ficou estranho, e flechas altas demais chamam atenção.
12. **Peças ligadas, alinhadas:** a aljava fica no prolongamento da correia; senão parecem coisas diferentes. O arco ficou na mão baixa, mostrando só um pedaço da madeira.
13. **Cabelo e rosto:** o cabelo é uma peça só (a trança de "bolinhas" saindo do cabelo liso pareceu outra coisa). O rosto não deve ser oval demais: maçãs mais largas e queixo marcado.
14. **Mão só quando ajuda:** a mão segurando o arco não combinou. Ficou só o pedaço do arco entrando por baixo do quadro. Uma franja grande, cobrindo a testa, também ajuda o rosto a não parecer oval.
15. **Sombras e dourados:** a sombra de uma junta não passa por cima de uma peça que está na frente (a sombra da bainha do capuz cortava a barba do Vidente). E dois detalhes dourados não ficam na mesma altura, senão um some no outro.
16. **Capuz justo e cajado à frente:** o capuz segue a forma da cabeça. Alto e largo, ele não parece encaixado. Um cajado nas costas não faz sentido: ele fica na frente, entrando por baixo do quadro. O fundo também conta quem é o personagem; no Vidente, um círculo mágico e constelações.

17. **Cabeça ligada ao corpo:** o pescoço e o trapézio sobem até a mandíbula, e a gola abraça o pescoço, sem ficar como uma faixa reta embaixo. A barba desce por cima da gola. Uma cabeça "pousada" num tronco reto parece "um montão de componentes soltos" (Carcereiro v1). Um arco ou porta escura atrás da cabeça ajuda a segurar a figura no fundo.
18. **Pescoço e linhas do corpo:** mostrar o pescoço dos lados de uma barba afunilada piorou o Carcereiro (v3). Funcionou melhor deixar a gola subir até o queixo, com a barba larga por cima e uma sombra na gola ao lado da barba. As linhas de dentro do corpo ficam retas e alinhadas entre si: as costuras na altura da base das ombreiras, e a linha do braço reta, descendo da ombreira. Curvas soltas, cada uma num ângulo, ficam bagunçadas. O corpo também não pode ser quadrado: os ombros são redondos e as laterais afunilam para baixo. Uma gola alta e grossa deixa o pescoço comprido: com o rosto terminando em y 174, os ombros ficam por volta de y 208 e a gola é só uma faixa curta. Nada importante abaixo de y≈280, porque a base da moldura cobre essa parte (o cinto do Carcereiro sumiu).

## Processo

1. Desenhar o personagem no estilo acima.
2. Renderizar no servidor local "retratos" (porta 8790) e passar o checklist.
3. Corrigir o que o checklist achar e só então mostrar.
4. Guardar cada versão aqui e no quadro de versões do canvas.
