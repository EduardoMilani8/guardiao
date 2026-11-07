# Como contribuir

Obrigado por querer ajudar. A Guarnição protege o computador de quem o usa, então
cada contribuição precisa deixar a proteção mais confiável, nunca menos.

## Sem programar

Usar a Guarnição no dia a dia e contar o que aconteceu já ajuda muito.

| O que aconteceu | Onde avisar |
|---|---|
| Algo quebrou, travou ou deu mensagem de erro | [Erro](https://github.com/EduardoMilani8/guarnicao/issues/new?template=1-erro.yml) |
| Um arquivo seu, legítimo, foi marcado como ameaça ou suspeito | [Falso positivo](https://github.com/EduardoMilani8/guarnicao/issues/new?template=2-falso-positivo.yml) |
| Um malware passou sem ser detectado | [Não detectado](https://github.com/EduardoMilani8/guarnicao/issues/new?template=3-nao-detectado.yml) |
| Uma ideia de melhoria | [Sugestão](https://github.com/EduardoMilani8/guarnicao/issues/new?template=4-sugestao.yml) |
| Uma falha de segurança na própria Guarnição | **Não abra issue.** Veja o [SECURITY.md](SECURITY.md) |

**Nunca anexe malware de verdade** numa issue, nem dentro de um `.zip`. Mande o
SHA-256 do arquivo (`sha256sum arquivo`) ou o link dele no
[MalwareBazaar](https://bazaar.abuse.ch) ou no [VirusTotal](https://www.virustotal.com).

## Com código

### Preparar o ambiente

Precisa de Linux e Python 3.11 ou mais novo. O ClamAV é opcional.

```bash
git clone https://github.com/EduardoMilani8/guarnicao.git
cd guarnicao
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Os testes não precisam de internet, de root, do ClamAV nem das bases baixadas: eles
usam pastas temporárias e imitações de cada parte.

### Onde fica cada coisa

```
guarnicao/            o programa (cada arquivo começa explicando o que faz)
guarnicao/launcher/   o painel: servidor local e a página
regras/              regras YARA do projeto
contrib/             serviços do systemd e os instaladores
extensao/            a extensão do GNOME (escudo na barra e avisos na muralha)
ferramentas/         medição da taxa de detecção
docs/                documentação
tests/               testes (pytest)
```

O [docs/como-funciona.md](docs/como-funciona.md) explica as decisões de cada parte.

### Antes de abrir um pull request

1. **Converse primeiro em mudanças grandes.** Abra uma sugestão antes de gastar tempo
   numa funcionalidade nova, para alinharmos se ela cabe no projeto.
2. **Escreva um teste** que falha sem a sua mudança e passa com ela.
3. **Rode todos os testes:** `.venv/bin/python -m pytest -q`.
4. **Regra YARA nova ou alterada:** rode uma varredura completa no seu computador e
   diga no pull request quantos falsos positivos apareceram. Uma regra que marca
   arquivos legítimos faz as pessoas desligarem o antivírus.
5. **Mexeu na extensão do GNOME:** rode `node --test extensao/testes/*.test.mjs` e
   teste num GNOME em janela, sem mexer na sua sessão (precisa do pacote
   `mutter-dev-bin`): `dbus-run-session -- gnome-shell --devkit --wayland`. Se mudou
   os retratos ou o escudo, gere a arte de novo com `python3 extensao/construir_arte.py`.
6. **Um assunto por pull request**, com uma descrição que diga o que mudou e por quê.

### As regras da casa

- **Amostras de malware nunca entram no repositório.** Os testes usam o arquivo de
  teste EICAR e trechos montados em tempo de execução com `"".join([...])`, para o
  próprio código da Guarnição não ser detectado por outros antivírus. Vale para nomes
  de regra, variáveis e comentários também.
- **Amostras reais só são lidas, nunca executadas**, e são apagadas depois.
- **O protetor nunca pode travar o computador.** Ele tem 2 segundos para decidir, não
  acessa a rede e, se algo der errado, libera a execução.
- **Só o hash sai do computador.** Nenhuma parte envia arquivos do usuário para fora.
- **O painel nunca roda como root** e só aceita pedidos da própria página.
- **Na dúvida, avisar é melhor do que isolar.** Mover um arquivo legítimo do usuário
  sem ele ver é um erro grave.

### Estilo

- Textos, mensagens, nomes e comentários em português do Brasil.
- Comentário só quando explica o porquê.
- Mensagens de commit curtas, em português, dizendo o que mudou (por exemplo:
  "Avisa quando o freshclam está parado").

## Convivência

Seja respeitoso. Discussões aqui são sobre a Guarnição e o código; mensagens com
ataque pessoal ou propaganda serão fechadas.
