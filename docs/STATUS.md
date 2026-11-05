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
