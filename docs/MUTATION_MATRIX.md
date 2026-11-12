# Matriz consolidada de mutação

Execução com python -m tools.counter_mutants, python -m tools.evidence_mutants e o teste T01 da fronteira observed. Os executores exigem controle limpo e falha por asserção.

| ID | Componente | Mutação | Risco | Teste que detectou | Resultado |
|---|---|---|---|---|---|
| M01 | Counter8 | corte <127 | Perde lacuna de 126 posições | test_pairs | killed |
| M02 | Counter8 | corte <129 | Atribui lacuna a delta 128 | test_pairs | killed |
| M03 | Counter8 | sem módulo | Erro em volta 255 para 0 | test_pairs | killed |
| M04 | Counter8 | rollover gera ambiguidade | Alarme espúrio | test_pairs | killed |
| M05 | Counter8 | soma delta | Uma posição candidata a mais | test_pairs | killed |
| M06 | Counter8 | nunca confirma | Permanece em reaquisição | test_arbitrary_jump_and_reorder | killed |
| M07 | Counter8 | confirma imediatamente | Aceita referência sem progressão | test_arbitrary_jump_and_reorder | killed |
| M08 | Counter8 | conserva referência na troca de época | Compara sessões distintas | test_epoch_reset | killed |
| M09 | Counter8 | apresentação conserva âncora pela regra antiga | Painel diverge da aquisição | test_view_diagnostic_equivalence | killed |
| M10 | Counter8 | classifica perda de 256 como observável | Confiança indevida no detector | test_alias_256 | killed |
| E01 | Agregação | qualquer ok aprova | mascara falha | test_order_and_missing | killed |
| E02 | Agregação | ignorar failed | omite violação | test_order_and_missing | killed |
| E03 | Agregação | ausente vira ok | verde sem execução | test_order_and_missing | killed |
| E04 | Agregação | unknown vira ok | aprova incerteza | test_order_and_missing | killed |
| E05 | Agregação | inconclusive vira warning | minimiza ambiguidade | test_order_and_missing | killed |
| E06 | Agregação | suprimir limitações | excede escopo | test_limits_and_optional | killed |
| E07 | Agregação | aprovar sem referência | sem evidência | test_concrete_ref_required | killed |
| E08 | Agregação | ignorar integridade parcial | aceita prefixo insuficiente | test_coverage_and_integrity | killed |
| E09 | Agregação | somente nós com resultado | check omitido | test_order_and_missing | killed |
| E10 | Agregação | inverter severidade | raiz melhor que filho | test_order_and_missing | killed |
| E11 | Agregação | consultar truth | contamina observed | test_truth_independence | killed |
| E12 | Agregação | aprovar sem cobertura | verde sem janela | test_coverage_and_integrity | killed |
| E13 | Parser | descartar 53 após checksum | perde próximo header | test_truncated_then_valid | killed |
| E14 | Replay | ignorar época | mistura sessões | test_replay_preserves_epoch_boundaries_and_partial_discard | killed |
| E15 | Fila | descartar mais antigo | perda silenciosa | test_bounded_queue_exact_limit_rejection_no_eviction | killed |
| E16 | Checkpoint | confirmar antes do fsync | prefixo prematuro | test_confirm_only_after_checkpoint_fsync | killed |
| E17 | Shutdown | compartilhar deadline | aborto indevido | test_independent_budgets_allow_healthy_writer_to_drain | killed |
| T01 | Fronteira observed | somar oportunidades de truth ao checksum | concordância simulada | test_live_truth_mutant_killed_by_file_source | killed |
