# Validação P3

**P3 implementada. P3 não liberada.** O gate Windows 10/11 em instalação limpa de Python 3.12 continua pendente. Esta execução valida o cliente Qt em Linux offscreen e o backend local da P2.1.

## Identidade e comandos

Base congelada `0c70ac518745b32f11cfd591f4a3501dcfe67200`. Os resultados abaixo pertencem ao commit executável `c385058dcb698ece7374235b68598286b936dbd6`. O ajuste posterior de rótulos na janela e seus testes estão identificados separadamente abaixo. A manutenção do workspace removeu os objetos e logs locais da tentativa anterior. A implementação foi reconstruída e os números desta página vêm exclusivamente da execução na nova árvore.

```text
python -m unittest discover -s tests -p test_p3.py -q
python -m tools.acceptance_p3 --out <diretorio-novo>
```

O segundo comando invoca acceptance P2 uma vez. Esse gate descobre a suíte inteira, roda o milhão, testa equivalência binária, replay, overload e recuperação. O gate P3 também inicia os processos reais, aciona os widgets e verifica seus resultados. Todos os critérios do gate externo usam verificações explícitas que continuam ativas sob `python -O`.

## Resultado medido

| Ensaio | Resultado |
|---|---|
| Ambiente | Python 3.12.14, Linux x86_64, glibc 2.39, PySide6 6.8.3, pyqtgraph 0.13.7, numpy 2.3.5, Qt offscreen |
| Gate completo | 253,31 s, checkout limpo. `passed=true`, `windows=false`, `released=false` |
| Regressão P2 | 149,08 s. Suíte com 126 testes (108 existentes e 18 P3), 1 milhão aceitos, zero gaps/checksum/framing, pacote golden preservado, replay fiel, writer lento, overload e recovery |
| Normal com GUI lenta | 6000 frames, 318000 bytes. completed/passed/complete, zero gaps, checksum e framing. 6000 frames na janela e report.md aberto |
| Checksum | 1001 oportunidades, 901 frames aceitos, 101 candidatos checksum, 100 episódios de framing e 100 lacunas candidatas. Timeline exibiu os últimos 500 eventos |
| Stop explícito | cancelled/not_evaluated/complete. 159 frames aceitos e 27 bytes finais de frame incompleto, preservados no wire. O parser registrou uma cauda truncada e um episódio de framing |
| Fechamento normal | GUI fechada durante running. O serviço terminou com 400/400 frames, zero erros normais, relatório e reabertura íntegra |
| Kill abrupto | Processo GUI morto durante running. O mesmo oráculo de 400/400 frames e relatório íntegro foi cumprido |
| Abertura de Run completa | 6000 frames e relatório exibidos. Hashes de todos os arquivos iguais antes e depois |
| Abertura de Run interrompida | interrupted_recovered/partial, zero frames confirmados no fixture e sem aprovação |
| Reprodutibilidade digital | Comparação adicional de wire.bin, frames.jsonl e metrics.json, byte a byte, entre P2 headless e GUI. Igualdade nos três arquivos do cenário normal e nos três do cenário checksum |

No normal, SHA-256 do wire observado `9db8b004ebf12a10d5347fbd3a403c4d3687887d9efb23124d17dc436fe57d5e`. No checksum, `dd5b3c94e7b2687d6ce45505ed89302c540ae38b944056c34a6cd60f9d9bcc88`. O teste de Stop depende do momento do comando e usa o oráculo de cancelamento íntegro com prefixo recebido. A quantidade 159 é um resultado desta execução.

| Ensaio | Snapshots/s | Recebidos / substituídos | Máx. publicação até widgets | Máx. atualização das curvas | CPU média da GUI |
|---|---:|---:|---:|---:|---:|
| Normal com pausa da GUI | 3,59 | 96 / 6 | 261,0 ms | 73,4 ms | 34,4% |
| Checksum | 3,15 | 20 / 0 | 224,4 ms | 10,7 ms | 38,2% |
| Stop | 4,18 | 7 / 0 | 216,1 ms | 3,6 ms | 53,0% |

A atualização ficou abaixo de 5 Hz. A idade medida dos snapshots efetivamente apresentados ficou abaixo de 500 ms nestes três ensaios. Durante a pausa deliberada, a tela permaneceu sem atualização por 1,5 s. A substituição de seis snapshots explica por que a idade do último snapshot mostrado após a pausa pode ser muito menor que a duração do congelamento. O gate mede atualização dos widgets, sem incluir o atraso físico do monitor.

SHA-256 de summary.json do gate Linux: `3453d85db56d890282f4a709cc7c30aa2077f0ff0bffde2d6d0acf1b3b1a90ff`.

## Cobertura e oráculos

| Caso | Evidência e resultado esperado |
|---|---|
| IPC e framing | Roundtrip por socket, versão bool, tipo inválido, comprimento fora do limite, JSON duplicado e EOF parcial |
| Start e repetição | Um único run_id e diretório para comando repetido. Conteúdo conflitante com o mesmo ID é recusado |
| Stop | Um único efeito, ACK identificado, dreno e cancelled/complete. O teste Qt usa o botão durante Run ativa |
| GUI lenta e fila visual | Caixa de um item conserva o último de 2000 snapshots. No ensaio real o consumo gráfico pausa 1,5 s, o cliente continua consultando e a aquisição preserva 6000 frames |
| Limites | Mesmo snapshot dentro da janela de cache, até 6000 frames, 500 eventos e 60 s do clock virtual |
| Operação sem GUI | Serviço executa e produz relatório sem consultas de apresentação |
| Apresentação bloqueada | Barreira no leitor visual e RunController conclui com integridade completa antes da liberação |
| Fechamento normal e kill | Processos Qt e serviço separados. Writer de teste espera após o 128º bloco. O pai confirma Run ativa, encerra ou constata fechamento da GUI, libera o writer e verifica o total, relatório e reabertura |
| Backend ausente | Consulta do worker falha, snapshot marca desconectado, nenhum start é emitido. GUI exibe execução/avaliação/integridade desconhecidas |
| Run concluída | Botão Abrir Run, RunReader, janela carregada, abertura de report.md e hashes de todos os arquivos iguais antes/depois |
| Run parcial | Leitor conserva interrupted_recovered/partial, ignora cauda sem checkpoint e a GUI abre o registro sem exigir relatório |
| NaN/Inf e rupturas | Valores ausentes e não finitos geram NaN no gráfico. Mudanças de counter, offset, época ou gap temporal rompem a curva |
| Unidades e slots | ACC/MEMS e IFOG/MEMS permanecem em unidades separadas. Temperatura seleciona um único slot |
| Eventos e filtros | Episódios de checksum têm span. Filtros preservam domínio, componente e severidade. GUI carrega linhas e detalhes |
| Estados | Run sem critérios termina completed/not_evaluated/complete. Interrupção voluntária e registro interrompido têm estados distintos |
| Separação de truth | Remover todos os arquivos de truth não muda a projeção do prefixo observado. Métricas do cenário falho conferem com os derivados P2. O teste P2 também cobre o SUT |
| Relatório | Visualização textual do relatório produzido pelo backend. Abertura não regrava a origem |

O hook da barreira é exclusivo do harness de fechamento/kill. Esses testes registram o hook externo e usam watchdog de 40 s para permitir o ponto controlado. O ensaio gráfico de 6000 oportunidades, o checksum e o Stop usam os defaults do backend.

## Reproduzir o gate em Windows

Em Windows 10/11 real, abra o PowerShell na raiz de um checkout limpo e escolha nomes novos para ambiente e saída. O pacote Git anexado permite obter o mesmo histórico com `git clone -b feature/v02-p3-gui foimu-v02-p3.bundle foimu-p3`.

```powershell
py -3.12 -m venv .venv-p3
.\.venv-p3\Scripts\python.exe -m pip install -r requirements-gui.txt
.\.venv-p3\Scripts\python.exe -m tools.acceptance_p3 --windows-gate --out ..\p3-windows-01
```

A opção Windows exige win32, versão compatível, venv, Python 3.12, dependências fixadas e plugin Qt nativo windows. Executar em sessão gráfica. O arquivo summary.json registra versões, ambiente, commit, critérios, erros e desempenho. Guardar também os logs da instalação, p2.log, backend.log, qt.log e os resultados de cada caso. Um erro precisa ser investigado antes da liberação.

## Limites

A taxa solicitada é virtual. CPU média usa o tempo de CPU do processo gráfico, expresso como porcentagem de um núcleo. O ensaio mede snapshots elaborados, aceitos e desenhados em janelas limitadas. Sobrecarga geral do host, latência física, duração prolongada, hardware e display nativo Windows exigem evidência própria. A correção de shutdown por fase da P2.1 e o codec legado continuam no histórico original.


## Verificação final da janela

O painel passou a agrupar explicitamente fatos observados no parser e diagnósticos do fluxo. A tabela de eventos passou a usar a largura disponível. O runtime desse ajuste está em `cec47a0f78ed5245976f99b84bdab4465e7373c1`. Foram acrescentados quatro testes Qt para conferir agrupamento, aba opcional de truth, perda de conexão, seleção/detalhe de evento, filtros e configuração de falha/duração.

A suíte inteira após o ajuste passou com **130 testes**, sendo 108 anteriores e 22 P3. Um ensaio adicional de 1001 oportunidades foi executado por meio dos widgets e do serviço desse commit. Sinais durante a Run, 901 frames aceitos, 101 candidatos checksum, 100 lacunas candidatas, 100 episódios de framing, relatório exibido e reabertura íntegra foram verificados. O gate completo de 253,31 s pertence ao commit anterior. O milhão e o replay pesado foram executados uma única vez na reconstrução.

## Arquivos entregues

| Grupo | Arquivos |
|---|---|
| Serviço, IPC e projeção | `foimu_testbench/service.py`, `foimu_testbench/ipc.py`, `foimu_testbench/presentation.py` |
| Cliente gráfico | `foimu_testbench/gui/__init__.py`, `__main__.py`, `client.py`, `window.py` |
| Ambiente gráfico opcional | `requirements-gui.txt` |
| Testes | `tests/test_p3.py`, `tests/test_p3_window.py` |
| Aceitação | `tools/acceptance_p3.py`, `tools/p3_probe.py`, `tools/p3_harness.py` |
| Documentação nova | `docs/P3_GUI.md`, `docs/P3_VALIDACAO.md` |
| Documento existente atualizado | `README.md` com entrada para o cliente e o serviço |

O diff sobre P2.1 não modifica arquivos existentes de firmware, protocolo, backend P2, testes anteriores ou configuração v1/v2. A versão do aplicativo continua a da base. O SHA Git e o schema IPC identificam este incremento.
