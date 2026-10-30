# Validação P1

Data: 30/10/2026. Baseline: `52531eaa16bb111cdb6ad862c8fd037d6ead0977`.
Branch: `feature/v02-p1-contracts`. Nenhum merge.

## Resultados executados

- Suíte completa: 64 testes aprovados, sem skips neste ambiente.
- 33 testes legados preservados e aprovados.
- 31 testes P1: 11 de caracterização e 20 de contratos/compatibilidade.
- `python -m tools.acceptance`: aprovado, incluindo 1.000.000 de pacotes.
- Normal: 1.000.000 aceitos, zero lacunas candidatas, checksum e framing; pico de buffer 53 bytes.
- Todas as configurações v1 existentes importadas, serializadas/reabertas e projetadas de volta sem mudança de configuração; 300 emissões comparadas por configuração, incluindo bytes e tempos.
- Tipos/chaves/versões inválidos, bool como inteiro, NaN/Inf em JSON, intervalos inválidos, ações sem regra e incompatibilidades de clock recusados.
- Todas as combinações de origem/destino da tabela de ciclo de vida exercitadas.
- Golden e recuperação após corrupção comparados em todas as 52 divisões do pacote.
- Identidade com Git limpo/sujo e sem Git exercitada em diretório temporário.
- Arquivos de implementação legada comparados com os blobs congelados; nenhuma mudança.
- 522 arquivos originais IEAv verificados por SHA-256; nenhuma alteração.

O runner de aceitação mantém as limitações B06. Por isso o resultado não se apoia
apenas em `passed=true`: testes/contagens foram examinados e os resultados dos
cenários conferidos contra os oráculos da baseline. A caracterização de B06 usa
mocks locais para demonstrar o problema, não modifica o ensaio real de aceitação.

Ambiente: Python 3.12.14; Linux-6.18.57-x86_64-with-glibc2.39. Tempo total da aceitação: 23.518 s.

Hash das fontes Python testadas: `5a78fc89ec79a095dac99fa240014b32da5c2cb1bef86e4e72d7fa99fbc03c29`.

| Cenário | Aceitos | Lacunas | Checksum candidatos | Framing | Resync |
|---|---:|---:|---:|---:|---:|
| checksum | 901 | 100 | 101 | 100 | 100 |
| loss | 901 | 100 | 0 | 0 | 0 |
| truncate | 901 | 100 | 101 | 100 | 100 |
| header | 901 | 100 | 1 | 100 | 100 |
| byte | 901 | 100 | 101 | 100 | 100 |
| jitter | 1001 | 0 | 0 | 0 | 0 |

## Comandos

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_p1*.py" -v
python -m tools.acceptance --out <pasta-nova>
git diff --check
```

A aceitação completa já inclui o milhão; não é necessário repeti-lo como um ensaio
separado para satisfazer o mesmo gate. O ajuste posterior de teste para tolerar
CRLF/LF em fontes foi validado pela suíte P1; não alterou código de runtime ou wire.

## Regressões e limites

Nenhuma regressão encontrada nos testes executados. O hash de fontes mudou pela
adição dos módulos; bytes e regras legadas não mudaram. Não foram executados Windows,
ensaio real de oito horas, profiling prolongado ou hardware. Nenhuma conclusão sobre
fidelidade elétrica, física óptica ou requisitos de voo.

B03/B04/B06/B07/B08/B12 permanecem no legado, caracterizados. B05/B09 têm contratos
v2 que separam estados/expectativas; B10 tem coleta prévia via fábrica de Run; B14 é
rejeitado na nova entrada. Isso não corrige retroativamente a CLI v1. B01/B02/B11/B13
permanecem fora desta implementação. Detalhes, API e decisões em `P1_CONTRATOS.md`.

P1 não contém execução v2, GUI, threads, writer, replay v2, hardware ou campanhas.
P2 não foi iniciado.
