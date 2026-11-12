# Auditoria integral e reanálise observed

## Dependências e integridade

| Entrada | Responsabilidade | Evidência consumida |
|---|---|---|
| `replay.replay_run` | Reproduzir uma execução integral com identidade e derivação | `storage.RunReader` abre Run e Scenario, verifica manifesto, hashes, checkpoints e estrutura da timeline antes de fornecer chunks |
| `observed_input.project_run` | Exportar parâmetros operacionais de uma Run v2 existente | Lê `run.json` e `scenario.resolved.json` em nomes fixos. Confere tamanho/hash do Scenario contra a referência completa. Projeta perfil, Hz, timeout em ns e referências de tamanho/SHA-256 do wire e índice |
| `observed_input.open_observed` | Abrir uma fonte de arquivo de uso único | Recebe somente o diretório dos dois arquivos e a projeção. A view entrega chunks imutáveis com bytes, offset, época e tempo gravado |
| `observed_analysis.reanalyze_observed` | Reconstruir frames, eventos e métricas | Recebe a view e alimenta o mesmo `Processing.consume` da aquisição. Retorna a saída somente após ler e verificar toda a entrada |
| Validação integral | Comparar resultados com critérios, inclusive os de truth | `validation.truth_summary` lê a verdade registrada e `validation.evaluate_run` escolhe a fonte pelo domínio do critério. Este papel continua no backend existente; uma classe adicional ValidationView seria redundante |

Na aquisição, `RunController._processing_worker` extrai taxa e timeout do Scenario. O produtor
registra truth em `emission.VirtualSource`. O serviço de apresentação lê o resumo de truth
separadamente. O replay integral usa `RunReader.chunks` para ler `observed/wire.bin`
e `RunReader.timeline` para ler `observed/chunks.jsonl`. A falta de um artefato listado
é detectada em `RunReader._verify_manifest` e impede a abertura estrita.

A fronteira começa **depois da projeção**. Para retirar o Scenario completo de uma cópia,
exporte antes a projeção, ou obtenha sua cópia registrada junto à fonte confiável.
A serialização usa os contratos JSON v2. A reanálise aceita apenas o par wire/índice
e a projeção. Truth, plano, validação, arquivos de frames/eventos previamente calculados
e métricas persistidas ficam fora de suas entradas. Os frames e métricas persistidos
são usados como referência independente de entrada **pelo teste diferencial**.

## Uso com uma Run v2 já gravada

```python
from pathlib import Path
from foimu_testbench.observed_input import project_run, open_observed
from foimu_testbench.observed_analysis import reanalyze_observed

run = Path("logs/ensaio")
spec = project_run(run)
with open_observed(run / "observed", spec) as view, reanalyze_observed(view) as result:
    print(result.observed_integrity)
    print((result.directory / "metrics.json").read_text(encoding="utf-8"))
```

O resultado reside em diretório temporário durante o bloco. Para preservá-lo, copie seus
quatro arquivos para um destino próprio durante o bloco. Para usar em outra máquina,
transfira `spec.to_json()` por meio confiável, restaure com `ObservedProjection.from_json`
e passe à API a pasta contendo exclusivamente o wire e o índice. Um ensaio de zero bytes
pode ter apenas o índice com fim explícito.

**complete** cobre exclusivamente as duas entradas consumidas. O leitor verifica hash e
tamanho totais enquanto lê, hash por chunk, sequência, offsets, época, clock, monotonicidade,
marcador final e ausência de sobra no wire. Uma entrada inválida levanta erro antes de disponibilizar
o resultado. Evidência parcial exige política de prefixo separada e é recusada nesta versão.
Os hashes pressupõem uma projeção de referência confiável. A substituição coordenada de
referências e dados exige autenticação externa para ser detectada. A API delimita dependências
entre componentes Python e não fornece isolamento de processo.

## ObservedCanonicalV1

A comparação usa igualdade dos quatro arquivos, incluindo sua ordem interna. Cada registro é
JSON determinístico com LF. As listas de inclusão estão em `observed_analysis`.
Mudanças de campos ou ordem exigem nova versão ou justificativa de compatibilidade registrada.

| Arquivo | Definição comparável |
|---|---|
| frames.jsonl | Ordem de aceite, época, span [início,fim), clock e tempo de recepção do último chunk, counter, integridade do frame, 15 campos e classificação numérica por campo |
| observed_events.jsonl | Ordem no domínio, tipo, componente, época, span, instante da detecção, domínio, estatuto epistêmico, faceta, severidade, versão da regra e payload permitido por tipo. Inclui candidato rejeitado, descarte e ressincronização |
| diagnostic_events.jsonl | Mesma estrutura, com transições observadas de silêncio e descontinuidade do counter, parâmetros temporais ou interpretação registrados pela regra |
| metrics.json | Versão, contagens da lista METRICS, estatística de período, jitter, maior intervalo e contagens de suspeitas de sentinela por sensor |

Um evento sem span de bytes conserva null. A baseline não produz frame span independente.
A ordem é definida separadamente em cada domínio. Métricas temporais usam os valores
originais da timeline no relógio experiment, inclusive leituras vazias. Tempo de execução
da reanálise, duração de CPU e latência física ficam fora da comparação.

## Proteção e escopo

`tests/test_observed_boundary.py` compara a saída persistida ao vivo com reprocessamento
em arquivo isolado, truth removida e truth falsa. Exercita adulteração das entradas, ausência
de dados, parcial, troca de época, silêncio e tempo irregular. O mutante soma as oportunidades
de truth à contagem ao vivo de checksum. A mesma comparação acusa a diferença.

A verificação AST limita os imports internos estáticos da cadeia à lista explícita:
observed_input, observed_analysis, processing, evidence, protocol, protocol.gateway53,
diagnostics, core, core.schema, core.contracts e inicializador do pacote.
Ela complementa o diferencial de execução. O protocolo e a política de counter desta
baseline continuam sendo a referência dos testes.

A regra counter8-reacquire-v1 pertence a diagnostics.counter, incluído no fechamento
de imports observado. A allowlist ObservedCanonicalV1 foi preservada. Em eventos de
descontinuidade, interpretation identifica a classe modular observada e rule_version
identifica sua regra. Os contadores adicionais de reaquisição estão no relatório
diagnóstico integral. Comparações de arquivos históricos devem levar em conta a versão
da regra: o replay com o código novo pode legitimamente produzir valores diferentes
dos calculados com a âncora antiga. Bytes e tempos de recepção são reutilizados.
