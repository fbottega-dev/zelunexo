# Decisões do Zelunexo

## Problema e escopo

O Zelunexo ajuda a entender uma pasta antes de organizar arquivos: mostra tamanhos e grupos de conteúdo repetido, gera um relatório HTML e guarda o resultado no SQLite. A ferramenta não apaga nem move os arquivos analisados. A estimativa de duplicação serve para orientar uma revisão manual.

O código foi criado neste projeto, com apoio de IA, sem clonar uma aplicação pronta. A biblioteca padrão do Python fornece os componentes principais: `pathlib`/`os`, `hashlib`, `sqlite3`, `argparse`, `json` e `unittest`. Python 3.12 é a versão mínima.

## Como uma duplicação é identificada

Cada arquivo legível recebe um SHA-256 calculado em blocos de 1 MiB. Dois caminhos entram no mesmo grupo quando têm tamanho e hash iguais. A implementação não usa um cache de hashes: cada análise volta a ler os arquivos, o que simplifica a correção e permite observar alterações entre execuções.

O hash é uma evidência prática de conteúdo igual, não uma comparação byte a byte. A possibilidade de colisão existe, embora seja extremamente pequena. Arquivos vazios ficam fora dos grupos de duplicados; múltiplos caminhos para o mesmo hardlink não são tratados como cópias independentes.

Para um grupo de `n` cópias de `s` bytes, o potencial lógico é `(n - 1) × s`. Isso não mede espaço físico recuperável: compressão, arquivos esparsos, deduplicação do sistema de arquivos e escolhas sobre quais cópias manter mudam o resultado real.

## Leitura e limites

- Links simbólicos e junctions não são seguidos. Isso evita sair da raiz escolhida e percorrer ciclos.
- Metadados são conferidos antes e depois da leitura para detectar alterações comuns durante o cálculo. Essa conferência não oferece um snapshot atômico nem impede todas as condições de corrida.
- Falhas de acesso aparecem no resultado como ocorrências. Uma análise parcial permanece consultável e devolve o código de saída `3`.
- Padrões `--ignorar` podem ser repetidos. Exclusões e caminhos pulados devem ser considerados ao interpretar os totais.
- O custo principal é ler todo o conteúdo: o tempo cresce com o volume de bytes. Os registros dos arquivos também consomem memória; o projeto se destina a pastas de uso pessoal, não a inventários de escala ilimitada.

## Persistência e saídas

O SQLite guarda análises e arquivos em tabelas relacionadas. Ocorrências, caminhos pulados e padrões de exclusão ficam como listas JSON nos registros das análises. Essa escolha mantém os dados consultáveis sem exigir servidor de banco ou instalação de dependências.

O cabeçalho `application_id` identifica o banco como Zelunexo e `user_version` registra a versão do esquema. A aplicação recusa um banco identificado como pertencente a outro programa. Cada análise é gravada em uma transação: se um arquivo falhar na gravação, a análise inteira é revertida. Consultas e exportações abrem o SQLite em modo somente leitura.

O banco e o relatório devem ficar fora da pasta analisada para que a ferramenta não leia as próprias saídas. O destino HTML é criado exclusivamente: um arquivo existente não é sobrescrito. O comando `exportar` usa os dados salvos e não precisa reler a pasta original.

Uma análise concluída devolve `0`; um erro de comando ou de execução impede a entrega normal e devolve `2`; ocorrências durante a leitura resultam em `3`. Scripts devem verificar o código de saída além de ler o relatório.

## Escolhas de produto

Uma CLI torna a execução reproduzível e fácil de integrar a scripts. O relatório HTML fornece uma visão visual que pode ser aberta sem iniciar um servidor. A ausência de exclusão automática mantém a decisão sobre os arquivos com a pessoa responsável por eles.

O histórico contém nomes e caminhos de arquivos. Não deve ser publicado com informações pessoais. Uma demonstração deve usar a pasta fictícia criada por `python -m zelunexo demo`, não uma pasta pessoal.

## Evoluções possíveis

Comparar duas análises, adicionar processamento progressivo para pastas muito grandes e oferecer verificação byte a byte de grupos candidatos são próximos passos possíveis. Um cache exigiria uma política de invalidação explícita; exclusão de arquivos exigiria um projeto separado de confirmação, recuperação e auditoria.
