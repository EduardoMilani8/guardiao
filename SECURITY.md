# Segurança

Um antivírus roda com acesso amplo ao sistema (o protetor roda como root), então uma
falha no Guardião pode ser usada contra quem o instalou.

## Como avisar de uma falha

**Não abra uma issue pública.** Use o aviso privado do GitHub:
[Report a vulnerability](https://github.com/EduardoMilani8/guardiao/security/advisories/new).
Só quem mantém o projeto vê o que você mandar.

Conte o que for possível:

- o que a falha permite fazer (por exemplo: rodar código como root, fazer o painel
  mover um arquivo qualquer, desligar o protetor);
- os passos para reproduzir;
- a versão (`git log -1 --oneline`).

Você recebe uma resposta assim que possível. Depois da correção, a falha é
publicada com o crédito para você, se quiser.

## O que conta como falha

- Escalar privilégios pelo protetor ou pelos instaladores.
- Fazer o painel agir a pedido de outro site (mover, apagar ou ler arquivos).
- Fazer o Guardião executar um arquivo analisado.
- Desligar ou enganar o protetor sem ser root.

Um malware que passa sem ser detectado não é falha de segurança: é um caso de
[Não detectado](https://github.com/EduardoMilani8/guardiao/issues/new?template=3-nao-detectado.yml).
