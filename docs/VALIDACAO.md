# Verificações da entrega

## Execução local — 24/09/2026

Windows, Python 3.12.14: 57 testes descobertos, **55 aprovados e 2 pulados**. Os dois casos pulados precisam criar links simbólicos, operação negada pelo Windows neste ambiente. Hardlink real e reparse point simulado foram verificados. `compileall` passou.

O fluxo real criou o acervo fictício, analisou 14 arquivos, encontrou quatro grupos e seis cópias excedentes, salvou o histórico SQLite e exportou HTML e JSON. Os testes também conferem preservação do conteúdo original, rejeição de sobrescrita, rollback da transação e identificação de bancos de outro aplicativo.

No navegador foram conferidos o layout em 1440 e 390 pixels, ausência de rolagem horizontal nessas larguras, busca sem acentos, filtro de três ou mais arquivos, limpeza de busca, expansão e recolhimento. Os estados vazio e parcial foram abertos e inspecionados. As capturas do README são dessa execução real com dados fictícios. A impressão tem estilos e comportamento implementados, mas não houve validação de uma impressão física.

## Revisão do código

A revisão com apoio de IA encontrou e corrigiu duas falhas antes da publicação: identificação insuficiente de bancos SQLite alheios e comparação de `ctime` entre APIs do Windows com significados diferentes. Há testes de regressão para ambas.

## Verificação remota

O workflow executa testes e comandos completos em Ubuntu e Windows, nas versões Python 3.12, 3.13 e 3.14. Os resultados por commit ficam disponíveis em [GitHub Actions](https://github.com/fbottega-dev/zelunexo/actions/workflows/ci.yml). Consulte a execução correspondente; o resultado local acima não substitui o resultado remoto.
