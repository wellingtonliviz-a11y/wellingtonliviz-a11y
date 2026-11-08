# Precifica Fácil

Sistema online de **preço e margem de lucro** para quem vende doces, salgados,
bolos e açaí. É vendido pela **Hotmart** ou **Kiwify** e funciona sozinho:

1. O cliente compra.
2. A plataforma avisa o sistema (webhook).
3. O sistema cria o login, gera uma senha e manda por e-mail.
4. O cliente entra e os dados ficam salvos na nuvem, em qualquer aparelho.
5. Em caso de reembolso, chargeback ou cancelamento de assinatura, o acesso é bloqueado sozinho.

Você não precisa fazer nada no dia a dia. O painel `/admin` serve só para
acompanhar as vendas e resolver casos raros.

## O que tem no sistema

| Página | Para quê |
|---|---|
| `/` | A calculadora (precisa estar logado) |
| `/entrar` | Login com o e-mail da compra |
| `/esqueci` | O cliente cria uma nova senha sozinho, por link no e-mail |
| `/conta` | Trocar nome e senha |
| `/demo` | Demonstração grátis, sem login (para a página de vendas) |
| `/admin` | Seu painel: clientes, reembolsos, reenviar senha, bloquear, criar cortesia |
| `/webhooks/hotmart` e `/webhooks/kiwify` | Endereços que você cadastra nas plataformas |

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
1. Em render.com, clique em **New > Blueprint** e escolha este repositório.
   O arquivo `render.yaml` cria o site e o banco PostgreSQL juntos.
2. Preencha as variáveis que ele pedir (veja a tabela abaixo).
3. Depois do primeiro deploy, copie o endereço do site (ex:
   `https://precifica-facil.onrender.com`) e coloque em `APP_URL`.

**No Railway:**
1. **New Project > Deploy from GitHub repo**, escolha o repositório e, em
   *Settings > Root Directory*, coloque `calculadora-precos`.
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
| `MAIL_FROM` | Remetente, ex: `Precifica Fácil <acesso@seudominio.com.br>` |
| `SUPPORT_EMAIL` | E-mail de suporte que aparece para o cliente |
| `HOTMART_HOTTOK` | Hottok da Hotmart (passo 4) |
| `KIWIFY_TOKEN` | Token do webhook da Kiwify (passo 4) |
| `HOTMART_PRODUCT_IDS` / `KIWIFY_PRODUCT_IDS` | Opcional: IDs dos produtos que liberam acesso, separados por vírgula. Vazio = qualquer produto |
| `ADMIN_EMAILS` | Seu e-mail (vira dono do painel `/admin`) |
| `ADMIN_INITIAL_PASSWORD` | Senha da sua conta no primeiro acesso. Troque depois em "Minha conta" |
| `CHECKOUT_URL` | Link do checkout, para o botão da demonstração |

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
cd calculadora-precos
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

Os testes cobrem: compra pela Hotmart e Kiwify, aviso repetido, token errado,
reembolso e recompra, outro produto, login, dados separados por cliente,
esqueci a senha, troca de senha, proteção de formulários, limite de tentativas
de login e o painel admin.

## Estrutura

```
calculadora-precos/
├── wsgi.py              # ponto de entrada (gunicorn wsgi:app)
├── app/
│   ├── __init__.py      # monta o sistema
│   ├── config.py        # variáveis de ambiente
│   ├── models.py        # tabelas: clientes, dados, compras
│   ├── access.py        # regras de liberar/bloquear acesso
│   ├── webhooks.py      # Hotmart e Kiwify
│   ├── auth.py          # login, esqueci a senha, minha conta
│   ├── main.py          # calculadora, demonstração e API de dados
│   ├── admin.py         # painel do dono
│   ├── mailer.py        # e-mails
│   ├── security.py      # sessão, CSRF, limite de tentativas
│   ├── templates/       # páginas
│   └── static/          # app.js (calculadora) e style.css
└── tests/
```
