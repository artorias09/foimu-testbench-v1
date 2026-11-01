# Bancada gráfica P3

Base P2.1 `0c70ac518745b32f11cfd591f4a3501dcfe67200`. A Run pertence ao serviço. A janela controla a bancada e lê uma projeção dos registros que o writer já produziu. Fechar a janela deixa o serviço executando até a condição de término do Scenario. Para interromper a Run, use **Parar** e confira o ACK e o estado terminal.

## Executar no PC

Na raiz do repositório, abra dois terminais PowerShell. No primeiro, prepare um ambiente Python 3.12 e mantenha o serviço aberto.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv\Scripts\python.exe -m foimu_testbench.service --port 8877
```

No segundo, abra a bancada com o cenário de aceitação. No Linux, substitua o caminho do interpretador por `.venv/bin/python`.

```powershell
.\.venv\Scripts\python.exe -m foimu_testbench.gui --port 8877 --scenario configs/v2/normal.json
```

1. Confira perfil, taxa, seed, fragmentação e saída. Escolha oportunidades ou duração virtual. Use uma pasta nova para cada execução.
2. Para injetar falhas, marque a regra e defina seu parâmetro. As cinco regras periódicas usam oportunidades. Jitter usa segundos. O formulário mantém valores de regras desativadas para o caso de haver habilitação agendada.
3. O editor permite usar o Scenario completo, inclusive critérios e ações agendadas. Depois de editar o JSON, clique em **Aplicar JSON aos campos**. Ao iniciar, os controles do formulário prevalecem nos campos correspondentes. Os critérios carregados continuam explícitos mesmo ao mudar a quantidade.
4. **Iniciar** envia a receita resolvida e retorna um ID de Run no ACK. Acompanhe as três curvas, métricas, filas, workers e a lista de eventos. Escolha o canal pelo seletor acima de cada gráfico.
5. Filtre por domínio, componente ou severidade. Selecione uma linha para ler o evento com tempo, clock, referências e intervalo de bytes.
6. Ao terminar, **Abrir relatório** mostra o texto produzido pelo backend. **Abrir Run** verifica o diretório com RunReader. Para reanexar à execução em andamento, basta abrir outra GUI na mesma porta.

O cenário normal fornecido inclui critérios de 6000 frames e ausência de erros. O formulário padrão sem arquivo usa uma receita sintética sem critérios. Nesse caso a avaliação permanece “Não avaliada”.

## Processos, dados e clocks

| Responsabilidade | Proprietário |
|---|---|
| Janela, controles, gráficos, eventos e relatório | Thread principal Qt |
| Consulta local e entrega dos ACKs | Worker de rede no processo da GUI |
| Admissão de comandos e estado | Processo de serviço em loopback |
| Execução da Run | Thread de RunController no serviço |
| Aquisição, parser/diagnóstico e gravação | Três workers P2.1, com filas e shutdown originais |
| Projeção de apresentação | Handler do serviço, atendendo snapshot sob trava separada dos comandos |

A projeção mantém um cursor por JSONL de frames, eventos observados, eventos diagnósticos e controle. Cada avanço lê até 2048 linhas por arquivo. Uma linha ainda incompleta fica para a consulta seguinte. Sem consultas gráficas, a aquisição funciona sozinha. Não há callback de apresentação no parser ou no writer. Nenhum objeto Python é compartilhado entre os processos.

Os valores gráficos vêm de `observed/frames.jsonl`. O tempo no eixo horizontal é a recepção do último chunk do frame, no clock virtual `experiment`. Um pacote agregado não identifica quando cada sensor foi amostrado. A associação de temperatura por slot usa a política sintética `(counter-1)%8`, com um canal selecionável por slot.

Os gráficos começam com IFOG X/Y/Z. Cada painel tem seu próprio eixo e unidade. ACC e tap usam contagens, MEMS usa °/s ou m/s², IFOG usa °/h e temperatura usa °C. Valores não finitos são lacunas. Mudanças de época, offset, counter ou intervalos maiores que dois períodos nominais interrompem a linha. O limiar temporal é uma política visual. Pan e zoom operam sobre a janela carregada.

Métricas ao vivo vêm dos registros já lidos pela projeção. Leitura dos quatro arquivos pode terminar em prefixos ligeiramente diferentes. O backlog informa os bytes de índice ainda por exibir. O valor de `packets_lost` é uma lacuna candidata de counter. Checksum conta candidatos rejeitados, inclusive headers sobrepostos. Na Run íntegra concluída, `diagnostics/metrics.json` fornece os valores finais. Uma aba opcional apresenta separadamente o resumo de truth do simulador. O SUT continua recebendo apenas os bytes e os tempos definidos na P2.

Cada evento exibe seu clock. A tabela apresenta a ordem de leitura dos registros e preserva a ordem dentro de cada produtor. Não se infere ordem física entre o monotônico de controle e o clock virtual de recepção.

## IPC local v1

TCP IPv4 restrito a `127.0.0.1`, uma requisição e uma resposta por conexão. Prefixo de comprimento uint32 big-endian seguido do JSON. A versão IPC é independente do perfil FO-IMU e do schema da Run. Cada envelope tem `schema_version=1`, `message_type`, `id`, `catalog_ns` (UTC Unix) e `payload`. Respostas válidas repetem o ID da requisição. Erros de framing anteriores à leitura do ID recebem ID próprio.

| Requisição | Payload | Resposta |
|---|---|---|
| hello | vazio | hello_ack e limite de atualização |
| get_status | vazio | run_state |
| start_run | command_id, scenario, out | command_ack com run_id e caminho |
| stop_run | command_id, run_id, reason | command_ack com aceitação ou recusa |
| open_run | command_id, path | command_ack após inspeção somente leitura |
| snapshot_request | vazio | snapshot com sequência, monotônico de publicação e envelopes agregados |

Um snapshot contém `run_state` e, quando há dados de Run, `signal_snapshot`, `metrics_snapshot`, `event_snapshot` e `pipeline_health`. O terminal acrescenta `run_finished`, com relatório e resumo de truth quando disponíveis. Erros incluem código e detalhe. Linhas de sinais têm tempo em ns, época, offset inicial, counter e vetor de valores na ordem dos campos de Packet após o counter. O offset final de cada frame aceito é início + 53.

Comandos aceitos ficam associados a um hash do tipo e conteúdo. Repetir ID e conteúdo retorna o mesmo ACK, marcado como duplicata. Outro conteúdo com o mesmo ID é rejeitado. O cache dura uma sessão de serviço. Após 256 comandos distintos o serviço recusa novos comandos até ser reiniciado. ACK de início indica admissão. O estado acompanha erros de preparação e o resultado efetivo da Run. Falha de rede durante um comando gera indicação de entrega incerta.

## Limites operacionais

| Recurso | Limite |
|---|---|
| Atualização de snapshots | Até 5 Hz por sessão com cache no serviço, intervalo de consulta mínimo de 200 ms no cliente, timer gráfico de 200 ms |
| Apresentação pendente | Um snapshot substituível. O cliente conta substituições e sequências omitidas |
| Sinais | Até 6000 frames, dentro dos últimos 60 s virtuais do prefixo lido |
| Eventos | Até 500 eventos recentes |
| IPC | 4 MiB por mensagem, 64 KiB por comando, até oito handlers concorrentes |
| Comandos e ACKs na GUI | Oito itens por fila e um comando de operador pendente por janela |
| Prévia de relatório | Primeiros 262144 caracteres. O Markdown integral fica na Run |
| Filas obrigatórias P2 | Defaults de 8 MiB e 16384 itens para RX e para writer |

A taxa de snapshots e os limites de memória são escolhas da bancada. Em taxas altas os 6000 frames podem cobrir menos de 60 s. Discos e processos usam recursos do mesmo PC. O teste de isolamento comprova que um consumidor visual lento não impõe espera de dreno à fila obrigatória nos casos exercitados.

A telemetria apresenta taxa recebida, substituições, saltos de sequência, frames e eventos na janela, tempo de desenho, idade máxima do snapshot e CPU média do processo gráfico. A idade mede o intervalo entre a produção do envelope e o fim da atualização dos widgets, no monotônico do mesmo host. Backlog anterior à projeção e apresentação física no monitor ficam fora dessa medida. O objetivo provisório de 500 ms se refere à bancada.

## Reabertura e falhas

Execução, avaliação e integridade ocupam campos independentes. Perda da conexão mostra estado desconhecido e a GUI volta a consultar a porta. O serviço não é reiniciado pela janela. Para recuperação posterior, inicie o serviço e use Abrir Run. O leitor verifica manifesto, timeline e checkpoints segundo a P2. Uma Run interrompida mostra `interrupted_recovered/partial`. Para registro incompleto, a projeção limita os dados visuais aos prefixos confirmados. O relatório é histórico e pode divergir do resultado da verificação de integridade posterior. A origem é preservada.

O serviço permanece aberto até encerramento explícito. A Run possui sua própria condição de término. Abertura offline é recusada enquanto uma Run está ativa no serviço. A porta é para sessão local confiável, sem autenticação por usuário. Nenhum comando IPC é enviado ao instrumento físico.

## Diferenças em relação ao plano

* A execução usa o transporte virtual já disponível na P2. O socket desta fase é controle/apresentação local.
* A projeção lê os derivados persistidos para evitar recalcular o parser e acrescentar trabalho aos workers obrigatórios. A métrica interina indica prefixo e a métrica final identifica o artefato de origem.
* Falhas podem ser ligadas/desligadas antes do ensaio ou por ações agendadas no Scenario. Alteração por clique **durante** a Run ficou pendente. A P2 não fornece contrato de ACK e índice efetivo para essa mutação.
* Navegação gráfica cobre a janela carregada e os últimos eventos. Seek arbitrário, A/B e árvore causal completa permanecem na etapa posterior.

Consulte [P3_VALIDACAO.md](P3_VALIDACAO.md) para resultados medidos, problemas e gate Windows.
