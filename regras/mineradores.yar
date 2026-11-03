// Mineradores de criptomoeda: o malware mais comum em máquinas Linux.

rule MineradorCripto
{
    meta:
        descricao = "configuração ou binário de minerador de criptomoeda"
        gravidade = "alta"
    strings:
        $pool_tcp = "stratum+tcp://" nocase
        $pool_ssl = "stratum+ssl://" nocase
        $xmrig = "xmrig" nocase
        $donate = "--donate-level"
        $algo = /"algo"\s*:\s*"(rx|cn|randomx)/
    condition:
        any of ($pool_*) or ($xmrig and ($donate or $algo))
}
