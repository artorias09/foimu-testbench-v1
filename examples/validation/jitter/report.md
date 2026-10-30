# Resultado FO-IMU testbench

Modo: virtual_deterministic; versão 0.1.0; contrato gateway53-fletcher16-le-v1.

| Métrica | Valor |
|---|---:|
| packets_expected | 1001 |
| packets_received | 1001 |
| packets_lost | 0 |
| checksum_errors | 0 |
| framing_errors | 0 |
| counter_discontinuities | 0 |
| duplicates | 0 |
| resync_events | 0 |
| reconnections | 0 |
| stream_timeouts | 0 |
| jitter_max_s | 0.0019743485263057445 |
| largest_gap_without_valid_data_s | 0.011974348526305745 |
| buffer_peak_bytes | 53 |

Perdas são lacunas candidatas do contador; timeouts por sensor e latência física não são observáveis.
Tempo virtual/acelerado não comprova duração real, ausência de memory leak ou timing do hardware.
JSON contém estatísticas por canal, temperaturas por slot, configuração, hashes e oráculo separado.
