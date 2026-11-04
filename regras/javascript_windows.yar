// Droppers em JavaScript para o Windows Script Host (wscript.exe).
// Chegam como anexo .js e baixam ladrões de senha (AgentTesla, Formbook...).
// Só rodam no Windows, mas passam por aqui em e-mails, pendrives e Downloads.
//
// `wide` procura também em UTF-16: o WSH executa scripts com BOM FF FE, e
// boa parte das amostras vem assim para escapar de buscas em texto simples.
// Nenhuma regra dispara só com ActiveXObject: bibliotecas antigas (jQuery)
// o usam para o XMLHttpRequest do Internet Explorer.

// Regra auxiliar: é texto (UTF-16 com BOM, ou sem byte zero no começo).
// O Wine, DLLs .NET e bibliotecas compiladas citam WScript e PowerShell sem
// ser script nenhum.
private rule Texto
{
    condition:
        uint16(0) == 0xFEFF or
        for all i in (0..511) : (i >= filesize or uint8(i) != 0)
}

// Regras auxiliares: texto que *usa* objetos do Windows, em vez de só citá-los
// (o registro do Wine e documentação citam "WScript.Shell" sem chamar nada).
// UsaWSH só existe no Windows Script Host; ActiveXObject também aparece em
// bibliotecas web antigas, para o XMLHttpRequest do Internet Explorer.
private rule UsaWSH
{
    strings:
        $cria = /\.CreateObject\s*\(/ ascii wide
        $pega = /GetObject\s*\(/ ascii wide
        $wsh = /WScript\.(Quit|Echo|Arguments|ScriptFullName|CreateObject)\b/ ascii wide
    condition:
        Texto and filesize < 20MB and any of them
}

private rule ScriptWSH
{
    strings:
        $novo = /new\s+ActiveXObject\s*\(/ ascii wide
    condition:
        UsaWSH or (Texto and filesize < 20MB and $novo)
}

rule JS_WSH_RodaComando
{
    meta:
        descricao = "script do Windows que executa comandos (WScript.Shell)"
        gravidade = "alta"
    strings:
        $shell = "WScript.Shell" ascii wide nocase
        $run = /\.(Run|Exec|ShellExecute)\s*\(/ ascii wide
    condition:
        ScriptWSH and $shell and $run
}

rule JS_WSH_PowerShell
{
    meta:
        descricao = "script do Windows que chama o PowerShell"
        gravidade = "alta"
    strings:
        $ps = "powershell" ascii wide nocase
    condition:
        UsaWSH and $ps
}

rule JS_WSH_CriaProcessoWMI
{
    meta:
        descricao = "script do Windows que cria processos pelo WMI (Win32_Process)"
        gravidade = "alta"
    strings:
        $wmi = "winmgmts" ascii wide nocase
        $proc = "Win32_Process" ascii wide
    condition:
        ScriptWSH and $wmi and $proc
}

rule JS_WSH_BaixaESalva
{
    meta:
        descricao = "script do Windows que baixa um arquivo e grava no disco"
        gravidade = "alta"
    strings:
        $http = /(MSXML2\.(Server)?XMLHTTP|WinHttp\.WinHttpRequest)/ ascii wide nocase
        $stream = "ADODB.Stream" ascii wide nocase
        $salva = "SaveToFile" ascii wide nocase
    condition:
        ScriptWSH and $http and $stream and $salva
}

rule JS_WSH_ObjetosEscondidos
{
    meta:
        descricao = "script do Windows que cria vários objetos com o nome escondido numa variável"
        gravidade = "alta"
    strings:
        // new ActiveXObject(XPTOQWERTY) em vez de new ActiveXObject("WScript.Shell")
        $dinamico = /new\s+ActiveXObject\s*\(\s*[A-Za-z_$][\w$]*\s*\)/ ascii wide
        $proprio = "ScriptFullName" ascii wide
        $wsh = "WScript." ascii wide
    condition:
        ScriptWSH and #dinamico >= 4 and ($proprio or $wsh)
}

rule JS_WSH_Ofuscado
{
    meta:
        descricao = "script do Windows ofuscado (texto gigante ou montado caractere a caractere)"
        gravidade = "media"
    strings:
        // Só objetos que não existem fora do Windows Script Host: um pacote web
        // com ActiveXObject e uma imagem embutida em base64 não pode disparar.
        $wsh = "WScript." ascii wide
        $proprio = "ScriptFullName" ascii wide
        // Um blob codificado (base64, hex, %xx), não código minificado entre aspas.
        $gigante = /["'][A-Za-z0-9+\/=%\\]{3000}/ ascii wide
        $char = "fromCharCode" ascii wide
        $unicode = /(\\u[0-9A-Fa-f]{4}){6}/ ascii wide
    condition:
        UsaWSH and ($wsh or $proprio) and ($gigante or #char > 10 or #unicode > 50)
}
