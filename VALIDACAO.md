# Validação efetivamente executada

Execução: 28/10/2026, no ambiente de desenvolvimento. Python 3.12.14; Linux-6.18.55-x86_64-with-glibc2.39.

## Resultado

- 33 testes unitários/de integração passaram.
- 1.000.000 de pacotes normais aceitos; zero perdas inferidas, erros de checksum e framing.
- Tempo de parede do ensaio normal acelerado: 21.244 s; suíte + cenários: 22.758 s.
- Maior buffer do parser no ensaio normal:53 bytes. Teste adicional usa100 kB de lixo e burst500 frames, exigindo limite de4148 bytes.
- Referência independente: GCC13.3 compilou struct packed e Fletcher copiados do fonte original; vetor53 B coincidiu integralmente com encoder Python. Checksum do vetor:0x5F54; bytes54 5F.

Hash SHA-256 do código Python testado: `267ab905a2e0132fc5062d57c52bf8c2f3c707e347322ed5efeea31f8beff25a`.

## Cenários controlados

| Cenário (1001 oportunidades) | Aceitos | Lacunas candidatas | Candidatos checksum inválido | Episódios framing | Recuperações |
|---|---:|---:|---:|---:|---:|
| checksum | 901 | 100 | 101 | 100 | 100 |
| loss | 901 | 100 | 0 | 0 | 0 |
| truncate | 901 | 100 | 101 | 100 | 100 |
| header | 901 | 100 | 1 | 100 | 100 |
| byte | 901 | 100 | 101 | 100 | 100 |
| jitter | 1001 | 0 | 0 | 0 | 0 |

Nos cenários de falha a cada10,100 frames são afetados. Counter160 é0xA0 e cria header sobreposto; isso explica101 candidatos inválidos nos ensaios de checksum/byte/truncamento e1 candidato no de header. Todos os901 frames íntegros restantes foram recuperados. Métrica de candidatos não é contagem de falhas físicas.

Jitter uniforme com seed fixa: máximo desvio de intervalo 0.0019743485263057445 s. Teste separado com entregas alternadas ±1 ms produziu período médio10 ms, desvio-padrão2 ms e jitter máximo2 ms, dentro de1 ns de tolerância numérica.

## O que foi exercitado

- Todas as52 fronteiras de fragmentação de um frame; leitura byte a byte; múltiplos frames por chunk; lixo antes do header; A0 A0 dentro de float; recuperação após truncamento e checksum errado.
- Inversão individual de todos os424 bits do vetor: rejeição de cada alteração. Uma colisão deliberada00→FF mostra que Fletcher não detecta toda corrupção possível.
- Counter wrap, duplicata, pacote atrasado sem retroceder âncora e exemplo de256 perdas invisíveis ao counter.
- NaN/Inf preservados no wire e contabilizados sem contaminar estatísticas finitas; constante não é declarada sensor falho.
- Gerador TCP em processo separado e aquisição com desconexão forçada:80 frames aceitos e1 reconexão, sem erros.
- Pausa real de120 ms na conexão:1 episódio de timeout de stream e recuperação do segundo frame, sem reconexão.
- Replay byte a byte idêntico, métricas temporais e eventos de conexão iguais ao registro original.

## Limites

- Não foi executado teste real de8 horas nem medição longitudinal de RSS/CPU; o limite do parser não prova ausência de memory leak no sistema inteiro.
- Não foi executado no Windows do usuário, por USB/COM, ESP32, STM32 ou FO-IMU física.
- O modelo não executa o main/ISRs originais, não reproduz sua inicialização nem valida a simultaneidade dos sensores.
- Nenhum timeout físico de sensor foi inferido artificialmente. Valores null em latência/timeouts significam não observável, não zero.
- Os resultados não são requisitos de voo, calibração ou desempenho óptico.

Relatórios detalhados, configuração e capturas dos cenários pequenos estão em `examples/validation/`. O ensaio de1 milhão registra métricas sem gravar CSV/binário para não inflar esta entrega. Para reproduzir localmente: `python -m tools.acceptance --out logs/aceitacao_nova`.
