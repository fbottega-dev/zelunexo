# Verificações da entrega

## Fechamento da versão 1.1.0 — 28/09/2026

O pacote wheel foi construído e instalado em um ambiente virtual temporário, fora do checkout, usando Python 3.12.14 no Windows. O executável instalado concluiu os comandos de demonstração, análise, histórico e exportação JSON. O relatório gerado contém CSS e JavaScript incorporados, e tanto o executável quanto `python -m zelunexo` retornaram a versão 1.1.0. A instalação do wheel usou `--no-index --no-deps`.

A verificação foi repetida no fechamento da entrega: **71 testes descobertos, 69 aprovados e 2 pulados** por falta de privilégio para criar links simbólicos no Windows. Passaram `compileall`, `git diff --check` e o comando de construção com isolamento padrão do pip. Um novo fluxo por terminal criou a demonstração em uma pasta com acento, encontrou 14 arquivos, quatro grupos e seis cópias excedentes, consultou o histórico e exportou HTML e JSON.

As capturas existentes de desktop e celular foram inspecionadas. Esta rodada não altera a interface; a abertura do novo HTML local foi bloqueada pela política do navegador da sessão, portanto não houve uma nova validação interativa. Os testes de geração do relatório e a conferência dos recursos empacotados passaram. Uma revisão independente com apoio de IA não encontrou bloqueadores no empacotamento.

A CI está configurada para repetir a construção e essa verificação de instalação nos seis ambientes da matriz, além da suíte de regras. O wheel do job Ubuntu/Python 3.12 só é disponibilizado como artefato após a aprovação das etapas anteriores. A existência dessa configuração não comprova aprovação: confira a execução do commit em [Actions](https://github.com/fbottega-dev/zelunexo/actions). O changelog reúne o escopo concluído e mantém explícitas as limitações; esta versão não promete ausência de bugs nem substitui as verificações futuras de mudanças.

## Validação de IDs, exclusões e concorrência — 27/09/2026

Esta rodada acrescentou seis testes: dois para limites do ID usado em `exportar`, três para padrões de exclusão com barra final e um para a disputa entre duas conexões durante a inicialização do histórico. A cobertura de junctions também foi executada com um padrão de diretório.

Antes das correções, um ID acima do limite do SQLite gerava `OverflowError`, `backup/` não excluía a pasta e a gravação concorrente podia produzir uma falsa rejeição de banco estrangeiro. Os testes reproduziram esses comportamentos e passaram após as mudanças. A disputa de conexões é provocada em um ponto conhecido da leitura, sem depender de temporizadores; também é verificada a nova tentativa após liberação do bloqueio.

Resultado local: **71 testes descobertos, 69 aprovados e 2 pulados** pela restrição de criação de links simbólicos no Windows. Compilação com `compileall` e revisão de whitespace passaram. Os commits têm execuções próprias no Actions.

## Correções — 27/09/2026

Foram reproduzidas e corrigidas duas falhas: o ponto de entrada do comando instalado não configurava UTF-8, e a criação inicial do banco podia deixar tabelas ou metadados incompletos após um erro.

Três testes novos executam ambos os pontos de entrada em subprocessos com saída inicialmente ASCII, verificando ajuda, mensagens de erro e criação de demonstração em caminho com acentos. Outros três verificam rollback durante a criação do esquema e gravação da versão, nova tentativa após falha e compatibilidade com bancos da versão 1.

Na suíte completa local, **65 testes descobertos: 63 aprovados e 2 pulados** pelo privilégio de links simbólicos do Windows. `compileall` e a verificação de whitespace passaram. As verificações remotas por commit permanecem disponíveis no Actions, no link ao final desta página.

## Execução local — 24/09/2026

Windows, Python 3.12.14: 57 testes descobertos, **55 aprovados e 2 pulados**. Os dois casos pulados precisam criar links simbólicos, operação negada pelo Windows neste ambiente. Hardlink real e reparse point simulado foram verificados. `compileall` passou.

O fluxo real criou o acervo fictício, analisou 14 arquivos, encontrou quatro grupos e seis cópias excedentes, salvou o histórico SQLite e exportou HTML e JSON. Os testes também conferem preservação do conteúdo original, rejeição de sobrescrita, rollback da transação e identificação de bancos de outro aplicativo.

No navegador foram conferidos o layout em 1440 e 390 pixels, ausência de rolagem horizontal nessas larguras, busca sem acentos, filtro de três ou mais arquivos, limpeza de busca, expansão e recolhimento. Os estados vazio e parcial foram abertos e inspecionados. As capturas do README são dessa execução real com dados fictícios. A impressão tem estilos e comportamento implementados, mas não houve validação de uma impressão física.

## Revisão do código

A revisão com apoio de IA encontrou e corrigiu duas falhas antes da publicação: identificação insuficiente de bancos SQLite alheios e comparação de `ctime` entre APIs do Windows com significados diferentes. Há testes de regressão para ambas.

## Verificação remota

O workflow executa testes e comandos completos em Ubuntu e Windows, nas versões Python 3.12, 3.13 e 3.14. Os resultados por commit ficam disponíveis em [GitHub Actions](https://github.com/fbottega-dev/zelunexo/actions/workflows/ci.yml). Consulte a execução correspondente; o resultado local acima não substitui o resultado remoto.
