# Etapa física posterior

Ainda não há firmware ESP32 nesta entrega. Primeiro validar o parser e o contrato no PC.

Primeiro alvo: saída de53 B via USB serial da placa, se disponível, em regime100 Hz, com sinais sintéticos. Depois, um emulador de subsistema por vez. São contratos diferentes: IFOG TI (requisição4 B; resposta4/6 B), ACC esperado pelo gateway (requisição4 B; resposta16 B) e ad24bit (stream24 B).

Antes de selecionar GPIOs: identificar a placa ESP32 exata, quais UARTs/USB estão livres, níveis elétricos e o transceiver. Não conectar UART lógica diretamente a par diferencial ou a pinos de alimentação do DB9.

O artigo H745 não define o protocolo dessa geração. Nenhum sketch deve fingir compatibilidade com ela sem novo contrato.
