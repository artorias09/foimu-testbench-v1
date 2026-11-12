# Counter8, política counter8-reacquire-v1

A máquina recebe exclusivamente counters de frames aceitos na ordem de recepção. Cada
declaração explícita de época reinicializa a máquina. A camada de apresentação também
reinicializa ao encontrar um frame de outra época.

| Estado anterior | Evidência | Observação | Próximo estado |
|---|---|---|---|
| Sem referência | Primeiro counter c | Inicial | Travado em c |
| Travado em p | d = (c-p) mod 256 igual a 1 | Contíguo | Travado em c |
| Travado em p | d = 0 | Mesmo valor repetido | Travado em c |
| Travado em p | 2 ≤ d ≤ 127 | Lacuna candidata de d-1 | Travado em c |
| Travado em p | 128 ≤ d ≤ 255 | Um salto ambíguo, causa inconclusiva | Em reaquisição, provisório c |
| Em reaquisição com provisório p | d = 1 | Referência readquirida, inclusive 255 para 0 | Travado em c |
| Em reaquisição com provisório p | d diferente de 1 | Evidência insuficiente | Em reaquisição, provisório c |

Durante a reaquisição cada frame substitui o provisório. Uma sequência sem progressão
unitária pode ficar indefinidamente nesse estado, com um único alerta de abertura.
Suspender a contagem nesse intervalo evita extrapolar a partir de uma âncora incerta,
ao custo de deixar lacunas candidatas sem estimativa. Reiniciar a época encerra o
episódio anterior. No caso 10,11,12,11,13 o último valor é provisório; um 14 confirma.
O primeiro passo só escolhe uma referência local. Uma progressão 200,201 basta para
voltar a comparar valores adjacentes sem afirmar que houve reset ou que 200 era correto.

Em estado travado, packets_lost soma apenas lacunas candidatas. O cenário legado
forward_delta_lt128_v1 identifica o corte para lacunas. A regra de reaquisição recebe
sua própria versão. out_of_order_or_reset e counter_ambiguous_jumps contam episódios
ambíguos abertos. counter_discontinuities conta aberturas, repetições e gaps enquanto
travado. counter_reacquisitions conta confirmações por progressão unitária.
