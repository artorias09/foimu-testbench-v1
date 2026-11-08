# Recepção e primeira leitura G5

1. Antes de abrir os dados, registrar commit do pré-registro, perfil, versão dos schemas,
   pipeline e tabela de comparação. Registrar escopo autorizado e custodiante.
2. Receber o bruto na área privada. Antes de copiar ou decodificar, registrar SHA-256,
   tamanho e horário de recebimento UTC. Comparar com hash da origem, se disponível;
   divergência de hash interrompe a ingestão até nova transferência. Preservar atributos
   do original, restringir escrita quando permitido. Nunca editar o original.
3. Preencher capture.manifest.json conforme capture/capture.schema.json, com origem,
   operador, firmware (tipo de hash informado pela origem), revisão, baud em bit/s,
   transporte, conversor, duração prevista em segundos, condição, orientação e notas.
   Usar unknown em dados desconhecidos. Hash, tamanho e horário de recebimento são medidos.
4. Em workspace privado criar external_corpus/{C1,C2,C3,C4}. Para cada aquisição usar
   uma pasta nova dentro do tipo, com capture.manifest.json, raw/, analysis/ e divergences/.
   Copiar o bruto para raw/wire.bin e reverificar tamanho/hash antes de análise. Registrar
   e verificar também sidecars originais de tempo/época quando existirem. Restringir escrita
   em raw/. Se houver interrupção ou parcial, preservar e identificar o estado.
5. Executar a análise exclusivamente sobre a cópia verificada. Registrar comando, versão,
   hashes de entrada/saída e cobertura. Recalcular os hashes do original e da cópia ao fim.

| Aquisição | Meta | Registro |
|---|---|---|
| C1 estática | ≥10 min, parada, todos os canais ativos, configuração estável | Orientação, janelas em regime, frequência aparente e estabilidade digital |
| C2 boot | power-on até ≥60 s | Marcar energização, primeiro counter, sentinelas, enquadramento e passagem ao regime |
| C3 movimento | 2–5 min por eixo ou sequência anotada | Ordem, sentido, duração, posições aproximadas e correspondência qualitativa dos canais |
| C4 reconexão | Opcional, com autorização operacional | Marcas externas de desconexão/retorno e épocas documentadas |

## Ordem de análise congelada

Contar ocorrências A0 A0 (inclusive sobrepostas e dentro do payload) e seus offsets.
Em seguida alimentar os bytes no parser atual e usar o Fletcher e a política de counter
da baseline. O scanner apenas localiza assinaturas; candidatos efetivamente examinados
pelo parser = aceitos + checksum_candidate_rejected. Preservar spans [início,fim),
frames aceitos/rejeitados, mismatches, bytes descartados, ressyncs, ambiguidades, lacunas
candidatas, reconexões documentadas e tamanho da cauda pendente imediatamente antes de
finish. Registrar marcador de fim e bytes totais. Um salto de counter sozinho deixa a
reconexão desconhecida. Não usar truth nem instanciar o simulador.

Com timeline compatível e referenciada, gerar os quatro arquivos de ObservedCanonicalV1
pela API documentada em TRUTH_BOUNDARY.md. Timeline externa exige verificar offsets,
relógio, unidades, leituras, épocas e hashes antes da projeção. Se houver somente wire,
executar scanner e parser em ordem de bytes, registrar métricas temporais e canonical
temporal como indisponíveis. Não fabricar chunks com tempos físicos ou supostas épocas.

## Versão, comparação e decisão

Confrontar assinaturas, distâncias, offsets e checksum em múltiplas janelas, cruzar os
campos com o consumidor independente e pedir identificação de firmware. Frames aceitos
isolados deixam a revisão indeterminada. Classificar byte/bit pattern antes de conversão:
acc_x/y/z/tap são contagens uint16 raw; IFOG, MEMS e temperatura permanecem campos
digitais até confirmar unidade e escala. Para floats conservar bytes e padrão de bits.

Enviar o mesmo SHA-256, nas condições autorizadas, ao operador do consumidor LabVIEW/VISA
ou logger independente. Solicitar exportação tabular por campo e offset, versão e política
de conversão. Colunas congeladas da comparação:

```csv
frame_index,byte_span,field,testbench_raw,independent_raw,equal,notes
```

Índices de frame começam em 0; alinhar pelo span no mesmo wire antes de comparar. Para
saída ausente usar unknown. Registrar diferenças em divergences/ segundo divergence.schema.json.
Nos intervalos [a,b) exigir b>a. Evidência identifica arquivo, hash, versão e janela.

G5 emite uma linha por escopo (framing, checksum, counter, ifog_digital_layout,
acc_digital_layout, mems_digital_layout, temperature_digital_layout, receive_rate,
physical_scale). Cada linha contém status (passed, blocked, external_pending ou refuted),
referências de evidência, IDs de divergência, cobertura e premissas. Passed exige evidência
positiva e tratamento das diferenças relevantes. UNKNOWN bloqueia apenas os escopos
dependentes. Registrar denominadores e taxas conforme HW_CAPTURE_EXPECTATIONS.md.
O gate estrutural trata contrato digital. Precisão, simultaneidade, calibração, latência
física e desempenho aeroespacial exigem ensaios específicos.

Diante da condição LAYOUT_HYPOTHESIS_REFUTED do pré-registro, interromper análise que
depende do perfil, preservar bytes e replanejar antes de propor qualquer mudança.
