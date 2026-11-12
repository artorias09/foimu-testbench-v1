# Pedido de captura ao IEAv para P3.5B

Para cruzarmos o decodificador da bancada com a revisão instalada, solicitamos as
capturas abaixo, nas condições autorizadas pelo laboratório. Guardar o arquivo binário
original, sem edição ou conversão para texto. Se disponível, registrar separadamente
o índice das leituras (ordem, offset, tamanho, época e timestamp de recepção com relógio
e resolução). Registrar lacunas do logger, reinícios e alterações de configuração.

| ID | Procedimento | Meta e finalidade |
|---|---|---|
| C1 | Unidade imóvel, orientação e condições anotadas | ≥10 min. Caracterizar framing, counters e distribuição digital em regime |
| C2 | Iniciar logger antes de energizar e marcar o power-on | Até ≥60 s após energizar. Verificar primeiro header, counter inicial, possíveis sentinelas e transição para regime |
| C3 | Rotação lenta conhecida em cada eixo, com marcações de eixo, sentido e instantes | 2–5 min. Registrar posições inicial/final e comparar sinais e ordem dos campos |
| C4 | Desconexão e reconexão física, apenas se autorizada | Opcional. Marcar instantes e observar ressincronização. G5 inicial pode usar C1–C3 |

Para cada arquivo, informar data com fuso, duração, revisão física, identificação/SHA do
firmware instalado quando disponível, variante ACC, configuração, baud e formato serial
efetivos, interface elétrica e modelo do conversor (incluindo RS-422 se aplicável),
orientação, condições do ensaio e identificação do logger. Calcular o SHA-256 na origem
e conferir após transferência. No PowerShell: Get-FileHash arquivo.bin -Algorithm SHA256.

Há um consumidor independente (LabVIEW/VISA, software legado ou logger) que possa
decodificar **o mesmo arquivo**? Se possível, anexar sua versão e a saída digital
indexada por posição de frame. Solicitamos também o layout instalado, datasheet e escala
MEMS, calibração FBG/IFOG aplicável e autorização específica para publicar os trechos
de firmware/documentos no histórico do repositório.

Até confirmação externa, interpretar acc_x/y/z/tap como contagens uint16. Atribuir
unidades físicas aos campos MEMS/IFOG exige a escala da revisão instalada.
