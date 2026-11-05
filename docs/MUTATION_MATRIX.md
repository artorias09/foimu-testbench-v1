# Matriz de mutação do counter8

Comando: `python -m tools.counter_mutants`. Para cada variante, o executor verifica
o teste original em uma cópia isolada, edita apenas aquela cópia e exige falha de
asserção. Erro de importação, sintaxe ou ambiente invalida o ensaio.

| Mutante | Risco | Teste que detectou | Resultado |
|---|---|---|---|
| M01 corte <127 | Perde lacuna de 126 posições | test_pairs | killed |
| M02 corte <129 | Atribui lacuna a delta 128 | test_pairs | killed |
| M03 sem módulo | Erro em volta 255 para 0 | test_pairs | killed |
| M04 rollover gera ambiguidade | Alarme espúrio | test_pairs | killed |
| M05 soma delta | Uma posição candidata a mais | test_pairs | killed |
| M06 nunca confirma | Permanece em reaquisição | test_arbitrary_jump_and_reorder | killed |
| M07 confirma imediatamente | Aceita referência sem progressão | test_arbitrary_jump_and_reorder | killed |
| M08 conserva referência na troca de época | Compara sessões distintas | test_epoch_reset | killed |
| M09 apresentação conserva âncora pela regra antiga | Painel diverge da aquisição | test_view_diagnostic_equivalence | killed |
| M10 classifica perda de 256 como observável | Confiança indevida no detector | test_alias_256 | killed |

Escopo: dez mutantes curados do contador. Os mutantes das demais partes do projeto
pertencem a gates separados.
