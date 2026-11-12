# Status do projeto — FO-IMU Testbench v0.2

Atualizado para a preparação P3.5B.

## Resumo executivo

Estado atual:

```text
P3.5A COMPLETAMENTE APROVADA
P3.5B PREPARAÇÃO APROVADA
G5 AGUARDANDO DADOS IEAv
```

A bancada virtual está funcional de ponta a ponta e possui mecanismos de replay, recovery, GUI, diagnóstico, fronteira `truth/observed`, semântica formal de counter e evidência, corpus dourado e mutation testing curado.

A confiança atual é **interna/digital**. A conformidade com a FO-IMU física permanece externa e pendente.

## Baselines

### P3.5A

- branch: `feature/v02-p35-state-evidence`
- HEAD: `eeed2dd210e87ca3999422ce5d19c159bc3646cb`
- tree: `fb4f89ed9a5d805cd015f277105611b903d997c6`

### P3.5B preparation

- branch: `feature/v02-p35b-preparation`
- HEAD: `512c3c010c58a535a92424b2429937140ddd3e75`
- core diff contra P3.5A: vazio

## Gates

| Gate | Estado | Escopo |
|---|---|---|
| G0 | `passed` local | identidade/rastreabilidade local |
| G1 | `passed` | CI Linux + Windows + GUI executado com zero falhas/skips inesperados |
| G2 | `passed` local | fronteira `truth/observed` |
| G3 | `passed` local | propriedades, counter, estados/evidência e corpus |
| G4 | `passed` local | 28 mutantes curados |
| G5 | `EXTERNAL_PENDING` | ancoragem contra dados reais IEAv |

G1 foi executado em GitHub Actions no commit `196cb8825e1d82f62d0d6bd7939bcbcf19653034`: Ubuntu (CPython 3.12.16) e Windows (CPython 3.12.10), com core 158/158, 4/4 testes Qt e suíte completa 162/162 com GUI em ambas as plataformas.

## Evidência local consolidada

### Suíte

```text
162 discovered
158 passed
0 failed
4 Qt skipped quando dependências gráficas não estão disponíveis
```

Core local sem GUI:

```text
158/158
0 skips
```

### Grupos direcionados

- P1: 31/31
- P2/P2.1: 47/47
- P3 sem janela: 18/18
- truth boundary: 11/11
- counter: 8/8
- state/evidence: 9/9
- corpus: 5/5

### Propriedades

- conservação: 200 seeds
- 1.854.905 bytes
- 12.801 frames aceitos
- 0 violações
- 25.600 transições de counter exercitadas
- 2.000 árvores de evidência exercitadas

### Mutantes

```text
28 killed
0 survived
0 invalid
```

## P3.5B — preparação de ancoragem externa

O procedimento foi congelado antes da abertura de qualquer captura real.

Inclui:

- manifesto de captura;
- SHA-256 de entrada;
- política de não modificar o raw original;
- schema de divergência;
- expectativas E1–E6 pré-registradas;
- decisões G5 por escopo;
- política de dados externos;
- dry-run com corpus sintético.

O dry-run usou o caso de checksum corrompido e confirmou:

- 159 bytes de entrada;
- 2 frames aceitos;
- 1 candidato rejeitado por checksum;
- 53 bytes descartados;
- 1 ressincronização;
- divergência D-01 preservada como `UNKNOWN` quanto à causa apenas olhando os bytes;
- hashes canônicos coincidentes com o corpus congelado;
- raw original inalterado antes/depois da análise.

## Hipóteses externas congeladas

Para a unidade real, continuam como `HYPOTHESIS`:

- E1: frame candidato de 53 B;
- E2: header `A0 A0`;
- E3: counter uint8;
- E4: Fletcher legado;
- E5: taxa nominal ~100 Hz;
- E6: campos multibyte little-endian.

Nenhuma delas deve ser convertida em fato físico apenas porque o simulador e o parser concordam entre si.

## Claims atualmente permitidos

Podemos afirmar que, no ambiente virtual testado:

- o protocolo implementado é processado de forma reproduzível;
- o parser incremental conserva/accounta bytes segundo os invariantes testados;
- replay e reanálise preservam a evidência observada dentro do escopo definido;
- `truth` e `observed` possuem fronteira estrutural testada;
- o diagnóstico de counter evita atribuição exata de perda em saltos ambíguos;
- estados/evidências exigem cobertura explícita para conclusões positivas;
- os mutantes curados demonstram que classes conhecidas de regressão são detectadas;
- o procedimento de ingestão externa pode ser executado sem modificar a captura original.

## Claims ainda proibidos

Ainda não podemos afirmar:

- conformidade da FO-IMU física com o layout de 53 B;
- checksum real da unidade instalada;
- taxa real de recepção de 100 Hz sem timeline verificável;
- calibração/escala física dos campos;
- precisão, bias, drift ou estabilidade metrológica da FO-IMU;
- sincronismo físico entre IFOG, ACC, MEMS e temperatura;
- comportamento do transporte físico/HIL ainda não integrado.

## Pendências externas atuais

### Publicação / governança

A autorização de publicação de material histórico derivado de firmware IEAv continua separada da aprovação técnica da P3.5A. A aprovação de G1 não autoriza tornar capturas ou firmware externos públicos.

### G5

Faltam capturas reais e metadados da unidade instalada.

O primeiro conjunto desejado é:

- C1: estática;
- C2: power-on;
- C3: movimento conhecido posteriormente;
- C4: reconexão opcional e apenas se autorizada.

## Próxima decisão técnica

Não iniciar P4 para substituir G5.

O próximo ganho de confiança vem de **dados reais**. A primeira análise deve ser estrutural e cega, sem modificar o parser para acomodar a captura.
