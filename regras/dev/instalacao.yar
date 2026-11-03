// Código que roda sozinho: scripts de instalação de pacotes, setup.py,
// hooks do git e tarefas automáticas do editor.
// Usadas só pelo módulo de dev: em código comum esses padrões são normais.
// gravidade "alta" = alto risco; "media" = atenção; "info" = contexto.

rule ColetaCredenciais
{
    meta:
        descricao = "lê credenciais ou tokens e acessa a rede (padrão de roubo de dados)"
        gravidade = "alta"
    strings:
        $arq = /\.ssh\/id_|\.aws\/credentials|\.npmrc|\.pypirc|\.git-credentials|\.docker\/config\.json/
        $token = /NPM_TOKEN|GITHUB_TOKEN|GH_TOKEN|AWS_SECRET_ACCESS_KEY/
        $navegador = /Login Data|\.mozilla\/firefox|google-chrome\/Default|Local Storage\/leveldb/
        $rede = /(curl|wget)\s|https?:\/\/|require\(\s*['"](https?|net|dns)['"]|requests\.|urllib|socket/
    condition:
        ($arq or $token or $navegador) and $rede
}

rule CodigoOfuscado
{
    meta:
        descricao = "decodifica e executa código em tempo de execução (ofuscação)"
        gravidade = "alta"
    strings:
        $decodifica = /base64|atob\s*\(|fromCharCode|(\\x[0-9a-fA-F]{2}){16}/
        // Só o que executa texto como código. child_process fica de fora:
        // quase todo instalador legítimo (esbuild, sharp...) roda binários com ele.
        $executa = /eval\s*\(|new\s+Function\s*\(|exec\s*\(/
    condition:
        $decodifica and $executa
}

rule CodigoInline
{
    meta:
        descricao = "executa código escrito direto no comando (node -e / python -c)"
        gravidade = "media"
    strings:
        $inline = /(node|python3?)\s+-[ec]\s/
    condition:
        $inline
}

rule AcessoARede
{
    meta:
        descricao = "acessa a rede (comum em instaladores que baixam binários)"
        gravidade = "info"
    strings:
        $cli = /(curl|wget)\s/
        $node = /require\(\s*['"](https?|net|dgram)['"]\s*\)|fetch\s*\(/
        $py = /urllib\.request|requests\.(get|post)|socket\.socket|http\.client/
        $ps = "Invoke-WebRequest" nocase
    condition:
        any of them
}
