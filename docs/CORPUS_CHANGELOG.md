# Corpus sintético digital

Versão inicial 1. Referência usada para todos os casos: 2c709f893a7f99e362d9cf5e61b6511740efe60b.
Entradas construídas sobre o vetor da fixture C independente, com counters e checksums ajustados.
Os quatro arquivos esperados foram exportados do caminho ao vivo, após verificar os
oráculos abaixo. A regressão reabre somente wire e timeline por fonte de arquivo.

| Caso | Transição de versão | Oráculo / escopo |
|---|---|---|
| normal | inicial → 1 | 3 frames aceitos |
| counter | inicial → 1 | 9,200,201,202; uma ambiguidade e uma reaquisição |
| checksum | inicial → 1 | 2 aceitos e um candidato com checksum inválido |
| epoch | inicial → 1 | Duas épocas explícitas, dois frames, uma reconexão |
| truncated | inicial → 1 | Um frame e cauda de 19 bytes descartada no fim confirmado |

Cada metadata.json registra os hashes do wire, da timeline e das quatro saídas e a projeção
para reanálise. O gate registra também o hash do próprio metadata.json.
Mudança de expectativa exige novo registro com caso, versão antiga/nova, motivo, commit
de referência, prova independente e impacto na claim. Uma diferença de teste, isoladamente,
não autoriza substituir o esperado. O corpus não contém captura física.
