# Guardião

![Linux](https://img.shields.io/badge/plataforma-Linux-333)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)
![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Antivírus para Linux. Bloqueia ameaças antes de elas executarem, vigia os downloads
e os processos e varre o sistema com ClamAV, regras YARA e os hashes do
MalwareBazaar, atualizados de hora em hora.

![Painel simulando um ataque: cada camada reage ao que encontra](docs/imagens/demonstracao.gif)

## Como funciona

Depois de instalado, o Guardião é formado por cinco serviços do systemd. Nenhum
depende de uma janela aberta.

| Serviço | O que faz | Quando roda |
|---|---|---|
| **Protetor** | Analisa cada programa no instante em que alguém tenta executá-lo e bloqueia se for uma ameaça | O tempo todo, desde o boot |
| **Monitor** | Analisa cada arquivo que termina de baixar em Downloads e avisa se algum processo agir como shell reverso ou minerador | O tempo todo, desde o login |
| **Atualizar bases** | Baixa os hashes, as regras e as assinaturas novas | De hora em hora |
| **Varredura rápida** | Confere os lugares onde malware costuma ficar: Downloads, `/tmp`, programas que iniciam sozinhos | Todo dia, por volta das 12:30 |
| **Varredura completa** | Confere o disco inteiro | Domingo, por volta das 13:00, com o carregador ligado |

O protetor e o monitor olham o que acontece *agora*. As varreduras existem para o
que já estava no disco antes, e para arquivos que pareciam limpos e passaram a ser
reconhecidos depois de uma atualização das bases.

As varreduras agendadas nunca movem nada sozinhas: avisam com uma notificação, e
você decide no painel.

## Painel

```bash
.venv/bin/python -m guardiao launcher
```

Uma página local para disparar varreduras, ver o histórico e mandar ameaças para a
quarentena com um clique.

![Ameaça encontrada, aguardando ser trancada](docs/imagens/carcereiro.png)

## Detecção

Cada arquivo passa por quatro camadas:

1. **Hashes** de malware conhecido, incluindo os enviados ao [MalwareBazaar](https://bazaar.abuse.ch).
2. **[ClamAV](https://www.clamav.net/)**, com milhões de assinaturas.
3. **Regras YARA**: as do projeto e cerca de 5 mil do [YARA Forge](https://github.com/YARAHQ/yara-forge).
4. **Heurísticas**: executável disfarçado de imagem, extensão dupla, conteúdo
   embaralhado. Viram "suspeito", nunca "ameaça" sozinhas.

Arquivos `.zip`, `.tar`, `.docx` e `.jar` são abertos e analisados por dentro.

Opcionalmente, o [VirusTotal](https://www.virustotal.com) confere os downloads
novos e o que a varredura achou suspeito, com a opinião de uns 70 antivírus. Só o
hash do arquivo é enviado, nunca o arquivo.

Medido com 195 amostras reais de novembro de 2026: reconhece **99,5%** do malware
já reportado e cerca de **metade** do malware Linux novo. Os números completos e o
método estão em [docs/deteccao.md](docs/deteccao.md).

## Instalação

Requer Linux e Python 3.11 ou mais novo.

```bash
git clone https://github.com/EduardoMilani8/guardiao.git
cd guardiao
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo apt install clamav clamav-daemon      # recomendado
```

Para ligar os serviços:

```bash
contrib/instalar-servicos.sh               # monitor, atualização e varreduras
sudo contrib/instalar-protetor.sh          # protetor (precisa de root)
```

O MalwareBazaar pede uma chave gratuita, criada em [auth.abuse.ch](https://auth.abuse.ch)
e colocada em `~/.config/guardiao/config.toml`:

```toml
[malwarebazaar]
chave = "..."
```

Para o VirusTotal (opcional), a chave grátis vai no mesmo arquivo, na seção
`[virustotal]`. Sem o ClamAV ou sem uma das chaves, aquela camada fica desligada e o resto funciona
normalmente.

## Uso pelo terminal

```bash
.venv/bin/python -m guardiao varrer --rapida
.venv/bin/python -m guardiao varrer ~/Downloads --isolar
sudo .venv/bin/python -m guardiao varrer --completa      # inclui arquivos do sistema
.venv/bin/python -m guardiao historico --achados
.venv/bin/python -m guardiao virustotal arquivo.exe        # só o hash é enviado
.venv/bin/python -m guardiao quarentena listar
.venv/bin/python -m guardiao quarentena restaurar <id>
.venv/bin/python -m guardiao quarentena apagar <id>       # de vez, pede confirmação
```

Duas ferramentas para usar quando quiser:

- `guardiao cacar` procura o que já se instalou e se esconde: bibliotecas
  injetadas, processos rodando de `/tmp`, serviços que não vieram de nenhum pacote,
  programas do sistema alterados.
- `guardiao dev <pasta>` audita um projeto de programação antes de você instalar as
  dependências: scripts de instalação maliciosos, pacotes com nome falsificado,
  tarefas que rodam sozinhas ao abrir a pasta no editor.

## Limites

- O protetor vale para o que é *executado*. Em `python script.py` quem executa é o
  Python, então o script não passa por ele (mas passa pelo monitor e pelas
  varreduras).
- Detectar malware recém-criado só pelo conteúdo é difícil para qualquer antivírus.
  O monitor de comportamento cobre parte do que escapa.
- Bons hábitos continuam valendo: ler um script antes de rodar e desconfiar de
  `curl | sh`.

## Documentação

- [Como cada parte funciona](docs/como-funciona.md): prazos, cache, configuração,
  segurança do painel.
- [Taxa de detecção](docs/deteccao.md): como foi medida e o que escapou.
- [Roadmap](ROADMAP.md): o que já foi feito e os próximos passos.

## Contribuir

Achou um erro, um falso positivo ou um malware que passou? Veja o
[CONTRIBUTING.md](CONTRIBUTING.md). Falhas de segurança no próprio Guardião vão
pelo [aviso privado](SECURITY.md), nunca por issue pública.

## Testes

```bash
.venv/bin/python -m pytest -q
```

Os testes usam apenas amostras inofensivas: o arquivo de teste EICAR e trechos
montados em tempo de execução, para o próprio código não ser detectado.

## Licença

[MIT](LICENSE) © 2026 Eduardo Milani
