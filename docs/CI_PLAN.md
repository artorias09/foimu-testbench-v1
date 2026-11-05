# Plano de CI

SUPPORTED_PYTHON = CPython 3.12.x (metadado >=3.12,<3.13). Execução local registrada
com 3.12.14. A revisão anterior anunciava >=3.11; habilitar outra série exige testá-la
primeiro. O plano de matriz cobre Linux e Windows. Os resultados locais não substituem
a execução em runners Windows ou ensaios físicos. Não há publicação de workflow nesta etapa.

| Nível | Quando | Comandos / evidência |
|---|---|---|
| Rápido | A cada PR, Linux e Windows | unittest discovery dos grupos p1, evidence_tree, observed_boundary, counter e protocol; executar tools.counter_mutants e tools.evidence_mutants. Conferir bytes canônicos, propriedades e saída killed por ID. |
| Médio | Branch de integração | python -m unittest discover -s tests -v; P1/P2/P2.1/P3 direcionados, Run v2 curta, replay e recovery. Instalar pins de requirements-gui.txt e rodar janela Qt offscreen em job próprio. Gate da janela exige zero skips de Qt nesse job. |
| Pesado | Agendado ou antes de liberar | python -m tools.acceptance_p2 --out DIRETORIO_NOVO (inclui milhão legado); fuzz prolongado, soak, GUI lenta e gate Windows físico. Mutation testing automático é futuro. |

Arquivar revisão/tree, ambiente, comandos, contagem e razões de skips, seed, logs completos
e hashes. Um erro de sintaxe ou import na execução mutante invalida o ensaio. Regressão ou
intermitência exige investigação registrada, sem retry automático para ocultar a primeira falha.
