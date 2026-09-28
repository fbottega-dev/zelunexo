# Próximas rodadas do Zelunexo

A versão 1.1.0 já entrega o fluxo principal: analisar uma pasta, consultar o histórico e exportar resultados. As propostas abaixo são melhorias futuras, em ordem de prioridade. Elas ainda não estão implementadas e não são necessárias para experimentar o projeto atual.

Cada rodada deve resolver uma mudança pequena, preservar os arquivos analisados e manter a execução local, sem servidor. Consulte [as decisões](DECISOES.md) e [o guia de estudo](ESTUDO.md) antes de alterar o comportamento.

## 1. Filtrar grupos por bytes redundantes

**Benefício:** ajudar a pessoa a encontrar primeiro os grupos com maior volume de cópias excedentes, sem perder a visão da análise completa. É o exercício pequeno sugerido no README.

Adicionar `--minimo-bytes` aos comandos que geram HTML, com inteiro não negativo e padrão `0`. A regra proposta é mostrar grupos cujos bytes redundantes sejam **maiores ou iguais** ao limite. Para três cópias de 100 bytes, o valor comparado é `(3 - 1) × 100 = 200`, e não 100 nem 300 bytes.

**Critérios de aceite:**

- Um grupo de 200 bytes redundantes aparece com limite 200 e fica oculto com limite 201; valores negativos ou não inteiros são recusados com mensagem clara.
- Sem a opção, o relatório mantém o comportamento atual. Com o filtro, o banco e os dados completos da análise continuam iguais.
- O HTML distingue “Totais da análise” de “Totais dos grupos exibidos”. Busca, filtro de quantidade de cópias e limite em bytes combinam suas condições; os totais exibidos acompanham essa combinação.
- Quando nenhum grupo passar pelos filtros, o relatório mostra uma mensagem de resultado vazio e totais filtrados iguais a zero, preservando os totais gerais.
- A exportação HTML de uma análise salva aplica o mesmo limite sem reler a pasta. O JSON continua contendo os dados completos; a ajuda explica que a opção se aplica ao HTML.

Comece pelo teste de fronteira 200/201 em uma pasta temporária. Depois implemente a seleção dos grupos, os argumentos e a apresentação, nessa ordem. Use o mesmo exemplo para verificar manualmente o relatório.

**Filtros e totais têm momentos diferentes:** `--ignorar` atua durante a análise; uma entrada excluída não entra nos totais dos arquivos analisados. Busca e filtros do relatório atuam sobre dados já salvos; ocultar um grupo não apaga registros nem muda os totais gerais. Os totais filtrados descrevem apenas os grupos visíveis, não todos os arquivos lidos.

## 2. Comparar duas análises do histórico

**Benefício:** mostrar o que mudou entre duas execuções, sem obrigar a pessoa a comparar relatórios manualmente.

Começar com uma comparação por caminho relativo entre dois IDs escolhidos explicitamente. Classificar caminhos como adicionados, removidos ou alterados; considerar alteração a mudança de tamanho ou hash. Uma mudança de nome aparece como remoção e adição nessa primeira versão. Como o banco não guarda uma identidade inequívoca da pasta original, a ajuda deve orientar a comparar análises da mesma pasta.

**Critérios de aceite:**

- Um teste com duas análises controladas cobre um arquivo adicionado, um removido, um alterado e um mantido; os mantidos não entram na lista de mudanças.
- O resultado informa os dois IDs, as datas e os padrões de exclusão usados, para que diferenças de escopo possam ser reconhecidas.
- Se alguma análise for parcial, a comparação destaca essa condição: ausência de um caminho não comprova que ele foi apagado da pasta.
- Um ID inexistente gera erro claro. A comparação usa somente o banco, funciona sem a pasta original e não altera análises anteriores.

## 3. Confirmar grupos com comparação byte a byte

**Benefício:** oferecer uma confirmação adicional de conteúdo idêntico para quem precisa ir além de tamanho e SHA-256, aceitando o custo de ler os candidatos novamente.

Adicionar uma opção explícita à análise para comparar o conteúdo dos arquivos de cada grupo candidato em blocos. O modo padrão permanece igual. O relatório deve distinguir a identificação por hash da confirmação adicional realizada na nova opção.

**Critérios de aceite:**

- Arquivos idênticos são confirmados, e um teste com candidatos de mesmo tamanho e hash simulado, mas conteúdo diferente, demonstra que a confirmação rejeita o falso agrupamento.
- A leitura usa blocos, sem carregar arquivos inteiros na memória. Uma falha de acesso ou alteração detectada nessa etapa aparece como ocorrência, deixa a análise parcial e não recebe o rótulo de confirmação concluída.
- A confirmação registrada permanece visível ao exportar o histórico, sem reler a pasta. Históricos anteriores continuam consultáveis e não recebem confirmação retroativa.
- A ajuda explica que a confirmação aumenta a leitura de disco e continua sem oferecer um snapshot atômico de uma pasta em edição.

## Rotina curta para cada rodada de commits

1. **Entender o ponto de partida.** Rode `git status --short`, `git diff`, `git diff --cached` e `git log -5 --oneline`. Separe alterações já existentes das que você pretende fazer e escolha uma única correção ou melhoria.
2. **Reproduzir antes de corrigir.** Para um bug, prepare dados fictícios mínimos, anote comando, resultado esperado e resultado observado. Para uma melhoria, escreva o critério de aceite. Quando houver lógica nova, crie um teste que falhe pelo motivo esperado antes da mudança.
3. **Implementar e verificar.** Execute o teste do caso alterado e, antes do commit, `python -m unittest discover -s tests -v` e `python -m compileall -q zelunexo tests`. Se mudar o HTML, abra o relatório com dados fictícios e confira filtros, estado vazio e tela estreita. Se mudar empacotamento, siga também a verificação do wheel descrita no README.
4. **Revisar o que será entregue.** Confira novamente os diffs e o status. Atualize a documentação do comportamento e inclua no commit apenas os arquivos da rodada, sem bancos pessoais ou relatórios particulares. Use uma mensagem que explique a mudança concreta.
5. **Conferir a CI após o envio.** No [GitHub Actions](https://github.com/fbottega-dev/zelunexo/actions), abra a execução correspondente ao SHA do commit enviado e confira todos os jobs. Registre falhas, testes pulados e limitações relevantes. Workflow existente, execução pendente ou aprovação de outro commit não comprovam aprovação desta rodada.

Este documento descreve propostas e uma rotina de trabalho; não registra a execução de testes nem a aprovação de CI. As verificações da entrega atual ficam em [VALIDACAO.md](VALIDACAO.md).
