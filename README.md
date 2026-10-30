# FO-IMU testbench — primeira versão executável

**** O projeto reproduz a saída binária do gateway anexado: 53 bytes, header A0 A0, counter8, floats/inteiros little-endian e Fletcher-16. Os sinais são sintéticos. Os repositórios IEAv originais não foram alterados.

Você precisa apenas do PC e Python 3.11 ou superior. Esta etapa não requer ESP32, Raspberry, LabVIEW, pip ou Docker. O código foi executado em Python 3.12.14/Linux neste ambiente; a execução no seu Windows ainda precisa ser confirmada.

## Primeiro ensaio no Windows

Extraia o ZIP e abra o PowerShell **dentro da pasta `foimu-testbench`**, onde está este README.

```powershell
py -3 --version
py -3 -m foimu_testbench demo --config configs/normal.json --out logs/primeiro_ensaio
```

Se o comando `py` não existir, use `python` no lugar, desde que a versão seja ≥3.11.

Esperado: 1000 pacotes recebidos, zero perdas inferidas, zero erros de checksum/framing. É um ensaio acelerado com relógio virtual: não espere dez segundos. Os resultados vão para uma **pasta nova**; para repetir, use outro nome. O programa recusa sobrescrever uma pasta existente.

Abra `logs/primeiro_ensaio/report.md`. Os demais arquivos são:

| Arquivo | O que prova |
|---|---|
| report.json | métricas, estatísticas por canal, configuração, versão, hash do código e limites de inferência |
| samples.csv | frames aceitos, counter, campos e timestamp de recepção do modelo |
| wire.bin | bytes realmente entregues ao parser, inclusive corrupção quando habilitada |
| chunks.jsonl | limites dos blocos, offsets, tempos e eventos de conexão |
| config.resolved.json | configuração completa usada, incluindo seed |

## Testar perda e checksum

```powershell
py -3 -m foimu_testbench demo --config configs/loss.json --out logs/perda_01
py -3 -m foimu_testbench demo --config configs/checksum.json --out logs/checksum_01
py -3 -m foimu_testbench demo --config configs/jitter.json --out logs/jitter_01
```

`loss.json`: 1001 oportunidades, 100 frames retirados, 901 aceitos, 100 perdas inferidas. O frame final válido permite observar a última lacuna.

`checksum.json`: 1000 oportunidades, 100 checksums alterados, 900 frames aceitos. O último corrompido não tem sucessor para revelar sua perda por counter; o total inferido pode ser99, embora o oráculo saiba que100 foram corrompidos. Headers falsos também podem produzir mais candidatos de checksum inválido que frames injetados. Essa distinção é intencional, não “arredondada” para passar no teste.

## Dois programas separados, usando tempo real

No primeiro PowerShell:

```powershell
py -3 -m foimu_testbench simulate --config configs/normal.json --packets 3000
```

No segundo, na mesma pasta:

```powershell
py -3 -m foimu_testbench acquire --seconds 35 --out logs/tcp_01
```

O servidor escuta `127.0.0.1:8765` e começa quando o cliente se conecta. São bytes TCP com o mesmo pacote; não é uma porta COM virtual. O parser não conhece o gerador. O horário de recepção pode variar com agendamento e buffering do sistema operacional. Os 5 segundos depois de terminar a emissão podem gerar um timeout de stream: isso é esperado pela duração escolhida.

Para testar reconexão, inicie outro ensaio do servidor com `--disconnect-at 100` e outro diretório no cliente. O servidor fecha uma conexão antes do índice100 e aceita a próxima; o cliente se reconecta. Ao perder a conexão, ele descarta um frame parcial e reinicia a referência de counter. Não atribui perda física exata ao intervalo desconectado.

Durante desconexão o servidor aguarda cliente e pode depois recuperar o cronograma com burst. Esse é o comportamento deste emulador TCP, não uma afirmação sobre o firmware real. `Ctrl+C` encerra a aquisição e salva o que já recebeu. Erros de disco ainda não possuem um mecanismo completo de recuperação.

## Replay

```powershell
py -3 -m foimu_testbench replay --input logs/primeiro_ensaio/wire.bin --timing logs/primeiro_ensaio/chunks.jsonl --out logs/replay_01
```

Mantém bytes, blocos e tempos observados. Sem `--timing`, o replay inventa intervalos nominais por bloco de53 B e registra essa limitação. Uma captura física futura poderá alimentar o mesmo parser; ainda falta o adaptador de aquisição COM nesta versão. CSV isolado não conserva framing/checksum original.

## Testes reproduzíveis

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m tools.acceptance --out logs/aceitacao_01
```

O segundo comando executa a suíte e um milhão de frames acelerados. `tests/fixtures/reference_gateway.c` contém a struct e o Fletcher extraídos do gateway, com origem/linhas. O vetor C está salvo em binário/hex, então não é necessário instalar compilador no Windows para rodar os testes. Isso valida o contrato de bytes contra uma referência independente; não significa executar o STM32 no PC.

## Ensaio de oito horas, posteriormente

Primeiro terminal:

```powershell
py -3 -m foimu_testbench simulate --config configs/soak_8h.json
```

Segundo terminal:

```powershell
py -3 -m foimu_testbench acquire --config configs/soak_8h.json --seconds 28810 --out logs/oito_horas_01
```

São 2.880.000 oportunidades no simulador, 152,64 MB só de bytes crus, além de CSV e JSONL. Reserve vários GB, mantenha a máquina ligada e sem suspensão. O host não recebe um contador largo ou número total pelo protocolo legado, então `packets_expected` do cliente fica `null`; compare o total com a configuração do emissor. A pausa final de10 s entra nas métricas de ausência de dados. Um comando preparado não significa que esse ensaio já foi executado. Ainda falta telemetria periódica de RSS/CPU/disco para aprovar a Fase de longa duração.

## O que está pronto e o que ainda falta

| Recurso | Estado nesta entrega |
|---|---|
| Auditoria dos seis snapshots e dois documentos | feita, com limites de leitura de LabVIEW/Altium declarados |
| Codec53 B e parser incremental | implementados e testados |
| Sinais sintéticos, relógio virtual e TCP real | implementados |
| Logging binário, CSV, sidecar temporal, relatórios JSON/Markdown | implementados |
| Drop, checksum, byte, header, truncamento, jitter por configuração | implementados |
| Burst/fragmentação, NaN/Inf, duplicata, wrap e ordem | cobertos por testes; nem todos expostos como falhas configuráveis |
| Reconexão TCP e silêncio de stream | implementados/testados; timeout de sensor não inferível |
| Estatísticas por canal e8 posições térmicas | implementadas; não há validação de faixa física |
| COM/USB serial e programa real VISA | ainda não integrados |
| Mocks de IFOG/ACC/MEMS e scheduler original | especificados; ainda não implementados |
| Congelamento, ausência de sensor, atrasos crescentes e desordem configurável | próximos passos da Fase2 |
| Perfil de boot e reprodução dos travamentos originais | próximos passos; o gerador normal representa regime estável ideal |
| Comparador automático A/B e profiling prolongado | especificados; ainda não implementados |
| Dashboard gráfico | posterior; a interface inicial é CLI e arquivos de relatório |
| ESP32 e HIL | especificados; nenhum sketch gravado ou hardware validado |

Não acrescente campos “status” ou timestamps ao frame legado sem criar um perfil separado: isso quebraria a compatibilidade que queremos testar.

## Leitura recomendada

1. [Auditoria completa](docs/AUDITORIA_FASE_0.md): arquitetura, versões, interfaces, sincronização, riscos e hardware.
2. [Especificação](docs/ESPECIFICACAO_TESTBENCH.md): métricas, oráculos e critérios provisórios.
3. [Evidências de código](docs/EVIDENCIAS.md): trechos numerados das fontes.
4. [Resultados executados](docs/VALIDACAO.md): o que efetivamente passou e o que não foi validado.

O próximo passo conjunto é rodar o primeiro ensaio acima no seu Windows e comparar os números do relatório. A primeira confirmação a pedir ao IEAv é o firmware ACC de16 B e os builds realmente instalados; isso muda quais mocks devemos implementar depois.
