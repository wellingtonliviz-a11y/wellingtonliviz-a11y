# Agendamento Inteligente

Sistema de **agenda online** e preço dos serviços para **manicures, pedicures e nail designers**.
Preço sugerido de venda: **R$ 49,90 por mês** (variável `PLAN_PRICE`).

É vendido pela **Hotmart**, **Kiwify** ou **Asaas** e funciona sozinho, com a mesma base do Precifica Fácil:

1. A cliente compra.
2. A plataforma avisa o sistema (webhook).
3. O sistema cria o login, gera uma senha e manda por e-mail.
4. Ela entra e os dados ficam salvos na nuvem, em qualquer aparelho.
5. Em caso de reembolso, chargeback ou cancelamento, o acesso é bloqueado sozinho (e a página de agendamento sai do ar).

É um sistema separado do Precifica Fácil (outro site, outro banco de dados, outro produto nas plataformas).

## O que tem no sistema

| Página | Para quê |
|---|---|
| `/` | Página de vendas (visitante) ou o sistema (cliente logada) |
| `/entrar`, `/esqueci`, `/conta` | Login, nova senha e minha conta |
| `/demo` | Demonstração grátis, sem login, com agenda de exemplo |
| `/a/nome-do-espaco` | Página pública de agendamento de cada manicure |
| `/admin` | Seu painel: clientes, reembolsos, reenviar senha, bloquear, criar cortesia |
| `/webhooks/hotmart`, `/webhooks/kiwify` e `/webhooks/asaas` | Endereços que você cadastra nas plataformas |
| `/termos` e `/privacidade` | Termos de uso e Política de privacidade (LGPD) |

Abas do sistema:

- **Agenda**: horários do dia, navegação por data, pendentes de confirmação, novo horário (encaixe manual),
  bloqueio de horário (folga, médico), confirmar / concluir / cancelar / reabrir e botão de WhatsApp com a
  mensagem de confirmação pronta. Mostra atendimentos de hoje, pendentes e o faturamento previsto em 7 dias.
- **Serviços**: preço de cada serviço (materiais por atendimento + luz/esterilização + valor da hora + taxas + margem),
  lucro por atendimento e quanto ela ganha por hora de cadeira. A duração do serviço é usada também na agenda.
- **Materiais**: esmaltes, lixas, luvas, algodão etc., com preço pago e tamanho da embalagem.
- **Link de agendamento**: endereço `/a/...`, QR Code, dias e horários de atendimento, intervalo, de quanto em quanto
  tempo os horários aparecem, antecedência mínima, quantos dias a agenda fica aberta, confirmação automática,
  aviso por e-mail, WhatsApp, mensagem, endereço e quais serviços aparecem (com foto e descrição).
- **Ajustes**: margem padrão, taxas, valor da hora, arredondamento e backup.

## Como funciona o agendamento

1. A cliente abre o link, escolhe um ou mais serviços (o tempo é somado), o dia e um horário livre.
2. Só aparecem horários dentro do expediente, fora do intervalo, sem conflito com outros agendamentos ou
   bloqueios e respeitando a antecedência mínima.
3. Ela informa nome e WhatsApp e confirma. O sistema confere de novo se o horário está livre na hora de gravar.
4. O horário entra na agenda como **aguardando confirmação** (ou **confirmado**, se a confirmação automática estiver ligada).
5. A manicure recebe um e-mail e a cliente tem um botão para avisar no WhatsApp com tudo preenchido
   e outro para salvar na agenda do celular (Google Agenda).

Proteções: limite de tentativas por IP, no máximo 3 agendamentos futuros pelo link para o mesmo telefone,
e a agenda de cada manicure é visível só para ela.

Os agendamentos ficam na tabela `appointments` (com data e hora no fuso `TIMEZONE`, padrão `America/Sao_Paulo`).
Serviços, materiais e configurações da agenda ficam no mesmo JSON do Precifica Fácil (`user_data`).

## Passo a passo para colocar no ar

### 1. Conta de e-mail para envio (SMTP)
O sistema precisa mandar e-mails. Use um serviço de envio:
- **Brevo** (grátis até 300 e-mails por dia): crie a conta, vá em *SMTP & API* e copie
  o servidor `smtp-relay.brevo.com`, a porta `587`, o login e a chave SMTP.
- **Resend**: servidor `smtp.resend.com`, porta `465`, usuário `resend`, senha = sua API key.

Para os e-mails não caírem no spam, valide um domínio seu no serviço de envio
(ex: `acesso@seudominio.com.br`).

### 2. Publicar

**No Render (mais fácil):**
1. Coloque a pasta `agenda-manicure` no repositório (ao lado de `calculadora-precos`).
   Em render.com, clique em **New > Blueprint**, escolha o repositório e use o arquivo `agenda-manicure/render.yaml`.
   Ele cria o site e um banco PostgreSQL só para esta versão.
2. Preencha as variáveis que ele pedir (veja a tabela abaixo).
3. Depois do primeiro deploy, copie o endereço do site (ex:
   `https://agendamento-inteligente.onrender.com`) e coloque em `APP_URL`.

**No Railway:**
1. **New Project > Deploy from GitHub repo**, escolha o repositório e, em
   *Settings > Root Directory*, coloque `agenda-manicure`.
2. **+ New > Database > PostgreSQL**. Na aba *Variables* do site, adicione
   `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`.
3. Adicione as outras variáveis e gere um domínio em *Settings > Networking*.

> Use um plano pago, mesmo o mais barato. No plano grátis o site "dorme" e
> demora para abrir, e o banco grátis do Render é apagado depois de um tempo.
> Também dá para usar o banco do **Neon** e colar o endereço em `DATABASE_URL`.

### 3. Variáveis de ambiente

| Variável | O que colocar |
|---|---|
| `SECRET_KEY` | Texto longo e aleatório (o Render gera sozinho) |
| `APP_URL` | Endereço do site, sem `/` no final |
| `DATABASE_URL` | Endereço do PostgreSQL (Render/Railway preenchem) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Dados do serviço de e-mail |
| `MAIL_FROM` | Remetente, ex: `Agendamento Inteligente <acesso@seudominio.com.br>` |
| `SUPPORT_EMAIL` | E-mail de suporte que aparece para o cliente |
| `HOTMART_HOTTOK` | Hottok da Hotmart (passo 4) |
| `KIWIFY_TOKEN` | Token do webhook da Kiwify (passo 4) |
| `HOTMART_PRODUCT_IDS` / `KIWIFY_PRODUCT_IDS` | Opcional: IDs dos produtos que liberam acesso, separados por vírgula. Vazio = qualquer produto |
| `ADMIN_EMAILS` | Seu e-mail (vira dono do painel `/admin`) |
| `ADMIN_INITIAL_PASSWORD` | Senha da sua conta no primeiro acesso. Troque depois em "Minha conta" |
| `CHECKOUT_URL` | Link do checkout, para os botões de assinar |
| `PRODUCT_NAME` | Nome do produto (padrão `Agendamento Inteligente`) |
| `PLAN_PRICE` | Preço mostrado na página de vendas (padrão `49,90`) |
| `TIMEZONE` | Fuso da agenda (padrão `America/Sao_Paulo`) |

O modelo completo está em `.env.example`.

### 4. Ligar a Hotmart e a Kiwify

**Hotmart:** *Ferramentas > Webhook (API e notificações) > Cadastrar webhook*
- URL: `https://SEU-SITE/webhooks/hotmart`
- Versão 2.0, produto: o seu
- Eventos: **Compra aprovada, Compra completa, Compra reembolsada, Chargeback,
  Compra cancelada** e, se for assinatura, **Cancelamento de assinatura**
- Copie o **Hottok** da página e coloque em `HOTMART_HOTTOK`

**Kiwify:** *Apps > Webhooks > Criar webhook*
- URL: `https://SEU-SITE/webhooks/kiwify`
- Eventos: **Compra aprovada, Reembolso, Chargeback** e, se for assinatura,
  **Assinatura cancelada**
- Copie o **Token** e coloque em `KIWIFY_TOKEN`

**Asaas (venda direta):**
1. Crie um **link de pagamento** do tipo **assinatura** (mensal e/ou anual), com Pix, cartão e boleto.
   Copie o código no final do link (`asaas.com/c/CODIGO`) e coloque em `ASAAS_PAYMENT_LINK_IDS`.
   Esse filtro é obrigatório: pagamentos de outros links da sua conta são ignorados.
2. Em *Integrações > Chave de API*, gere a chave e coloque em `ASAAS_API_KEY`.
   Ela é usada só para buscar o nome e o e-mail do cliente.
3. Em *Integrações > Webhooks*, crie um webhook para **cobranças** e outro para **assinaturas**:
   - URL: `https://SEU-SITE/webhooks/asaas`
   - Token de autenticação: invente um texto longo e coloque o mesmo em `ASAAS_WEBHOOK_TOKEN`
   - Eventos de cobrança: *Cobrança confirmada, Cobrança recebida, Cobrança vencida, Cobrança estornada,
     Chargeback solicitado e Em disputa de chargeback*. Eventos de assinatura: *Assinatura removida e Assinatura inativada*.
4. Use o link de pagamento como `CHECKOUT_URL`.

Comportamento: cada mensalidade paga mantém o acesso, sem e-mail repetido. Cobrança vencida bloqueia
(volta sozinho quando a pessoa paga; para não bloquear, use `ASAAS_BLOCK_OVERDUE=0`). Estorno, chargeback
e assinatura removida também bloqueiam. O sistema sempre responde 200 para eventos que não usa, para o
Asaas não pausar a fila de avisos.

### 5. Testar antes de vender
1. Entre em `/entrar` com `ADMIN_EMAILS` e `ADMIN_INITIAL_PASSWORD` e abra `/admin`.
2. Use o botão de **teste de webhook** da plataforma, ou faça uma compra real de
   valor baixo com um cupom de 100%.
3. Confira se o cliente aparece no painel e se o e-mail com a senha chegou.
4. Peça o reembolso dessa compra e confira se o cliente fica **Bloqueado**.

Se algo não funcionar, veja os **Logs** do Render/Railway: cada aviso recebido
das plataformas aparece lá (liberado, revogado ou ignorado).

## Rodar no seu computador

```bash
cd agenda-manicure
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # deixe DATABASE_URL vazio para usar SQLite
python wsgi.py          # abre em http://localhost:5000
```

Sem SMTP configurado, os e-mails (com a senha) aparecem no terminal.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes cobrem: compra pela Hotmart, Kiwify e Asaas, reembolso, login, esqueci a senha, painel admin
e a agenda (preço igual ao da calculadora, horários livres com antecedência, intervalo e conflitos, agendamento
pelo link, horário disputado, limite por telefone, confirmação automática, encaixe e bloqueio manual,
agenda privada de cada manicure, link único e página fora do ar para cliente bloqueada).

## Estrutura

```
agenda-manicure/
├── wsgi.py              # ponto de entrada (gunicorn wsgi:app)
├── render.yaml          # blueprint do Render (site + banco)
├── app/
│   ├── __init__.py      # monta o sistema
│   ├── config.py        # variáveis de ambiente
│   ├── models.py        # tabelas: clientes, dados, compras, links e agendamentos
│   ├── access.py        # regras de liberar/bloquear acesso
│   ├── webhooks.py      # Hotmart, Kiwify e Asaas
│   ├── auth.py          # login, esqueci a senha, minha conta
│   ├── main.py          # sistema, demonstração e API de dados
│   ├── agenda.py        # link público, horários livres, agendamentos e fotos
│   ├── admin.py         # painel do dono
│   ├── mailer.py        # e-mails
│   ├── security.py      # sessão, CSRF, limite de tentativas
│   ├── templates/       # páginas (agendar.html = página pública de agendamento)
│   └── static/          # app.js (sistema), style.css e vendor/ (QR Code)
└── tests/
```
