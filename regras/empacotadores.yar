// Executáveis comprimidos/empacotados para esconder o código real.

rule ELF_EmpacotadoUPX
{
    meta:
        descricao = "executável comprimido com UPX: comum em malware para esconder o código"
        gravidade = "media"
    strings:
        $upx = "UPX!"
    condition:
        uint32(0) == 0x464c457f and $upx   // começa com \x7fELF
}
