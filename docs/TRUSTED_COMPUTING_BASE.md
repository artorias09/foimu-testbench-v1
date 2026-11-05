# Base de confiança por conclusão

O limite começa nos bytes que o RX declara recebidos. Ele termina na saída canônica do
agregador, para uma captura e manifesto identificados pelo chamador. Para verificar:

| Componente necessário | Claim dependente | Falsa confiança se falhar | Proteção executável |
|---|---|---|---|
| Codec de decodificação, Fletcher | Campos e validade digital do candidato | Valor trocado ou frame incorreto aceito | ProtocolTests.test_independent_c_reference e test_every_single_bit_change_rejected |
| StreamParser e LocatedParser | Enquadramento, descarte, spans | Descarta sobreposição ou desloca localização | test_truncated_then_valid, mutante E13, conservação em 200 seeds |
| RX, envelope e fila limitada | Ordem, época e bytes entregues ao processamento | Perda silenciosa antes do writer | tests/test_p2_backend.py, E15 |
| Writer raw, hash, índices e confirmação | Evidência preservada até limite declarado | Anunciar dados antes da confirmação em disco | CheckpointOrderingTests, E16, reabertura e adulteração de artefatos |
| Fonte de arquivo e projeção observed | Mesmos bytes, ordem, clock e épocas | Replay usa plano ou cola duas épocas | tests/test_observed_boundary.py, E14 para replay integral |
| Processamento, diagnósticos e counter | Eventos, métricas e interpretação modular | Repetir um incidente ou contar perda exata fictícia | M01–M10, diferencial ao vivo e arquivo |
| Reanálise e seleção canônica | Comparabilidade dos fatos selecionados | Ocultar uma diferença ao comparar | Diferenciais de fonte de arquivo, truth removida e envenenada, T01 |
| Registro de observabilidade e manifesto | Limites explícitos e cobertura obrigatória | Promover heurística ou omitir check requerido | test_heuristic_and_violation, test_structural_conditions_are_detector_relative, M10 |
| Produtor de cada CheckResult/EvidenceRef | Execução do predicado e correspondência entre referência, janela e fato | Referência válida em estrutura mas fabricada em conteúdo | Contrato, verificação de hash na entrada e diferencial disponível; cada futuro produtor exige ensaio próprio |
| Agregação e serialização | Estado da raiz, limites e cobertura | Verde por ausência de eventos ou por filho opcional | E01–E12, propriedades e comparação de bytes |

O shutdown entra na base de confiança da conclusão de integridade final (E17). O encoder
sintético e o simulador geram estímulos. Para a claim observed sua saída é apenas entrada.
A auditoria integral e a validação contra truth têm dependências adicionais em RunReader,
manifesto completo e oráculo. GUI, IPC e rendering apenas apresentam resultados e ficam
fora da TCB observed. O modelo pressupõe runtime Python, sistema de arquivos, implementação
SHA-256 e referências de origem confiáveis. Durabilidade em perda de energia, exatidão
do relógio físico e autenticidade do hardware continuam fora da evidência deste gate.
