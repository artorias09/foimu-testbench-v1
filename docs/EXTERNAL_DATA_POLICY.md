# Custódia das capturas externas

Usar workspace de acesso controlado e backup autorizado pelo IEAv, preferencialmente
fora do clone. O diretório external_corpus na raiz está ignorado pelo Git como proteção
adicional. A equipe deve confirmar permissões de leitura e escrita no sistema operacional.
O atributo read-only auxilia a prevenção de alterações acidentais. SHA-256 verifica a
identidade dos bytes em relação à referência conservada; registrar separadamente a origem.

Registrar authorization_scope para recebimento, armazenamento, análise, compartilhamento
e publicação. Na ausência de informação usar unknown e esclarecer antes do uso que depende
de autorização. Submeter a autorização específica também firmware, metadados, hashes,
logs e resultados derivados antes de qualquer envio a Git, CI ou serviços externos.
O histórico do projeto mantém IEAV_PUBLICATION_AUTHORIZATION = EXTERNAL_PENDING.
