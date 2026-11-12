# Observabilidade por detector

Uma entrada de observability.CLAIMS relaciona condição, detector, status, razão,
premissas, limite e teste. Os status se referem exclusivamente ao par condição/detector.

| Condição | Detector | Status | Premissas | Limite / razão |
|---|---|---|---|---|
| Lacuna modular candidata | counter8 | observable | Referência travada, mesma época, hipótese de progressão ordenada | 2 ≤ delta ≤ 127. Estimativa de 1 a 126 posições. MODULAR_FORWARD_GAP |
| Perda de múltiplo de 256 | counter8 | not_observable | Mesma época, somente counter | Adicionar k voltas completas deixa o par de bytes idêntico. COUNTER8_ALIASING |
| Causa de salto ambíguo | counter8 | not_observable | Mesma época, somente counter | Para delta ≥ 128 a observação do salto sustenta várias explicações. MULTIPLE_COMPATIBLE_CAUSES |
| Intervalo longo de recepção | host_receive_timing | warning_only | Timeline preservada, mesma época, limiar calibrado e buffering limitado para interpretar o transporte | O watchdog mede silêncio frente ao limiar nominal. HOST_INTERVAL_ONLY |

Um valor repetido é observável, mas sua origem física é desconhecida. Um salto ambíguo é
observado; a atribuição de causa é inconclusiva. O intervalo do host pode acrescentar um
aviso mesmo se o par de counters progrediu de uma unidade. A medida sozinha não estima
o número de amostras perdidas. A calibração para a FO-IMU real está pendente.

## Check observado V1

Observabilidade qualifica uma relação condição/detector. O resultado abaixo qualifica a
execução de um predicado sobre uma janela. Os status de execução, avaliação e integridade
da Run continuam em seus contratos próprios.

| Resultado | Significado operacional |
|---|---|
| not_evaluated | Check previsto, sem execução, por exemplo desabilitado, fora da janela ou sem implementação. Materializado mesmo quando falta a linha de resultado. |
| unknown | Houve tentativa, mas a evidência, as premissas ou a integridade não sustentam uma conclusão confiável. |
| inconclusive | Há evidência concreta e mais de uma interpretação compatível. Um salto modular é observado; sua causa permanece aberta. |
| ok | O produtor atesta ter executado o predicado sem violação, com premissas satisfeitas. O agregador exige referência positiva, janela e quantidade mínima. Aprovação restrita ao predicado e cobertura declarados. |
| warning | Evidência concreta de degradação, suspeita ou premissa parcial. É o máximo que um indicador heurístico pode atribuir como anomalia. |
| failed | O produtor atesta uma violação explícita do critério, com detector identificável, descrição da violação, premissas suficientes, quantidade e janela verificáveis. |

A API `aggregate(MANIFEST_V1, resultados_por_check_id)` devolve bytes JSON UTF-8 de
EvidenceTreeCanonicalV1. O chamador fornece o resultado de checks executados separadamente,
todos da mesma execução. A função não executa detectores, autentica arquivos nem atribui
causa. O manifesto completo existe antes dos resultados. Os nós de sensores são opcionais
e registram a limitação física; os checks do pacote são associados ao protocolo compartilhado.
Protocolo e Transporte são requeridos. O indicador de intervalo longo é opcional.

O pai usa o pior resultado aplicável entre checks locais e filhos requeridos:
failed > inconclusive > warning > unknown > not_evaluated > ok. Um filho opcional
tem linha e motivo próprios. Evidência e limitações opcionais também sobem. Uma folha
exclusivamente cega registra seu limite e não vota como falha. Um lugar requerido vazio
sem check declarado fica not_evaluated. A raiz conta condições limitadas distintas sem
detector formal declarado no seu escopo. O limite de um detector permanece registrado
mesmo quando outro detector cobre a condição.

### EvidenceRef e política de cobertura

V1 referencia fonte observed, ID e versão do check, artefato lógico (wire, frames ou chunks),
contagem, integridade e cobertura [início,fim). A origem e a versão têm defaults fixos.
No wire o intervalo é de bytes; nos demais artefatos é de registros ordinais. Época e
fim exclusivo de prefixo confirmado são opcionais. A razão e uma eventual violação
pertencem ao CheckResult. O artefato é identificado dentro da captura fornecida pelo
chamador; misturar execuções viola a premissa da API.

Uma conclusão positiva precisa de cobertura explícita. Ao menos uma referência deve
atingir o mínimo declarado pelo check; não somamos referências potencialmente sobrepostas.
Toda referência utilizada deve ser suficiente em integridade. Um frame válido ou
candidato a checksum exige ao menos 53 bytes. Todos os checks de counter no manifesto
exigem duas observações. Entradas inválidas ou sem cobertura suficiente dão unknown.
Conclusão sem referência, ID incompatível ou failed sem violação são erros de contrato.

| Grupo de checks | Uso de integridade partial |
|---|---|
| Counter8 | Aceita par localizado no prefixo confirmado com estado inicial e época conhecidos, além das premissas do par. |
| Parser e Fletcher | Aceita decisão local confirmada até o fim declarado, inclusive estado de entrada para enquadramento. |
| Timing de recepção | Política conservadora: requer timeline completa. Cauda desconhecida pode mudar o intervalo coberto. |
| Condição cega | Limitação por detector. Nunca autoriza ok por descarte de evidência. |

O resultado de um prefixo explicitamente aceito mantém integrity=partial, cobertura e
partial_checks em todos os ancestrais. Esta política descreve o consumidor de referências.
A fonte observed integral continua recusando reanálise de entradas parciais.

### Canonicalização e premissas de confiança

Campos selecionados: versão da árvore e manifesto, raiz, nós, relações requeridas e opcionais,
resultado, aplicabilidade, checks, versões, detector, limites, premissas, mínimos, razões,
violações, referências com cobertura, limitações estruturais e escopo parcial. Nós, checks,
conjuntos e referências são ordenados e referências idênticas são deduplicadas. A ordem
dos filhos não altera os bytes. Identificadores devem ser semânticos, sem caminhos ou
informações da execução. O núcleo confia que o produtor realmente observou o intervalo
referenciado; um EvidenceRef não é uma assinatura nem uma prova autônoma de autenticidade.
