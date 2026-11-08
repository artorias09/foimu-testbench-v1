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

## Revisão 2, congelamento anterior à recepção

Todos os itens abaixo têm status HYPOTHESIS para a unidade instalada. A confiança expressa
a expectativa sobre a captura antes da observação. G e MAN remetem às referências do quadro acima.

| ID | Escopo | Comportamento esperado | Fonte | Confiança | Sustenta | Refuta |
|---|---|---|---|---|---|---|
| E1 | comprimento | 53 bytes/candidato | G struct packed, MAN | moderada | Distância repetida de 53 entre limites confirmados pelo consumidor independente | Outro comprimento estável explica os mesmos bytes |
| E2 | framing | A0 A0 inicia o frame | G header, MAN | moderada | Assinatura nos limites confirmados em várias janelas | Outra assinatura nos limites, após verificar transporte |
| E3 | counter | uint8 no offset 2, rollover modular | G struct/TX | moderada | Progressão e voltas no campo, concordância byte a byte | Outro offset/largura demonstrado pelo firmware instalado ou consumidor |
| E4 | checksum | Fletcher mod 255 do payload [2,51), LE em [51,53) | G TX e MAN Listing 2 | moderada | Recomputação consistente em frames alinhados | Outra regra explica discrepâncias sistemáticas em transporte íntegro |
| E5 | taxa | aproximadamente 100 Hz em regime | G TIM3, MAN | moderada, condicional | Contagens por janela de tempo de recepção confiável em C1 | Outra taxa sustentada, além da incerteza de medição e buffering, corroborada pelo laboratório |
| E6 | endianness | campos multibyte little-endian | G struct/MCU, contrato auditado | moderada | Campos com bytes assimétricos batem com decodificação independente | Interpretação alternativa corroborada nos mesmos spans |

Histórico: revisão 1 na baseline eeed2dd. Revisão 2 individualiza comprimento e header,
inclui endian e critérios positivos. Nenhuma captura real foi consultada. Após a abertura,
registrar toda revisão com documento, versão/commit anteriores e novos, evidência já vista,
motivo e impacto por claim. Preservar a análise realizada com o pré-registro anterior.
O código formal de parada desta revisão é LAYOUT_HYPOTHESIS_REFUTED.
