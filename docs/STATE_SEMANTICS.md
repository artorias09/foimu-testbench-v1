# Observabilidade por detector

Uma entrada de observability.CLAIMS relaciona condição, detector, status, razão,
premissas, limite e teste. Os status se referem exclusivamente ao par condição/detector.

| Condição | Detector | Status | Premissas | Limite / razão |
|---|---|---|---|---|
| Lacuna modular candidata | counter8 | observable | Referência travada, mesma época, hipótese de progressão ordenada | 2 ≤ delta ≤ 127. Estimativa de 1 a 126 posições. MODULAR_FORWARD_GAP |
| Perda de múltiplo de 256 | counter8 | not_observable | Mesma época, somente counter | Adicionar k voltas completas deixa o par de bytes idêntico. COUNTER8_ALIASING |
| Causa de salto ambíguo | counter8 | not_observable | Mesma época, somente counter | Para delta ≥ 128 a observação do salto sustenta várias explicações. MULTIPLE_COMPATIBLE_CAUSES |
| Intervalo longo de recepção | host_receive_timing | warning_only | Timeline preservada, mesma época, limiar calibrado e buffering limitado para interpretar o transporte | O watchdog mede silêncio frente ao limiar nominal. HOST_INTERVAL_ONLY |

Um valor repetido é observável, mas sua origem física é desconhecida. Um salto ambíguo é
observado; a atribuição de causa é inconclusiva. O intervalo do host pode acrescentar um
aviso mesmo se o par de counters progrediu de uma unidade. A medida sozinha não estima
o número de amostras perdidas. A calibração para a FO-IMU real está pendente.
