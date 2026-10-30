# Resultado FO-IMU testbench

Modo: virtual_deterministic; versão 0.1.0; contrato gateway53-fletcher16-le-v1.

| Métrica | Valor |
|---|---:|
| packets_expected | 1001 |
| packets_received | 901 |
| packets_lost | 100 |
| checksum_errors | 101 |
| framing_errors | 100 |
| counter_discontinuities | 100 |
| duplicates | 0 |
| resync_events | 100 |
| reconnections | 0 |
| stream_timeouts | 0 |
| jitter_max_s | 0.01000000000000135 |
| largest_gap_without_valid_data_s | 0.02000000000000135 |
| buffer_peak_bytes | 73 |

Perdas são lacunas candidatas do contador; timeouts por sensor e latência física não são observáveis.
Tempo virtual/acelerado não comprova duração real, ausência de memory leak ou timing do hardware.
JSON contém estatísticas por canal, temperaturas por slot, configuração, hashes e oráculo separado.
