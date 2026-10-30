# P1: contratos e caracterização

Implementação exclusiva de P1, sobre `52531eaa16bb111cdb6ad862c8fd037d6ead0977`.
O plano anterior foi incorporado sem alterações. Nenhum executor, codec, parser,
config v1, teste legado, fixture ou exemplo foi modificado. P2 não foi iniciado.

## Uso e instalação

Python >=3.11, biblioteca padrão, sem novas dependências. O ambiente validado é
Python 3.12.14/Linux. Windows continua pendente. A CLI v1 permanece exatamente
igual. Não há comando CLI v2 nem runner v2 nesta etapa.

```python
from pathlib import Path
from foimu_testbench.scenarios import load_v1, Scenario, to_v1
from foimu_testbench.provenance import new_run

scenario = load_v1('configs/normal.json')
text = scenario.to_json()
restored = Scenario.from_json(text)
assert to_v1(restored)['packets'] == 1000
run = new_run(restored, Path.cwd(), run_id='ensaio-001')
assert run.execution_status == 'draft'
assert run.evaluation_status == 'not_evaluated'
assert run.integrity_status == 'unknown'
run = run.transition('validated')
```

`new_run` coleta identidade antes de qualquer execução. Não inicia aquisição,
não abre transporte e não escreve arquivos. P2 deverá consumir essa identidade;
o caminho v1 continua coletando seu hash ao terminar.

## Contratos públicos

| Local | Responsabilidade |
|---|---|
| `core/schema.py` | Dataclasses tipadas, validação estrita, JSON canônico e rejeição de chaves duplicadas |
| `core/contracts.py` | Run, Event, TimePoint, ClockDefinition, Fidelity, CodeIdentity, AcceptanceCriterion, EvaluationResult, ArtifactReference, Provenance, Reference e ByteSpan |
| `scenarios.py` | Scenario L1 e contratos auxiliares de taxa, duração, transporte, regras, ações, recursos e importação |
| `provenance.py` | Identidade Git/ambiente/hashes e fábrica de Run draft |

Todo objeto de contrato tem `schema_version=2`. JSON salvo exige versão explícita
em cada objeto tipado, inclusive os aninhados. `ImportRecord.source_schema_version=1`
é a versão da fonte importada, não a versão de seu envelope.

Construtores não convertem strings em números. `bool` é recusado onde se exige
inteiro, inclusive versão, seed, sequência e offsets. Domínios fechados usam
`typing.Literal`, validados em runtime com comparação de tipo e valor. Quantidades
aceitam explicitamente int ou float finitos; sua unidade é obrigatória e limitada
por contexto (`Hz`, `s`, `ns`). Campos opcionais desconhecidos são `None`/`null`.
JSON não admite NaN/Inf ou objetos Python; o wire legado continua admitindo esses
bit patterns. `payload` é intencionalmente aberto, mas restrito a valores JSON
finitos: sua semântica específica pertence à regra identificada pelo evento.

`to_json()` ordena chaves e usa separadores fixos e UTF-8. Preserva ordem de listas,
que pode ter significado experimental. Determinismo é para os mesmos valores e
schema; identidade UTC/Git naturalmente muda entre coletas. Isso não implementa
canonicalização numérica universal entre linguagens.

Dataclasses têm atributos congelados. Listas/dicionários internos não são containers
profundamente imutáveis; não devem ser editados por referência durante um ensaio.
`to_dict`, `to_json` e transições revalidam o conteúdo; `from_json` produz cópia nova.
P1 não introduz compartilhamento concorrente. Fronteiras futuras devem enviar snapshots
JSON, não referências mutáveis. Alterações declarativas usam `dataclasses.replace`,
que revalida o novo objeto.

## Execução, avaliação e integridade

Caminho normal: draft, validated, prepared, armed, running, stopping, finalizing,
completed. Transições são explícitas por `Run.transition`, retornando novo objeto.
Cancelamento antes de iniciar é direto; durante execução passa por stopping/finalizing
antes de cancelled. Failed/aborted são saídas possíveis das fases operacionais,
sempre com motivo. Estados terminais não reabrem. `interrupted_recovered` é apenas
estado de importação terminal e exige motivo e integridade não completa; nenhum
recuperador físico foi implementado.

Concluir não muda avaliação nem integridade. Aprovação requer execução completed,
integridade complete, critérios não vazios, resultado para todos, evidência positiva
e comparações coerentes. Resultado desconhecido ou evidência insuficiente é inconclusivo.
`evaluate` compara somente um escalar e um critério; não é o motor de avaliação de
ensaios de P2. O chamador fornece evidência e unidades coerentes com o critério.
Não há autenticação de que uma evidência declarada realmente ocorreu.

JSON de Run pode representar um estado já existente, sem histórico de transições;
`transition` valida mudanças em memória. Um journal que demonstre o histórico é P2.

## Tempo e eventos

ClockDefinition declara virtual, monotonic_local, utc_catalog ou unknown. TimePoint
contém clock_id, meaning, valor inteiro em ns (ou desconhecido), unidade e incerteza.
Resolução do clock e incerteza não são inferidas do número de casas do valor.
`elapsed_ns` recusa clocks diferentes, UTC/unknown, regressões, valores desconhecidos
e significados distintos. Não faz sincronização nem cálculo de latência entre clocks.

Event suporta campos do plano com opcionais nulos. ByteSpan usa `[start,end)`,
não vazio e início não negativo. Span exige stream e época. Truth exige
simulator_truth; observed não admite truth/inference/hypothesis como certeza.
`Run.validate_event` verifica associação de Run e registro de clock. Ele não grava
nem localiza eventos no parser legado. Observação e truth são envelopes independentes;
nenhum novo contrato é importado pelo codec ou pelo diagnóstico v1.

## Scenario e importação

Scenario só admite L1, synthetic_v1, contrato legado e transporte virtual ou TCP.
Clock virtual exige transporte virtual; monotonic_local exige TCP. Não há implementação
de novos transportes. Quantidade de oportunidades e duração são alternativas exclusivas.

O importador registra SHA-256 do JSON de entrada canonicalizado, caminho opcional e
normalizações aplicadas. Não é hash byte a byte do arquivo original. Copia fragmentação,
resolve defaults existentes, registra unidades e não inventa critérios de aprovação.
Configs v1 não identificam modo de transporte; por isso a importação escolhe virtual
explicitamente e registra essa escolha. Todas as cinco configurações existentes têm
roundtrip sem alteração de semântica pelo adaptador `to_v1`.

`schema_version=True` é rejeitado pelo importador e pelo schema v2. O validador v1
não mudou. `to_v1` é projeção explícita para demo, não executor: recusa TCP, ações
agendadas e duração, pois não podem ser representados fielmente naquele caminho.
Ações agendadas são apenas contratos de habilitação de regras existentes, por índice
zero-based de oportunidade e sequence_id. Não há scheduler nem controle ao vivo.
A composição `legacy_v1` mantém RNG/ordem originais; seeds por mecanismo permanecem
para uma versão posterior, pois introduzi-las agora mudaria os eventos reproduzidos.

## Identidade

Coleta versão do pacote, Python, OS, arquitetura, UTC, commit/tree Git, dirty e hashes
SHA-256 de pacote, testes, configs, pyproject, requirements e ferramenta de aceitação.
Git ausente, timeout ou raiz sem repositório produz indisponibilidade explícita,
sem inventar SHA. Arquivos ignorados pelo Git não entram em dirty, mas os arquivos
relevantes enumerados ainda são hashados. Falhas de leitura de arquivos são erros,
não ausência silenciosa de evidência. Coleta não é snapshot atômico contra edições
concorrentes de fontes; execute sobre checkout estável. Não há lock/durabilidade.

A versão do aplicativo permanece 0.1.0, pois não foi publicada release v0.2 completa.
Schema 2 identifica contratos novos. O hash calculado pelo runner legado muda ao
adicionar arquivos Python ao pacote; isso é efeito correto da identificação de código,
não mudança do pacote binário.

## Decisões em relação ao plano

| Questão/evidência | Escolha | Impacto |
|---|---|---|
| P1 não deve implementar backend/writer | Contratos separados, sem integrar runners antigos | Novas garantias pertencem à API v2; não se atribuem à CLI v1 |
| Contratos pequenos não requerem Qt/Pydantic | Biblioteca padrão e validador restrito aos tipos efetivamente usados | Zero dependências; validador testado, não é framework genérico nem exportador JSON Schema |
| Plano sugere UUID para Run; identidade não atravessa wire | IDs textuais não vazios fornecidos pelo chamador | Opaque IDs permitem fixtures determinísticas; unicidade global cabe ao futuro controlador |
| Plano propõe seeds independentes | Manter perfil legacy_v1 no adaptador | Reprodução exata; gerador novo exigirá outro perfil de composição |
| Plano prevê Run completa e referências extensas | Campos necessários a P1, com versão e desconhecidos explícitos | Journal, topology detalhada, durabilidade e indexação ficam para P2+ |

O plano original não foi alterado silenciosamente.

## Achados B01 a B14

| Achados | Estado nesta etapa |
|---|---|
| B03, B04, B06, B07, B08, B12 | Apenas caracterizados; sem correção do caminho legado |
| B05 | Caracterizado; contrato v2 separa completed, aprovação e integridade; runner v1 inalterado |
| B09 | Caracterizado; expectativas/criteria separadas de Event observed em v2; métricas v1 inalteradas |
| B10 | Caracterizado; fábrica v2 coleta identidade antes; coleta final v1 permanece |
| B14 | Caracterizado; rejeição corrigida na fronteira nova e importador, sem alterar aceitação antiga |
| B01, B02, B11, B13 | Não corrigidos; fora do foco P1, limites do plano permanecem |

## Verificação

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_p1*.py" -v
python -m tools.acceptance --out logs/p1_aceitacao
```

O terceiro comando inclui o milhão normal acelerado. Usar pasta nova. Testes Git
comparativos podem ser ignorados em distribuição sem Git; fixtures binárias continuam
obrigatórias. Comparação de fontes normaliza apenas CRLF/LF; bytes do wire não têm
normalização. Nenhum dos 33 testes anteriores foi editado.

Resultados finais estão em `P1_VALIDACAO.md`. Sem Windows, GUI, aquisição concorrente,
writer assíncrono, COM, modelos físicos, ESP32/Pi ou HIL nesta entrega.
