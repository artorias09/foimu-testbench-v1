# P2: validação executada e limites

## Identificação

Branch: `feature/v02-p2-backend`, criada de `origin/main` em
`d23f4eab71276e082eca604022a443205a92cb24` (merge da P1).
Baseline v0.1.0 congelada: `52531eaa16bb111cdb6ad862c8fd037d6ead0977`.

A evidência final abaixo identifica o commit executável, antes do commit que
acrescenta esta documentação. Não se atribui a um commit posterior um ensaio que
não foi executado nele. Código, testes e configuração não foram modificados
durante o gate final. A documentação final não altera esses artefatos.

## Resultado final executado

Execução em 2026-10-30, Python `3.12.14`,
`Linux-6.18.57-x86_64-with-glibc2.39`, arquitetura `x86_64`.
Commit do gate: `0d4a77b1fe84e71695e87fca29ff8322b0f4681c`, árvore limpa (`dirty=false`).
O identificador de versão de aplicativo continua 0.1.0; o commit identifica este
incremento P2 de desenvolvimento, sem tag de release v0.2.

| Verificação | Resultado |
|---|---|
| Suíte completa | 107 testes, todos passaram |
| Legado normal | 1.000.000 pacotes, zero perdas inferidas/checksum/framing |
| Buffer parser legado no milhão | 53 bytes de pico |
| Normal v2 | 6000 oportunidades a 100 Hz nominal virtual, 6000 frames |
| Erros normal v2 | Zero lacunas candidatas, checksum e framing |
| Wire normal v2 | 318000 bytes |
| Volume total da Run normal | 17789308 bytes, incluindo ledger, índices e checkpoints |
| Reabertura | Manifesto, hashes, timeline e relatório válidos |
| Replay v2 | Wire idêntico e todas as métricas iguais à origem |
| Checksum v2 | 1001 oportunidades; 901 frames aceitos; 101 candidatos checksum inválidos; critério passou |
| Writer lento | 200 frames preservados; RX avançou durante bloqueio; filas drenadas |
| Writer sobrecarregado | Limite de 1000 bytes, Overload explícito, failed/partial |
| Morte do backend | Processo interrompido na terceira escrita; interrupted_recovered; prefixo confirmado de 106 bytes |
| Golden | decode/encode idênticos aos 53 bytes independentes |

O cenário de corrupção produz 101 candidatos inválidos para 100 mutações. Headers
candidatos encontrados durante ressincronização explicam a diferença; o oráculo
não força igualdade entre mutações e candidatos. O ensaio de perda final separado
mostra truth dropped=1 e zero lacunas observáveis por counter sem sucessor.

Tempos de parede medidos nesta execução:

| Etapa | Segundos |
|---|---:|
| Ferramenta de aceitação legada, incluindo suíte | 57.337 |
| Run virtual v2 normal | 40.592 |
| Replay v2, incluindo verificações | 89.752 |
| Gate P2 completo | 223.895 |

Esses tempos são custos observados neste host, sem metas de aceitação temporal.
O nominal virtual representa 60 s de ensaio, independentemente do tempo de parede.
O gate usa barreiras explícitas e registra `throughput_claim=false`; não mede
capacidade sustentada, latência física ou desempenho do hardware FO-IMU.

Resumo original do gate: `p2-acceptance-release/summary.json`, SHA-256
`91dfa44664d62841a8de544c1845d68069a21bb4016f79e8cb20d9a3e1e234f4`.
Os números acima foram transcritos desse artefato; diretórios de logs não são
versionados no repositório. Os comandos documentados regeneram as evidências.

Depois do gate, o teste de timeline foi reforçado com um fim em 0 ns após dados
posteriores, além do caso de tempo negativo. Os nove testes de storage foram
reexecutados e passaram. Essa alteração é exclusivamente de teste e não modifica
o runtime validado pelo gate; não houve repetição desnecessária do milhão.


## Comandos reproduzíveis

Na raiz do repositório, escolha diretórios de saída novos:

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m tools.acceptance --out logs/aceitacao_legada
py -3 -m tools.acceptance_p2 --out logs/aceitacao_p2
```

O gate P2 chama `tools.acceptance` como subprocesso, que descobre a suíte inteira
e executa o milhão legado. Portanto, essa execução cobre os três comandos sem
repetir desnecessariamente a mesma carga. O gate P2 verifica explicitamente a
quantidade mínima de testes, os oráculos legados e cada etapa v2; suas condições
não dependem de `assert` removível por `python -O`. Isso não altera o comportamento
da ferramenta legada quando executada isoladamente.

Também foi executada a suíte direcionada antes do gate:

```text
python -m unittest discover -s tests -p 'test_p2*.py' -q
43 testes, OK
```

## Matriz de cobertura da tarefa

Os nomes abaixo são métodos de teste. Os arquivos ficam em `tests/`.

| Item | Evidência | Oráculo principal |
|---|---|---|
| 1. Run normal | `test_p2_backend.py::test_normal_reopens_hashes_and_drains_without_deadlock` e gate de 6000 | Quantidade correta; completed/passed/complete; reabertura válida |
| 2. Truth separado | `test_truth_removed_same_observed` | Remover ledger não altera wire, chunks, frames ou métricas |
| 3. Writer lento | `test_writer_slow_does_not_directly_block_rx` | RX avança enquanto writer espera Event; liberação permite dreno sem perda |
| 4. Fila cheia | `test_writer_queue_full_explicit_partial_and_no_deadlock`, `test_rx_queue_full_explicit_partial` | Overload explícito, failed/partial; pico dentro do limite |
| 5. Writer morto | `test_writer_dead_and_disk_full` | SystemExit do worker não vira completed; erro estruturado |
| 6. Disco cheio | Mesmo teste e `test_p2_storage.py::test_failure_between_wire_and_index_preserves_unindexed_tail` | ENOSPC antes/depois do wire; cauda sem índice preservada e não íntegra |
| 7. Stop normal | `test_stop_idempotent_and_drained` | cancelled/complete; chunk em andamento salvo; motivo preservado |
| 8. Stop duplicado | Mesmo teste | ACK original, indicação duplicate e somente um stop_ack persistido |
| 9. Backend morto | `test_p2_storage.py::test_full_controller_killed_inside_writer` | Processo termina com código 19 dentro do writer; 106 bytes confirmados |
| 10. Reabertura interrompida | `test_checkpoint_preserves_tail_and_never_recovers_completed` e gate | interrupted_recovered; origem byte a byte intocada |
| 11. Zero dados | `test_zero_data_never_implicit_pass` | Sem critério: not_evaluated; exigência de recepção: failed |
| 12. Lixo contínuo | `test_garbage_and_silence_have_distinct_watchdogs` | Silêncio de frame válido, sem silêncio de bytes |
| 13. Silêncio total | Mesmo teste; `test_p2_evidence.py::test_watchdogs_garbage_and_total_silence` | Dois watchdogs e atraso de detecção conhecido |
| 14. Byte span | `test_frame_spans_and_refs`, `test_epoch_discard_retains_byte_origin_and_detection_time` | Intervalos exatos [início,fim), refs e época dos bytes |
| 15. Equivalência parser | `test_located_parser_exact_legacy_equivalence` | Mesmos Packets reencodificados e mesmas estatísticas, fragmentos de 1 a 53, 4096 e 65536 B |
| 16. Checksum | `test_corruption_and_unobservable_final_drop` e gate | Aceitos e candidatos inválidos iguais ao oráculo, sem confundir candidatos com falhas injetadas |
| 17. Drop final | Mesmo teste | Truth dropped=1, observed frames=9 e lacuna por counter=0 |
| 18. Regressão temporal | `test_p2_storage.py::test_timeline_validated_even_without_manifest_trust` | Timeline inválida recusada independentemente do manifesto |
| 19. Configuração de origem | `test_replay_source_config_and_explicit_override` | Replay fiel reproduz todas as métricas e bytes |
| 20. Override | Mesmo teste | Run filha; diferença 50→100 Hz registrada; jitter reanalisado em 0,01 s |
| 21. Fonte alterada | `test_initial_identity_preserved_and_source_change_recorded` | Identidade inicial preservada; final diferente; sources_changed=true |
| 22. Backlog limitado | `test_bounded_queue_exact_limit_rejection_no_eviction` | Dois itens de 5 B ocupam limite de 10 B; terceiro recusado |
| 23. Sem descarte silencioso | Mesmo teste, testes de overload e ENOSPC | Itens existentes não expulsos; falha/integridade parcial explícita |
| 24. Shutdown com dreno | Testes normal, Stop e writer lento | Pendências zero e nenhum worker vivo ao finalizar normalmente |
| 25. Sem deadlock normal | Teste normal e aceitação | Pipeline termina e Run reabre; não é prova de todas as interleavings possíveis |

Testes adicionais cobrem snapshots contra mutação, envelope imutável, composição
legacy_v1/RNG, NaN/Inf em JSON sem perder wire, ações ordenadas/não alcançadas,
watchdog de worker com relógio mock, CLI v1 importada, configuração inválida,
recusa de sobrescrita, unidades incompatíveis e ausência de truth na avaliação.

Testes de recovery cobrem ainda journal truncado, estrutura inválida de checkpoint,
tipos estritos, adulteração de artefatos e escrita parcial entre bytes e índice.
O replay multiépoca confirma que o descarte de um frame parcial pertence à época
anterior, apesar de ser detectado quando a nova conexão é declarada.

## Regressão e preservação

Os 64 testes anteriores foram preservados: 33 da v0.1.0 e 31 da P1. Os 43 testes
P2 são adicionais. Não houve exclusão ou alteração de testes antigos para fazer a
suíte passar. B01 e B02 têm testes novos que caracterizam separadamente o caminho
legado: ingest escreve e processa na thread chamadora; metadados surgem no finish.

`protocol/gateway53.py`, `acquisition/__init__.py`, `config.py`,
`diagnostics/__init__.py`, `fault_injection/__init__.py`, `runners.py`,
`simulator/__init__.py`, fixtures C/binário/JSON, configurações v1 e
`tools/acceptance.py` permanecem idênticos ao ponto de partida desta fase.
O golden de 53 bytes continua com SHA-256:
`6b501065bb1db9a60ba51def38ffb3b43c6b9c47957c1a66d5777912f689c80b`.

Não foi detectada regressão no escopo dos testes executados. Isso não equivale a
compatibilidade comprovada com todo consumidor externo. Novos campos aditivos de
Run v2 são lidos pelo leitor P2; o leitor estrito P1 pode rejeitá-los. Os arquivos
v1 e seu caminho de execução continuam disponíveis.

## Problemas encontrados e tratados nesta etapa

| Problema | Evidência/decisão | Resultado |
|---|---|---|
| stop_reason apagado por transição sem motivo | Teste dedicado P2 antes do backend | None conserva motivo; substituição explícita permanece possível |
| Frozen superficial permite listas/dicts mutáveis | Teste altera Scenario após criar controlador | Snapshot JSON e envelopes bytes/tuplas nas fronteiras |
| Writer lento e pipeline v1 síncrono | Caracterização B01; bloqueio controlado do writer | Três workers e filas limitadas, sem alegação de throughput com barreiras |
| Falha na finalização podia expor completed antes do commit | Injeção de ENOSPC na confirmação final | Candidato terminal privado; estado público finalizing até run.json; fallback failed/partial |
| Verificação só do append não cobre tamanho total | Orçamento de 50000 bytes com execução maior | Verificação total por checkpoint e na finalização; limite soft documentado |
| Checkpoint JSON válido com estrutura inválida | Caudas escalares, artifacts errado, versão bool | Recusa cauda; conserva último prefixo estruturalmente válido |
| Descarte na reconexão recebia época nova | Fragmento de 10 B na época 0 descartado ao declarar época 1 | Span/refs/epoch da origem; tempo de detecção da nova leitura |
| Campos NaN/Inf não cabem em JSON estrito | Frame sintético com NaN e Inf | Wire intacto, null acompanhado por numeric_status |

O detalhamento de decisões e a classificação individual B01–B14 estão em
[P2_BACKEND.md](P2_BACKEND.md). O plano original não foi reescrito.

## Arquivos lidos e escopo da revisão

Foram lidos integralmente README.md, pyproject.toml, docs/PLANO_V02.md,
docs/P1_CONTRATOS.md, docs/P1_VALIDACAO.md, docs/AUDITORIA_FASE_0.md,
docs/ESPECIFICACAO_TESTBENCH.md, docs/VALIDACAO.md, docs/EVIDENCIAS.md,
docs/source_manifest.json, o código Python de foimu_testbench/, testes existentes,
configs e tools/acceptance.py. Também foram examinados histórico e árvore Git.
A revisão P2 usa a auditoria já documentada; não reinterpreta a física dos sensores.

Os 522 arquivos originais disponíveis foram conferidos contra source_manifest.json
sem divergências. Nenhum firmware, PCB ou documento original IEAv foi alterado.

## Inventário de alterações

Criados:

- `foimu_testbench/backend.py`, `evidence.py`, `processing.py`, `emission.py`.
- `foimu_testbench/storage.py`, `validation.py`, `reporting.py`, `replay.py`, `cli_v2.py`.
- `tests/test_p2_contracts.py`, `test_p2_evidence.py`, `test_p2_backend.py`,
  `test_p2_storage.py`, `test_p2_cli.py`, `test_p2_legacy_characterization.py`.
- `configs/v2/normal.json`, `tools/acceptance_p2.py`.
- `docs/P2_BACKEND.md`, `docs/P2_VALIDACAO.md`.

Modificados:

- `foimu_testbench/core/contracts.py`: motivo preservado e campos de identidade final,
  catálogo, operação e limitações necessários ao ciclo v2.
- `foimu_testbench/provenance.py`: coleta inclui ferramentas relevantes sob tools/.
- `foimu_testbench/__main__.py`: despacho aditivo dos três comandos v2.
- `README.md`: entrada para os comandos e documentação P2; instruções v1 conservadas.

Nenhuma dependência adicionada. pyproject.toml e requirements.txt não mudaram.

## Limites e validações pendentes

Não foram executados Windows, serial, ESP32, Raspberry, HIL, STM32, hardware IEAv,
queda elétrica real, oito horas reais ou caracterização prolongada de RSS/CPU.
Nenhum requisito físico, de voo ou de navegação foi introduzido.

O executor v2 aceita virtual e replay. TCP continua no caminho v1. Não há GUI, IPC
para GUI, A/B completo, parameter sweep, scripting, Allan variance ou modelos L2/L3.

Filas limitam bytes serializados e itens, não memória total. max_memory_bytes é
recusado. Orçamento de disco é gatilho de parada, não quota rígida; diagnóstico de
emergência pode excedê-lo. Checkpoints por lote não prometem limite temporal de
perda. Hashes de checkpoint implicam custo de I/O que cresce com captura, e o
leitor mantém posições de checkpoints em memória na inspeção offline.

Thread bloqueada em I/O do kernel não pode ser cancelada com segurança; saída
aborted/partial explicita workers vivos. O processo CLI pode encerrar, mas a P2
não oferece isolamento por processo para cada worker. Um disco totalmente
indisponível pode impedir até a gravação da falha; API ainda retorna falha, e o
leitor usa os metadados/prefixos disponíveis sem inventar conclusão.

Identidades inicial/final detectam mudanças persistentes entre coletas; não
congelam fontes nem detectam edição e reversão transitórias. Timestamps de recepção
continuam sem relação demonstrada com amostragem física. Truth sintético não
valida erro físico do sensor, sincronismo ou revisão instalada no IEAv.

A etapa termina na P2. P3 e GUI não foram iniciadas.


## Correção posterior: orçamento independente de shutdown (2026-10-30)

O gate original acima permanece histórico. Antes da correção, o novo teste
`test_p2_shutdown.py` reproduziu deterministicamente RX=1 s de orçamento,
processamento=0,1 s e writer=0, com aborted/partial. Essa caracterização foi
registrada no commit 4f0a10b. O teste foi então atualizado para a semântica corrigida:
RX e processamento consomem 0,9 s cada, writer recebe seu próprio 1 s e drena em
0,5 s, terminando cancelled/complete após interrupção solicitada. Usa workers
simulados e relógio controlado, sem sleeps; os testes existentes continuam cobrindo
o pipeline real.

Runtime corrigido: `f80f7eb2e746566ed253653936a86b944bcd2bb9`.

- Suíte P2 direcionada: 44 testes passaram.
- Suíte completa, chamada pelo acceptance P2: 108 testes passaram, 107 preservados.
- Primeira tentativa (`p2-shutdown-acceptance`): suíte e milhão passaram; normal v2
  falhou por worker_progress nos três workers antes dos joins finais. Os atrasos
  de detecção registrados foram aproximadamente 1,23 a 1,33 s além do limiar de
  5 s. Nenhum worker ficou vivo ao final. Causa da falta de progresso não determinada;
  não foi demonstrado vínculo com a alteração dos joins.
- Repetição sem mudar código ou limites (`p2-shutdown-recheck`): gate completo
  passou, com 1 milhão legado sem erros, 6000 frames v2 sem erros, replay idêntico,
  checksum, writer lento, overload e recuperação de prefixo de 106 bytes.
- Tempo total da repetição: 251.422 s. Não representa taxa sustentada.

Comandos executados:

```text
python -m unittest discover -s tests -p test_p2_shutdown.py -v
python -m unittest discover -s tests -p 'test_p2*.py' -q
python -m tools.acceptance_p2 --out /workspace/scratch/daa2df17b73e/p2-shutdown-acceptance
python -m tools.acceptance_p2 --out /workspace/scratch/daa2df17b73e/p2-shutdown-recheck
```

O acceptance chama a suíte completa e a ferramenta legada, incluindo o milhão.
Nenhum teste anterior, protocolo ou parâmetro de watchdog foi alterado. O timeout
agora é independente por join final de RX, processamento e writer, conforme
P2_BACKEND.md; não é um limite total do execute. P3 não foi iniciada.
