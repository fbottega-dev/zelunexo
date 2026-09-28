# Histórico de versões

## 1.1.0 — 28/09/2026

Versão que encerra o escopo inicial do projeto: análise por conteúdo, histórico local e relatórios offline. Esta entrega consolida as correções feitas após a primeira implementação.

- Padrões terminados em `/` ignoram somente diretórios, incluindo nomes com glob.
- IDs de exportação fora do intervalo do SQLite são recusados com mensagem clara.
- Falhas de exportação limpam a saída incompleta criada pela tentativa, quando o sistema permite.
- O comando instalado e `python -m zelunexo` emitem texto em UTF-8, inclusive quando a saída é redirecionada.
- A criação do banco reverte tabelas e metadados juntos em caso de falha.
- A validação e a criação do banco compartilham um bloqueio para evitar erros durante gravações concorrentes.
- A CI valida o wheel instalado fora do checkout e disponibiliza o pacote como artefato.

O esquema SQLite continua na versão 1; históricos existentes são compatíveis. O nome atual é Zelunexo. Para históricos do antigo Rastro, informe o caminho anterior com `--banco .rastro/historico.sqlite3`.

Os limites permanecem explícitos: comparação por tamanho e SHA-256, estimativa lógica de bytes, ausência de exclusão automática e ausência de snapshot atômico da pasta. Veja o README e o guia de estudo antes de ampliar o escopo.
