# P3.5A, fronteira observed, 2026-11-05

**VERIFIED_LOCAL** no Linux x86_64, Python 3.12.14, branch
`feature/v02-p35-truth-boundary`. Baseline reconciliada pelo bundle em
`4e1f8c3caa10f4b5f32deca2b7e616cabb28c0a6`, tree
`c6ad049b34d7185251a4404e2756e754b499337a`. Revisão executável e testes
em `26d6509`. Dependências de produção adicionais: zero.

| Comando | Descobertos | Passaram | Falharam | Pulados |
|---|---:|---:|---:|---:|
| python -m unittest discover -s tests -v | 142 | 138 | 0 | 4 |
| python -m unittest discover -s tests -p 'test_p1*.py' -q | 31 | 31 | 0 | 0 |
| python -m unittest discover -s tests -p 'test_p2*.py' -q | 46 | 46 | 0 | 0 |
| python -m unittest discover -s tests -p 'test_p3*.py' -q | 22 | 18 | 0 | 4 |
| test_observed_boundary no discovery completo | 10 | 10 | 0 | 0 |

P2 inclui shutdown P2.1, replay integral e recuperação após morte de processo. Os quatro
skips são os testes da janela Qt por ausência de PySide6 e pyqtgraph. Testes P3 do serviço,
do cliente e de apresentação disponíveis passaram. Os grupos são subconjuntos da suíte.

Probe do PRE-GATE executado com `PYTHONPATH=. python ../pregate.py` a partir do repositório.
SHA-256 do script: `a4404ee1b37f799cf0bf8f8b0ff2282a85176b81b9cb3159adc290161ee41474`.
Conservação confirmada em 200 seeds, 1.854.905 bytes e 12.801 frames aceitos.
A sequência de counter auditada continua produzindo 40 descontinuidades.

**Fronteira aprovada localmente.** Os arquivos canônicos ao vivo e reanalisados foram iguais
nas três variantes. O mutante de teste foi detectado por uma diferença de 32 na métrica de checksum.
O replay integral recusou as duas cópias com truth alterada ou removida. A aprovação se limita
ao caminho de evidência completa documentado em TRUTH_BOUNDARY.md.

**REPORTED_NOT_REPRODUCED** para o gate histórico da GUI em Windows.
**EXTERNAL_PENDING** para captura física e confirmação de revisão, escala e timing no IEAv.
O restante dos gates P3.5A, inclusive a correção do counter, permanece pendente.

## Atualização de 2026-11-05: counter8 e observabilidade

Branch feature/v02-p35-counter. Base d3288babe8b34a324dbce657cbd8be70727448ce
(tree 31a7831c3b6bc427b680862e24a98c7494519080). HEAD executável testado:
6695dd5c99c4932da88a54aaebd8359e69289ed7. O commit seguinte registra a documentação;
o manifesto do pacote informa seu HEAD final.

| Gate local | Resultado |
|---|---|
| Suíte completa, mesmos comandos de discovery acima | 151 descobertos, 147 passaram, 0 falhas, 4 skips Qt |
| P1 | 31/31 |
| P2 e P2.1 | 46/46 |
| P3 | 18/22, 4 skips por dependências Qt ausentes |
| Fronteira observed | 11/11, incluindo comparação do episódio ambíguo ao vivo e em arquivo |
| Propriedades da máquina | 100 seeds, 25.600 transições |
| python -m tools.counter_mutants | 10 killed, 0 survived |
| Mesmo pregate.py | 200 seeds, 1.854.905 bytes, 12.801 frames, zero violações de conservação |

O ensaio com 50 frames que abriu 40 ambiguidades na baseline passou a abrir uma única
ambiguidade; referência final 239, zero lacunas candidatas. A causa permanece inconclusiva.

A primeira integração falhou ao persistir um evento de descontinuidade por usar uma
variável sem atribuição. O teste integrado reproduziu a falha e a correção passou
no diferencial. Na primeira suíte completa, a salvaguarda P1 de identidade binária
recusou a alteração solicitada de diagnostics/__init__.py. O teste agora fixa o SHA-256
dessa revisão específica do consumidor. Os outros cinco arquivos continuam comparados à
v0.1. O vetor golden, a lógica de framing e o Fletcher seguem protegidos pela suíte.

VERIFIED_LOCAL para a política counter8-reacquire-v1 e sua integração. Em ensaio real,
atribuição física, calibração do tempo do transporte e revisão de firmware são EXTERNAL_PENDING.

## Atualização de 2026-11-05: estados e evidências

Base 098f15c79109f697469d01ce9d17edcafd130ef8. Branch feature/v02-p35-state-evidence.
Revisão executável 16daaea. Linux, CPython 3.12.14, biblioteca padrão.
A API é lógica e independente da GUI. O gate cobre o agregador, o contrato de referências
e os detectores digitais registrados. A entrada dos checks é explicitamente atestada pelo
produtor. Integração visual, interpretação física e verificação no IEAv seguem pendentes.

| Gate | Resultado observado |
|---|---|
| python -m unittest discover -s tests -v | 161 descobertos, 157 passaram, 0 falhas, 4 skips Qt por dependências ausentes |
| Discovery separado de test_p1*, test_p2*, test_p3* | 31/31, 47/47 (inclui o novo teste de fsync), 18/22 com quatro skips |
| Discovery separado de test_observed_boundary*, test_counter*, test_evidence_tree* | 11/11, 8/8 e 9/9 |
| Propriedades | 2.000 árvores, 40 seeds, profundidade variável; 100 variações adicionais de limites. Combinações de estados verificadas separadamente. |
| tools.evidence_mutants | 12 mutantes de semântica e cinco da TCB detectados |
| tools.counter_mutants e diferencial T01 | Dez mutantes de counter e um de contaminação ao vivo detectados |
| pregate.py com PYTHONPATH=. | 200 seeds, 1.854.905 bytes, 12.801 frames, zero violações; sequência do counter: 50 frames, um salto ambíguo, referência 239, zero lacunas candidatas |

Na preparação do ensaio E16, o controle limpo identificou a ausência de run_id no novo
fixture de checkpoint. O ensaio foi corrigido antes de contabilizar o mutante. O gate
usa somente execuções nas quais o controle limpo passou e o mutante falhou por asserção.

## Fechamento P3.5A

PUBLICATION_PENDING. G1 aguarda GitHub Actions nas duas plataformas. A fonte de evidência
local desta entrega é a revisão executável indicada em evidence/gates/G2 a G4. Os commits
seguintes acrescentam instruções, pré-registro e os próprios resultados. O bundle completo
contém o histórico necessário ao teste de blobs v0.1 e pode ser clonado diretamente.

| Claim | Status | Evidência e escopo |
|---|---|---|
| Identidade local reconciliada | VERIFIED_LOCAL | G0, Git HEAD/tree e registro de origem |
| Core e Qt em CI Linux e Windows | EXTERNAL_PENDING | G1 not_run, exige runner remoto |
| Truth não influencia reanálise observed no corpus testado | VERIFIED_LOCAL | G2, diferenciais e auditoria integral estrita |
| Parser conserva bytes no corpus gerativo | VERIFIED_LOCAL | G3, 200 seeds |
| Counter readquire após salto ambíguo | VERIFIED_LOCAL | G2/G3, caso 9,200,201 |
| Agregação exige evidência positiva | VERIFIED_LOCAL | G3/G4, propriedades e mutantes |
| Cinco capturas sintéticas reproduzem os arquivos esperados | VERIFIED_LOCAL | G3, hashes das entradas e saídas em tests/corpus |
| Gate histórico Windows em estação real | REPORTED_NOT_REPRODUCED | Relato de aprovação, artefatos históricos indisponíveis nesta entrega |
| Conformidade com FO-IMU, escala ACC/IFOG/MEMS | EXTERNAL_PENDING | G5 por claim, capturas e metadados externos |
| Latência física absoluta a partir de tempo de recepção isolado | NOT_SUPPORTED | O perfil legado carece de timestamp físico por sensor |

A descoberta local inclui um novo teste que verifica os cinco casos do corpus. Total 162,
158 passaram e quatro testes Qt foram pulados por dependências opcionais ausentes.
O controle inicial de G4 rejeitou um mutante detectado por dois subtestes do mesmo teste.
O executor foi corrigido para reconhecer múltiplas falhas de asserção, mantendo a
exigência do teste esperado e a rejeição de erros de execução. A matriz final executou
os 28 casos. O workflow pesado fica disponível por acionamento manual.
