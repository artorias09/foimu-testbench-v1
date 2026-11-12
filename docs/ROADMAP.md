# Roadmap — FO-IMU Testbench v0.2

O roadmap é orientado por **ganho de confiança**, não por quantidade de funcionalidades.

## Concluído

### P1 — contratos e caracterização

- contrato do pacote legado;
- parser incremental;
- caracterização e regressão do baseline;
- invariantes iniciais.

### P2 / P2.1 — backend, persistência e shutdown

- workers separados;
- filas limitadas;
- storage estruturado;
- replay;
- recovery;
- correção do orçamento de shutdown por fase.

### P3 — GUI

- configuração de cenário;
- controle de Run;
- métricas/sinais/eventos;
- localização por bytes/tempo;
- reabertura de relatório;
- independência entre GUI e backend.

### P3.5A — confiabilidade interna do validador

- truth boundary;
- reanálise observed por arquivo;
- counter semantics/reacquisition;
- observability registry;
- state/evidence semantics;
- Trusted Computing Base;
- corpus dourado;
- mutation matrix 28/28;
- preparação de CI.

Estado: **implementada; liberação pendente por G1**.

### P3.5B — preparação de ancoragem externa

- procedimento de ingestão;
- manifests/schemas;
- expectativas E1–E6 congeladas;
- política de dados externos;
- divergências por escopo;
- dry-run de captura externa.

Estado: **preparação aprovada**.

## Próximo gate

### G5 — captura real IEAv

Objetivo: determinar quais hipóteses digitais são sustentadas pela unidade instalada.

Primeiras capturas:

- C1 estática;
- C2 boot;
- C3 movimento conhecido posteriormente;
- C4 reconexão opcional.

G5 é decidido por escopo, não por um booleano global.

## Depois da ancoragem externa

### P4 — análise pós-run / comparação

Só iniciar quando o contrato digital relevante estiver ancorado ou quando os scopes bloqueados estiverem explicitamente aceitos como limitação.

### P5 — fault model ancorado

Substituir falhas puramente hipotéticas por classes observadas/documentadas no sistema real.

### P6 — transporte físico conhecido

Integrar adaptador serial/COM/RS-422/USB conforme a interface confirmada.

### P7 — shadow mode

Observar a FO-IMU real sem controlar o hardware, comparando o caminho do testbench com o software/consumer existente quando disponível.

### P8 — HIL

Somente depois que protocolo, transporte, limites e autorização operacional estiverem estabelecidos.

## Regra de avanço

Não usar uma fase posterior para esconder um gate anterior.

Exemplos:

- P4 não substitui G5;
- HIL não substitui a validação do parser;
- um dashboard bonito não substitui evidência;
- o simulador não valida a conformidade do hardware consigo mesmo.
