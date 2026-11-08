# Precifica Fácil

Calculadora de preço e margem de lucro para quem vende **doces, salgados, bolos,
açaí e marmitas**. A pessoa cadastra o que paga nos ingredientes, monta a receita
e vê na hora o **preço sugerido**, o **lucro por unidade** e se o preço que já
cobra está dando lucro ou prejuízo.

É um único arquivo (`index.html`), sem servidor, sem banco de dados e sem
mensalidade. Funciona no celular e no computador.

## O que o cliente consegue fazer

- **Ingredientes e embalagens:** cadastra o preço pago e o tamanho da embalagem
  (g, kg, ml, L ou unidade). O app calcula o custo por grama/ml/unidade.
  Quando o preço sobe no mercado, ele atualiza aqui e **todos os produtos são recalculados**.
- **Produtos:** monta a receita (ingredientes + quantidade), diz quantas unidades
  rende e quanto tempo leva.
- **Resultado na hora:** custo por unidade, preço sugerido (arredondado para cima),
  lucro por unidade e lucro na receita inteira.
- **Diagnóstico do preço atual:** informando quanto já cobra, o app diz se está
  *na meta*, *abaixo da meta* ou dando *prejuízo*, e quanto precisa aumentar.
- **Ajustes:** margem padrão, taxas da maquininha/iFood, gás/luz/perdas e o valor
  da hora de trabalho.
- **Backup:** gera um texto ou arquivo com todos os dados para guardar ou trocar de aparelho.

Vem com exemplos prontos (brigadeiro, bolo de pote, açaí) e o botão
"Começar do zero" para apagar e usar os próprios dados.

## Como o preço é calculado

```
custo da receita = ingredientes + (ingredientes × % gás/luz/perdas) + (minutos ÷ 60 × valor da hora)
custo por unidade = custo da receita ÷ rendimento
preço sugerido    = custo por unidade ÷ (1 − margem − taxas)
```

A margem é calculada **sobre o preço de venda** (o jeito certo). Margem de 40%
significa que 40% do que o cliente paga é lucro, depois de pagar custos e taxas.

## Como vender na Hotmart ou Kiwify

1. **Hospede o arquivo** (grátis) em um destes:
   - **Netlify Drop:** acesse app.netlify.com/drop e arraste a pasta `calculadora-precos`.
   - **GitHub Pages:** neste repositório, em *Settings > Pages*, publique a branch e
     o app fica em `https://SEU-USUARIO.github.io/REPOSITORIO/calculadora-precos/`.
2. **Crie o produto** na Hotmart/Kiwify como *produto digital* ou *área de membros*.
3. **Entregue o link** do app na área de membros ou no e-mail de compra, com um
   vídeo curto mostrando como usar.
4. Ensine o cliente a **adicionar à tela inicial** do celular (Chrome: menu ⋮ >
   "Adicionar à tela inicial"; iPhone: Compartilhar > "Adicionar à Tela de Início").
   Assim fica parecendo um aplicativo.

### Bom saber antes de vender
- **Os dados ficam no aparelho do cliente** (no navegador). Se ele limpar os dados
  do navegador, perde tudo. Por isso existe o backup, e vale reforçar isso no vídeo.
- **Quem tiver o link consegue usar.** Para um produto de entrada (R$ 19 a R$ 47) isso
  costuma ser aceitável. Se quiser bloquear, o próximo passo é colocar login
  ligado à compra (webhook da Hotmart/Kiwify), o que exige um servidor.
- Para mudar o nome do produto, troque "Precifica Fácil" no `<title>` e no `<h1>` do `index.html`.
