# Pré-registro G5, revisão 1

Registrar o commit deste documento antes de abrir a primeira captura física. Escopo:
perfil gateway53-fletcher16-le-v1, hipótese de correspondência à revisão instalada.
As fontes G e MAN e as funções/linhas são identificadas em AUDITORIA_FASE_0.md.

| Expectativa | Fonte | Confiança antes da captura | O que a refutaria nesse escopo |
|---|---|---|---|
| Candidatos têm 53 bytes com header A0 A0 | G, struct e TX; MAN, exemplo do host | Alta para snapshot, instalada pendente | Em transporte confirmado, outro alinhamento persistente explica o wire e este não estabiliza |
| Fletcher mod 255 sobre [2,51), dois bytes LE | G, cálculo/empacotamento; MAN Listing 2 | Alta para snapshot | Candidatos alinhados com divergência sistemática reproduzida por decodificador independente |
| Counter uint8 avança módulo 256 em regime regular | G, campo e incremento | Alta sobre largura no snapshot, condicional sobre progressão | Campo diferente ou progressão incompatível em aquisição limpa e ordenada, após excluir perdas no logger |
| Aproximadamente 100 Hz nominais | G TIM3; MAN | Moderada para taxa instalada | Taxa sustentada incompatível em janela estável, com relógio e buffering caracterizados |
| Em regime, header, checksum e ordem de campos tendem a permanecer estáveis | G e MAN, inferência sobre C1 | Condicional | Mudança persistente de layout dentro da mesma configuração confirmada |

Conservar o pré-registro original. Revisões posteriores devem registrar data, commit,
evidência já vista, alteração, motivo e impacto na claim. Distinguir resultados por
revisão física, época e janela de boot/regime.

Em G5, informar denominadores e taxas de candidatos, aceitações, erros e ressyncs;
quando aplicável apresentar intervalo de confiança, método e premissa de independência.
Considerar rajadas e autocorrelação antes de usar intervalo binomial. O critério é por
escopo (framing, checksum, counter, IFOG, ACC, MEMS ou timing). Para cada divergência
registrar divergence_id, scope, observation, expected, classification, evidence
(arquivo/hash/span/época), claim_impact e status. Classificar como PARSER, FIRMWARE,
TRANSPORT, CAPTURE_ARTIFACT ou UNKNOWN. UNKNOWN bloqueia as claims dependentes.
Registrar quais escopos ficaram aprovados, bloqueados ou sem evidência.

Se a captura limpa em transporte confirmado não estabilizar em A0 A0, 53 bytes e
checksum do perfil, e revisão diferente, transporte ou artefato de captura não explicarem
a divergência, registrar LAYOUT HYPOTHESIS REFUTED e parar a evolução dependente do layout
até replanejamento. Este documento prepara o gate, cuja execução depende do IEAv.
