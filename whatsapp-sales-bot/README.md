# 🤖 Robô de Vendas para WhatsApp

Robô que automatiza o dia a dia de quem vende pelo WhatsApp: mostra o catálogo,
monta o carrinho, fecha o pedido, envia a chave Pix, avisa o vendedor e mantém o
cliente atualizado sobre o status da entrega. Tudo pela **API oficial do WhatsApp
(Cloud API da Meta)**, sem risco de banimento do número.

Feito em **Python + Flask + SQLite**. Dá para hospedar no Render, Railway ou Oracle Cloud.

## ✨ O que ele faz

### Para o cliente
| Digita | O robô faz |
|---|---|
| `oi` / `menu` | Mostra o menu com as opções |
| `1` | Catálogo com preços e aviso de "últimas unidades" ou "esgotado" |
| `add P01 2`, `2x P01` ou só `P01` | Coloca no carrinho (respeitando o estoque) |
| `2` | Mostra o carrinho com subtotal e taxa de entrega |
| `remover P01` / `limpar` | Edita o carrinho |
| `3` | Fecha o pedido: pede o endereço (ou `retirada`) e envia a chave **Pix** |
| `4` | Mostra os últimos pedidos e o status de cada um |
| `5` | Chama um atendente humano (o robô fica em silêncio até o vendedor liberar) |
| `6` | Horário de funcionamento, Pix e taxa de entrega |
| *envia foto/arquivo* | Confirma o recebimento (ex: comprovante) e avisa o vendedor |

### Para o vendedor (pelo próprio WhatsApp, com `#`)
| Comando | O que faz |
|---|---|
| `#ajuda` | Lista todos os comandos |
| `#produto P01 \| Bolo de pote \| 12,90 \| 20` | Cria ou edita um produto (estoque opcional) |
| `#estoque P01 15` / `#estoque P01 livre` | Ajusta o estoque ou desliga o controle |
| `#remover P01` | Tira o produto do catálogo |
| `#pedidos` / `#pedidos novo` | Lista pedidos (todos ou por status) |
| `#pedido 12` | Detalhes do pedido |
| `#status 12 enviado` | Muda o status **e avisa o cliente automaticamente** |
| `#resumo` / `#resumo semana` / `#resumo mes` | Faturamento, ticket médio, mais vendidos e estoque baixo |
| `#responder 5511999998888 texto` | Responde o cliente pelo número do robô |
| `#bot 5511999998888` | Devolve o cliente ao atendimento automático |

Status disponíveis: `novo`, `confirmado`, `preparando`, `enviado`, `entregue`, `cancelado`.
Ao cancelar, o estoque volta automaticamente.

Quando chega um pedido novo, todos os números em `ADMIN_PHONES` recebem um aviso
com os itens, o total, o endereço e um link `wa.me` para falar com o cliente.

## 🧪 Teste em 1 minuto (sem conta da Meta)

```bash
cd whatsapp-sales-bot
python -m venv .venv && source .venv/bin/activate   # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python simulate.py
```

O simulador já vem com 3 produtos de exemplo. Digite `oi` para começar,
`/vendedor` para usar os comandos de vendedor e `/cliente` para voltar.

## 🚀 Colocando no WhatsApp de verdade

1. **Crie o app na Meta**: acesse [developers.facebook.com](https://developers.facebook.com/),
   crie um app do tipo *Business* e adicione o produto **WhatsApp**.
2. Em *WhatsApp > Configuração da API*, copie o **Token de acesso** e o
   **ID do número de telefone**. Para produção, gere um token permanente com um
   *Usuário do sistema* no Gerenciador de Negócios.
3. **Configure o `.env`**:
   ```bash
   cp .env.example .env
   # preencha WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, PIX_KEY, ADMIN_PHONES...
   ```
4. **Publique o servidor** (precisa de HTTPS). No Render ou Railway: aponte para
   esta pasta, use `pip install -r requirements.txt` como build e o `Procfile`
   (`gunicorn app:app`) para iniciar. Cadastre as variáveis do `.env` no painel.
   Para testar no seu computador, use `python app.py` + [ngrok](https://ngrok.com/).
5. **Cadastre o webhook** na Meta (*WhatsApp > Configuração*):
   - URL de callback: `https://SEU-DOMINIO/webhook`
   - Token de verificação: o mesmo valor de `WHATSAPP_VERIFY_TOKEN`
   - Assine o campo **messages**
6. Envie `oi` para o número do robô. Pelo seu número de vendedor, cadastre os
   produtos com `#produto`.

> ⚠️ **Banco de dados:** o SQLite fica num arquivo (`vendas.db`). Em hospedagens
> com disco temporário (como o plano grátis do Render), os dados se perdem a cada
> deploy. Use um disco persistente (`DATABASE_PATH=/data/vendas.db`) ou uma VM como a Oracle Cloud.

> ℹ️ **Regra das 24h da Meta:** o robô pode mandar mensagens livres até 24h depois
> da última mensagem do cliente. Avisos de status enviados depois disso precisam
> de um *template* aprovado pela Meta.

## 🗂️ Estrutura

```
whatsapp-sales-bot/
├── app.py            # Servidor Flask: webhook da Meta (verificação, assinatura, deduplicação)
├── simulate.py       # Simulador de conversa no terminal
├── bot/
│   ├── config.py     # Variáveis de ambiente
│   ├── db.py         # SQLite: produtos, clientes, carrinho e pedidos
│   ├── handlers.py   # Toda a lógica de conversa (cliente e vendedor)
│   └── whatsapp.py   # Envio de mensagens e leitura do webhook (Cloud API)
└── tests/            # Testes automatizados (pytest)
```

A lógica de conversa (`handlers.py`) não depende do WhatsApp: recebe
`(telefone, texto)` e devolve as mensagens a enviar. Por isso dá para testar tudo
sem internet e, no futuro, reaproveitar o mesmo robô no Telegram ou Instagram.

## ✅ Testes

```bash
pip install -r requirements-dev.txt
pytest
```

## 💡 Ideias para evoluir
- Botões e listas interativas do WhatsApp no lugar dos números do menu
- Geração de Pix copia-e-cola / QR Code com o valor do pedido
- Painel web para acompanhar os pedidos
- Lembrete automático de carrinho abandonado (usando templates)
- Respostas com IA para dúvidas fora do menu
