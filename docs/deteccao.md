# Taxa de detecção

Medida em 4 de novembro de 2026 com 195 amostras enviadas ao
[MalwareBazaar](https://bazaar.abuse.ch) entre 2 e 4 de novembro: 98 programas
Linux (ELF), 48 programas Windows (EXE), 24 scripts shell e 25 JavaScript. As
amostras foram só lidas, nunca executadas, e apagadas depois.

## Malware já reportado: 99,5%

194 de 195. Os hashes do MalwareBazaar são baixados de hora em hora: uma amostra
enviada por pesquisadores passa a ser reconhecida em até uma hora.

## Malware novo

Medido *sem* a base de hashes, que daria 100% por construção, já que as amostras
vieram dela. É o que o Guardião reconhece de malware que ninguém reportou ainda:

| | Todas | Linux (ELF) | Windows (EXE) | Shell | JavaScript |
|---|---|---|---|---|---|
| ClamAV sozinho | 22,1% | 39,8% | 8,3% | 0% | 0% |
| Regras YARA sozinhas | 3,6% | 5,1% | 0% | 8,3% | 0% |
| **Guardião: ameaça** | **25,6%** | **44,9%** | 8,3% | 8,3% | 0% |
| **Guardião: ameaça ou suspeito** | **34,9%** | **54,1%** | 16,7% | 29,2% | 0% |

O que mais escapou foram variantes recompiladas da botnet Mirai, cada uma com um
hash novo, e JavaScript ofuscado (ladrões de senha do Windows).

Depois dessa medição vieram regras para os droppers JavaScript do Windows Script
Host (`regras/javascript_windows.yar`). Elas foram escritas olhando 58 amostras e
medidas em outras 41 que não foram usadas para escrevê-las: o JavaScript foi de 0%
para **46,3%**, sem nenhum falso positivo em 1,14 milhão de arquivos de um disco real.

## O que não entra nesta conta

Os números medem só o conteúdo dos arquivos. Ficam de fora o
[monitor de comportamento](como-funciona.md#monitor-de-comportamento), que reconhece
um shell reverso ou um minerador pelo que ele faz, seja qual for o arquivo, e o
[caçador](como-funciona.md#caçador), que procura o que já se instalou. É assim
também nos antivírus comerciais: detectar malware recém-criado só pelo conteúdo é
difícil, e o comportamento cobre parte do que escapa.

## Como medir de novo

```bash
.venv/bin/pip install -r ferramentas/requirements.txt
.venv/bin/python -I ferramentas/medir_deteccao.py --desde AAAA-MM-DD
```

O script baixa as amostras mais recentes de cada tipo, vistas a partir de
`--desde` (o dia seguinte à última medição, para nenhuma amostra se repetir),
mede sem a base de hashes e apaga tudo no fim. Ele imprime a tabela no formato
desta página. Precisa da chave do MalwareBazaar.
