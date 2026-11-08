# Reproduzir P3.5A

Usar checkout com histórico completo (o teste P1 confere blobs da v0.1) e CPython
3.12.x. A matriz fixa 3.12.14. Na raiz, criar venv com python -m venv .venv e usar o
Python desse ambiente nos comandos abaixo. O core usa biblioteca padrão.
Cada execução requer um novo diretório de saída para preservar os logs anteriores.

```shell
python -m pip install -r requirements.txt
python -m tools.ci_gate core --out logs/core-01
python -m tools.ci_gate boundary --out logs/boundary-01
python -m tools.ci_gate properties --out logs/properties-01
python -m tools.ci_gate mutants --out logs/mutants-01
python -m pip install -r requirements-gui.txt
```

Para GUI, definir QT_QPA_PLATFORM=offscreen (PowerShell: `$env:QT_QPA_PLATFORM="offscreen"`)
e executar `python -m tools.ci_gate gui --out logs/gui-01`. Exigir quatro testes de janela
executados com zero skips. O workflow ci.yml roda core e GUI em Windows e Ubuntu;
propriedades e matriz de mutantes têm jobs próprios em Ubuntu. Cada job preserva os
arquivos de resultado mesmo após falha. Core rejeita skips e registra P1, P2 incluindo
P2.1, P3 não gráfico, fronteira, counter e estados separadamente.

heavy.yml é manual e chama tools.acceptance_p3, que chama acceptance_p2 e a aceitação
legada de um milhão de frames. Inclui Run v2, replay, testes de recovery e GUI lenta.
O runner hospedado fornece evidência da sua própria plataforma. O gate da estação
física Windows permanece uma execução separada.

As versões Python da GUI e suas dependências ficam em requirements-gui.txt. Para atualizar,
usar venv nova, registrar o resolvedor com pip freeze, revisar os pins e as expectativas
de versão em acceptance_p3, e executar os jobs nas duas plataformas. Os rótulos latest
dos sistemas hospedados variam. Conservar o log do runner junto aos resultados.

## Restaurar a entrega e publicar a branch

Após extrair o ZIP, restaurar o histórico completo e verificar o conteúdo local:

```powershell
git clone -b feature/v02-p35-state-evidence foimu-p35a-full.bundle foimu-testbench
cd foimu-testbench
git bundle verify ../foimu-p35a-full.bundle
git rev-parse HEAD 'HEAD^{tree}'
```

Conferir com release.json do ZIP. A autorização para publicação dos materiais IEAv,
inclusive trechos de firmware no histórico, está EXTERNAL_PENDING. Após a liberação
do conteúdo e com credencial de escrita no repositório de destino, executar:

```powershell
git remote add github https://github.com/artorias09/foimu-testbench-v1.git
git push github HEAD:refs/heads/feature/v02-p35-state-evidence
git fetch github refs/heads/feature/v02-p35-state-evidence:refs/remotes/github/feature/v02-p35-state-evidence
git rev-parse 'HEAD^{tree}' 'refs/remotes/github/feature/v02-p35-state-evidence^{tree}'
```

Os dois últimos hashes devem coincidir. Conferir os jobs para o SHA publicado e preservar
os artefatos de Actions antes de atualizar G1. Para a integridade do snapshot, conferir
cada SHA-256 listado no manifest.json do gate relativo à pasta desse manifesto.
