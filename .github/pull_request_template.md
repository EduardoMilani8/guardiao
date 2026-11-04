## O que muda

<!-- Uma ou duas frases. -->

## Por quê

<!-- Qual problema resolve? Se houver, cite a issue: "Resolve #123". -->

## Como conferir

<!-- O que quem revisa pode fazer para ver a mudança funcionando? -->

## Lista de conferência

- [ ] `.venv/bin/python -m pytest -q` passa.
- [ ] Há teste novo ou alterado cobrindo a mudança.
- [ ] Nenhuma amostra de malware entrou no repositório (só EICAR e trechos montados com `"".join([...])`).
- [ ] Se mexi numa regra YARA: rodei uma varredura completa e conto aqui quantos falsos positivos apareceram.
- [ ] Se mexi no protetor: ele continua sem acessar a rede e liberando a execução quando algo dá errado.
- [ ] Se mudei o comportamento de algo, atualizei o README ou o `docs/como-funciona.md`.
