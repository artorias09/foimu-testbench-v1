# Especificação do testbench — interface primeiro

Versão inicial de projeto: 0.1.0. Contrato: `gateway53-fletcher16-le-v1`.

## Objetivo e limite de equivalência

O parser receberá apenas bytes e tempo de recepção, venha de TCP localhost, arquivo ou COM. O simulador conhece os sinais e as falhas aplicadas, mas não passa essas respostas prontas para o parser. A comparação usa um oráculo separado, assim como aplicar uma tensão conhecida no seu ADC e comparar o resultado medido com a referência.

Compatibilidade significa mesmos campos, tamanhos, ordem, endianess e checksum. Não significa reproduzir temporização elétrica, aquisição física, boot, concorrência interna ou todas as falhas do gateway real. Essas camadas serão acrescentadas separadamente. Não haverá “campo extra secreto” no pacote externo para melhorar artificialmente o diagnóstico.

## Estrutura e fronteiras

| Diretório/módulo | Responsabilidade |
|---|---|
| docs | auditoria, contratos, limitações, oráculos e resultados |
| protocol | serialização e parser incremental dos 53 B; outros contratos isolados futuramente |
| simulator | sinais e cronograma sintético; emissão de bytes |
| fault_injection | transformação configurável de valores, bytes e eventos |
| acquisition | transporte e captura; não interpreta valores de sensores |
| diagnostics | contador, estatísticas incrementais, qualidade, tempo e relatório |
| replay | bytes gravados e tempo de recepção; nunca apenas valores reempacotados |
| configs | JSON, seed e identificação do perfil |
| tests | vetores independentes, oráculos e regressão |
| esp32_emulator | especificação posterior; não gravar firmware antes de validar software |
| logs | saídas por execução, ignoradas como fonte do projeto |

Implementação inicial em Python, biblioteca padrão, sem Docker. Python 3.11 ou superior. Serial físico será adaptador opcional com dependência fixa; core, TCP e testes não dependem de PyVISA/Qt/numpy. Configuração validada; chaves desconhecidas devem ser recusadas para que um erro de digitação não desative silenciosamente uma falha.

## Perfis de protocolo

| Perfil | Uso | Situação |
|---|---|---|
| gateway53-fletcher16-le-v1 | host ↔ saída simulada do gateway | implementar na Fase 1 |
| ifog-ti-request-be-v1 | gateway ↔ IFOG TI | especificado na auditoria; futuro mock |
| acc16-request-le-v1 | gateway ↔ ACC que ele espera | contrato inferido do consumidor; produtor real precisa ser fornecido |
| ad24bit24-stream-le-v1 | teste independente da aquisição ADS1256 | contrato separado, sem checksum; futuro mock |
| ifog-h745-unknown | geração do artigo | não implementável fielmente sem firmware/protocolo |

A versão de protocolo é registrada no log de controle; não é adicionada ao frame legado de 53 bytes.

## Sinais determinísticos da Fase 1

Tempo de modelo `t = índice / rate_hz`. Perfis produzem valores já nas unidades do pacote externo:

- IFOG X = `100*sin(2π*0.2*t)` deg/h.
- IFOG Y = `25` deg/h.
- IFOG Z = rampa periódica `10*(t % 20)` deg/h.
- ACC X/Y = 0, ACC Z = 2048 counts, tap =1024 counts. Não converter counts para g sem calibração.
- Temperatura = `25 + slot*0.5 + 0.001*t` °C, slot `(counter-1)%8` no perfil do firmware.
- MEMS gyro = IFOG/3600, em deg/s; MEMS ACC = `[0,0,9.81]` m/s². É correlação sintética definida pelo teste, não prova de calibração real.

O float32 quantiza os valores; tolerâncias dos testes consideram essa quantização. Não usar igualdade bit a bit entre seno calculado por bibliotecas matemáticas distintas como requisito metrológico.

## Canal virtual e relógios

1. Modo determinístico: stream incremental em memória, fragmentação configurável e relógio virtual. Útil para milhões de pacotes, falhas e métricas exatas. Não mede jitter do Windows.
2. Modo TCP: simulador e aquisição em processos independentes no localhost, com relógio real monotônico. TCP não preserva fronteiras de pacotes; a aquisição deve lidar com qualquer fragmentação ou agrupamento. TCP entrega em ordem dentro de uma conexão: desordem de frames é aplicada antes de enviar.
3. Adaptador COM: mesma interface de leitura de bytes; depende de USB/serial e, para dois programas locais, de driver de portas virtuais. Necessário para reutilizar sem mudanças um host que exige VISA/COM.

Registrar separadamente `model_time`, emissão planejada, escrita no transporte e recepção do host quando disponíveis. Timestamp do host não é timestamp de medição física. Não atribuir ao pacote real a latência que só conhecemos por controle do simulador.

## Métricas e significado correto

| Métrica | Definição | Limite |
|---|---|---|
| packets_expected | quantidade planejada no ensaio controlado | no host real é desconhecida sem duração/referência; não inventar |
| packets_received | frames aceitos com header e Fletcher válidos | contar duplicados separadamente |
| packets_lost | lacunas inferidas por counter em sequência plausível | inclui rejeitados; não é prova de perda elétrica; pode ser limite inferior |
| packets_lost_truth | retirados pelo gerador de falhas | só no oráculo de simulação, separado do diagnóstico observado |
| checksum_errors | candidatos de 53 B com header correto e checksum inválido | não é número universal de bytes/frames fisicamente corrompidos |
| framing_errors | episódios de descarte para recuperar framing, incluindo final incompleto | não confundir com “um erro por byte” |
| counter_discontinuities | transições que não são avanço unitário, incluindo repetição | não somar uma duplicata como 255 perdas |
| duplicates | contador repetido consecutivo | no legado pode ser aquisição travada, frame repetido ou perda de 256 ciclos |
| out_of_order_or_reset | avanço modular grande, ambíguo | não decidir reset versus ordem apenas por uint8 |
| resync_events | recuperação válida após descarte/candidato inválido | a inicialização limpa não conta como recuperação |
| timeouts por sensor | null se não observável no frame | suspeitas de sentinelas e congelamento são campos diferentes |
| stream_timeouts | episódio sem bytes por limiar configurado | TCP/COM pode estar aberto; contar só uma vez até retornar |
| reconnections | nova conexão bem-sucedida depois da primeira | não confundir reconectar transporte com sincronizar parser |
| período médio / std | diferença entre timestamps de frames aceitos; Welford, std populacional | em TCP vários frames podem compartilhar timestamp de um read |
| jitter máximo | `max(abs(dt - 1/rate_hz))` | inclui gaps; publicar também quantidade de intervalos |
| latência média/máxima | só com instantes comparáveis e associação inequívoca | no wire legado: null; idade física desconhecida |
| maior intervalo sem dados | máximo entre chegadas de frames válidos, incluindo cauda até fim da captura | “sem dados válidos”, não ausência de bytes |
| estatísticas por sensor | n finito, média, std, mínimo/máximo, não finitos, limites sintéticos e repetições | sinal constante não comprova sensor congelado |

Counter8 volta em **2,56 s a 100 Hz**. Lacunas de 256 podem parecer zero; desordem/reset também são ambíguos. A política inicial considera delta modular de 2…127 como lacuna candidata, delta≥128 como ordem/reset ambíguo, delta0 como repetição. A âncora não deve andar para trás diante de pacote atrasado. Essa política é conservadora, documentada e parametrizável futuramente. Perdas antes do primeiro frame e depois do último não são observáveis só por counter.

Cada temperatura mantém estatística própria de slot e contador de atualizações; nunca preencher silenciosamente “leitura nova” com o último valor. IFOG X/Y/Z individualizados; ACC e MEMS por canal; resumos por grupo derivados desses canais. Valores de erro embutidos são preservados crus e marcados como suspeitos, sem exclusão oculta das estatísticas.

## Falhas e oráculos a implementar em etapas

Todas as falhas devem ter `enabled`, período/faixa/índices ou probabilidade + seed. Mutar valor antes do checksum cria um dado semanticamente inválido com frame íntegro; mutar byte depois do checksum cria erro de transporte. Não são a mesma falha.

| Injeção | Resultado correto esperado | Observabilidade / etapa |
|---|---|---|
| remover frame counter100, fluxo 99→101 | lacuna+1, descontinuidade+1, parser continua; próximo frame aceito | Fase1 básica |
| pular counter sem retirar frame | descontinuidade/lacuna candidata; truth distingue salto de perda real | Fase2 |
| XOR 1 bit no checksum a cada N | cada candidato selecionado rejeitado, próximos aceitos, erros exatos no ensaio controlado | Fase1 básica |
| XOR 1 bit no payload após checksum | rejeição por Fletcher, resync sem encerrar | Fase1 básica |
| truncar um frame | fragmento não aceito; próximo completo recupera; residual final marcado | Fase1 básica |
| header inválido | framing_error; checksum não tem obrigação de contar o frame sem header | Fase1 básica |
| congelar IFOG X com checksum recalculado | n de X mantém, repetições aumentam; Y/Z continuam no modelo; não chamar repetição de timeout | Fase2 |
| sensor sem resposta | mock do sensor fica silencioso; baseline G pode bloquear em ACC; proposta deve isolar falha | Fase2 + modelo de gateway; em Fase1 externa não existe uma UART por sensor |
| timeout do sensor | scheduler excede prazo e produz comportamento do perfil original ou corrigido | Fase2/modelo; host externo só vê efeito e possível sentinela |
| jitter alternado ±1 ms na entrega | intervalos alternam 8/12 ms em período10; std2 ms e jitter máx2 ms | Fase1 básica em relógio virtual |
| atraso crescente | atraso conhecido no oráculo cresce; host vê deriva no período, não latência física absoluta | Fase2 |
| pausa de comunicação | 1 episódio de stream_timeout; retorno retoma parser; loss depende de descartar ou reter frames | Fase2 TCP |
| desconectar/reconectar | reconnections+1, descarte do fragmento antigo; iniciar nova época de counter | Fase1 TCP básico |
| burst | frames válidos no mesmo chunk aceitos; períodos host podem ser zero; memória limitada | Fase1 básica |
| NaN/Inf em campo float | checksum válido, n_nonfinite+1, estatísticas finitas não contaminadas | Fase1 teste de codec/diagnóstico; injeção configurável depois |
| fora de faixa | dado preservado; limite de engenharia configurado sinaliza; não transformar limite sintético em especificação real | Fase2 configurável |
| ordem 10,12,11,13 | 11 identificado como atraso/ambiguidade; âncora não retrocede; não alegar perda definitiva sem janela de reordenação | Fase2 |
| alteração 00↔FF que colide no Fletcher | demonstrar que checksum pode aceitar corrupção; teste passa quando reconhece limitação | Fase1 teste unitário |
| cache misto com checksum válido | parser aceita; só oracle temporal/modelo identifica erro de idade; evidenciar limite do protocolo | Fase2/modelo |

Fletcher-16 **não detecta qualquer corrupção possível**. O teste “todos detectados” vale para o padrão de injeção escolhido (ex.: inverter um bit do checksum). Não vale para qualquer padrão adversarial ou troca de bytes. Header também não é protegido. Se o payload contiver `A0 A0`, o parser pode examinar candidatos falsos; contagem de candidatos inválidos não equivale ao total de frames danificados.

## Testes e critérios quantitativos provisórios

| Teste / critério | Oráculo | Origem |
|---|---|---|
| estrutura | exatamente53 B, offsets corretos, endian LE, Fletcher sobre49 B | derivado do G |
| normal1M | 1.000.000 emitidos e aceitos; 0 checksum/framing/lacuna/duplicata; buffer final vazio | proposta de aceitação software |
| checksum | 1 bit inválido a cada N; rejeições igual quantidade injetada em vetor sem headers acidentais; nenhum inválido entregue | proposta de teste |
| fragmentação | testar todas as 52 fronteiras de corte e byte a byte; mesmos valores do vetor | proposta de teste |
| recuperação | após frame truncado/corrompido, próximo frame íntegro conhecido aceito; no máximo uma janela de frame se não houver falso header com checksum coincidente | proposta condicionada ao cenário |
| sensor failure | desligar mock de um sensor não encerra aquisição dos outros no perfil proposto | proposta; baseline original pode falhar |
| jitter determinístico | erro numérico <1 ns nas estatísticas de tempo virtual do cenário ±1 ms | proposta de software; não exigência do Windows |
| TCP | duas aplicações recebem todos os frames normais e recuperam transporte de forma controlada | teste de integração; não comprova serial física |
| longa duração | 8 h reais a100 Hz; todos resultados comparados com truth; memória após aquecimento sem crescimento persistente | proposta; executar posteriormente na máquina dedicada |
| memória | medir tracemalloc e RSS em pontos periódicos; buffers limitados; investigar crescimento >10 MiB em 8 h, excluindo caches explicados | limiar inicial proposto, não requisito aeroespacial |
| disco | 53×100×3600 =19,08 MB/h só de bytes; 8 h=152,64 MB + CSV/timestamps | derivado do formato/taxa; orçamento de armazenamento |
| desempenho do host | reportar picos, tempo de CPU, disco, perfil e máquina; limites de jitter real a combinar | precisa definir com IEAv |
| atrasos físicos toleráveis | não definidos | precisa definir com IEAv |

Não afirmar “sem memory leak” por um teste curto. Um milhão de frames acelerados equivale em conteúdo a 2 h46 min40 s a100 Hz, **mas não é um ensaio de duração real de 2 h46 min40 s**.

## Logs, replay e relatórios

Cada execução terá configuração resolvida, seed, versão do simulador, hash do código/contrato, Python/OS, horário UTC, escala de tempo, canal e limites de inferência. Bytes crus `.bin` são a evidência; CSV contém apenas frames aceitos e campos de qualidade. Captura temporal registra offsets/tamanhos dos blocos recebidos e timestamps monotônicos em `.jsonl`, incluindo desconexão quando suportada. Métricas agregadas em JSON; resumo legível gerado desse JSON.

Replay de `.bin` preserva bytes, fragmentação artificial e ordem, mas não recupera intervalos originais perdidos. Replay com sidecar de chunks preserva agrupamento/intervalos observados no host; não recria o instante físico de conversão. CSV antigo sem bytes não preserva checksum original, corrupção, endianess efetivamente recebida nem framing. Qualquer reconstrução a partir dele deve ser rotulada “replay de valores”, nunca captura fiel.

## Regressão A/B

Fixar dataset/captura, seed, configuração, carga, política temporal e critérios. Salvar `baseline_A.json` e `candidate_B.json` com hashes distintos. Comparar perdas observadas e truth, rejeições, recuperações, tempo, CPU/memória e coerência dos dados. Ganho só existe se a métrica melhora sem violar as demais condições. Comparar arquivos de duas simulações iguais não demonstra melhora de firmware.

O primeiro baseline cobre codec/host. Para firmware: extrair funções originais em harness de HAL fake mantendo trechos originais rastreáveis, ou rodar A e B no mesmo hardware com estímulos gravados. Não reescrever o original antes de reproduzir a falha. Depois, uma mudança por vez: timeout global ACC, limpeza limitada sem strlen, validade, snapshot de transmissão e TX não bloqueante.

## Critérios de passagem para ESP32 e HIL

- Codec comprovado por vetor independente e suíte de parser; logs reproduzíveis disponíveis.
- Confirmar placa ESP32 e transporte USB; não assumir todos os modelos possuem três UARTs ou mesmo USB.
- Emular saída externa primeiro; frequências de100 Hz são metas de interface, não hard-real-time óptico.
- Para gateway real, confirmar pinout/transceiver/versão antes da ligação. Emular um subsistema por vez.
- ACKs, headers ou timestamps novos não podem ser inseridos no perfil legado; futuras extensões precisam de versão distinta.
- Não prometer simular três IFOGs independentes, ACC e MEMS simultaneamente numa única ESP32 sem validar recursos, multiplexação e tempo de resposta.

