# Estudar e apresentar o Rastro

## Executar um caso pequeno

Na raiz do repositório, com Python 3.12 ou superior, execute os comandos abaixo. A pasta `demo` e os arquivos HTML devem ser destinos novos. O banco e as saídas ficam fora da pasta analisada.

```sh
python -m rastro demo ./demo
python -m rastro analisar ./demo --banco ./.rastro/historico.sqlite3 --html ./relatorio.html
python -m rastro historico --banco ./.rastro/historico.sqlite3
python -m rastro exportar 1 --banco ./.rastro/historico.sqlite3 --saida ./copia.html
python -m rastro exportar 1 --banco ./.rastro/historico.sqlite3 --saida ./copia.json --formato json
```

O ID `1` pressupõe um banco novo. Se já houver histórico, use o identificador mostrado pelo comando `historico`. Abra `relatorio.html` no navegador e compare os grupos apresentados com os arquivos fictícios da pasta.

Para praticar exclusões, gere outra saída:

```sh
python -m rastro analisar ./demo --banco ./.rastro/historico.sqlite3 --html ./relatorio-filtrado.html --ignorar "backup/*"
```

## Acompanhar o fluxo no código

1. Comece pelo ponto de entrada `rastro/__main__.py`: veja como os argumentos chegam aos comandos.
2. Localize a travessia da pasta e o cálculo de SHA-256. Entenda a diferença entre caminho, conteúdo, tamanho e identidade de um arquivo.
3. Acompanhe o agrupamento por tamanho e hash e refaça o cálculo `(quantidade - 1) × tamanho` para um grupo do exemplo.
4. Procure o código que grava e consulta o SQLite. Relacione uma análise com seus arquivos e com as ocorrências registradas.
5. Leia a geração do relatório e verifique como nomes de arquivos viram texto HTML sem serem interpretados como marcação.

## Fundamentos para explicar

| Conceito | Aplicação no projeto |
| --- | --- |
| Leitura em blocos | Calcula o hash sem carregar todo o conteúdo de cada arquivo de uma vez. |
| SHA-256 | Produz uma assinatura do conteúdo; nomes iguais não bastam para identificar cópias. |
| Dicionários e agrupamento | Reúnem arquivos que compartilham a chave tamanho/hash. |
| Banco relacional | Associa arquivos a uma análise e permite consultar o histórico. |
| Tratamento de erros | Distingue erro de comando, leitura parcial e execução completa. |
| Testes automatizados | Exercitam comportamento com arquivos temporários e entradas controladas. |

Leia também [as decisões e limitações](DECISOES.md), especialmente hardlinks, alterações durante a leitura e a diferença entre bytes lógicos e espaço físico.

## Verificar o comportamento

```sh
python -m unittest discover -s tests -v
python -m compileall -q rastro tests
```

A configuração de CI executa os testes e um fluxo com dados fictícios em Windows e Ubuntu, usando Python 3.12, 3.13 e 3.14. A existência do workflow não comprova aprovação: confira o resultado da execução correspondente ao commit apresentado.

Experimente também copiar um arquivo com outro nome, criar um arquivo vazio, alterar conteúdo sem mudar o nome e tentar gerar um relatório num caminho já existente. Antes de cada execução, escreva o resultado esperado e depois compare. Para simular falhas de acesso, use apenas dados temporários e considere que permissões variam entre sistemas operacionais.

## Roteiro de apresentação

Explique o problema em uma frase: “Quero enxergar o que ocupa uma pasta e quais arquivos têm conteúdo repetido, antes de decidir como organizá-la.” Mostre a pasta fictícia, execute a análise, abra o relatório e exporte uma análise do histórico.

Depois, escolha um grupo de duplicados e percorra o caminho completo: descoberta dos arquivos, leitura em blocos, agrupamento, persistência e apresentação. Explique uma falha possível e o comportamento que o usuário recebe. Finalize apontando uma limitação concreta e a mudança que seria necessária para resolvê-la.

Sobre autoria, descreva o processo com precisão: “O projeto foi desenvolvido com apoio de IA, sem partir de uma aplicação pronta.” Acrescente apenas o que você realmente fez, revisou e consegue explicar. Não atribua a si decisões que ainda não compreende; use o código e os testes para estudá-las antes de apresentar o trabalho.

Perguntas úteis para praticar:

- Por que comparar tamanho e hash, em vez de apenas o nome?
- O que acontece se um arquivo mudar enquanto está sendo lido?
- Por que duas entradas de hardlink não representam duas cópias físicas?
- Por que o banco não pode ficar dentro da pasta analisada?
- Como consultar ou exportar uma análise quando a pasta original não existe mais?
- Qual é o custo de recalcular todos os hashes e quando um cache seria justificável?
