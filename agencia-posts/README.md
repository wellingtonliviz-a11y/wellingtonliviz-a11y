# Agência de Posts

Sistema interno para quem presta serviço de social media para pequenos comércios.
Cada cliente tem a sua pasta, assim nada fica espalhado.

- **Clientes:** dados de contato, @ do Instagram, cores, fontes, tom de voz, valor mensal, dia de pagamento e quantos posts por mês foram contratados.
- **Arquivos:** logos, fotos que o cliente mandou e artes prontas (PNG, JPG, WEBP, GIF, PDF e MP4). Ficam guardados no banco de dados.
- **Postagens:** data e hora, formato (feed, carrossel, story, reels), legenda, hashtags, artes e status:
  Ideia → Em produção → Aguardando aprovação → (Ajuste pedido) → Aprovado → Publicado.
- **Painel:** o que sai hoje, posts atrasados, próximos 7 dias, o que está com o cliente, entregas do mês por cliente e pagamentos chegando.
- **Agenda:** calendário do mês com todos os clientes (ou um só), com cor por cliente e por status.
- **Aprovação pelo cliente:** cada cliente tem um link secreto. Lá ele vê as artes e as legendas e aprova ou pede ajuste, sem senha. Esse link pode ser enviado pelo WhatsApp com um clique.
- **Na hora de postar:** prévia estilo Instagram, um botão para copiar legenda e hashtags e outro para baixar a arte.

## Rodar no computador

```bash
cd agencia-posts
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # preencha ADMIN_EMAILS e ADMIN_INITIAL_PASSWORD
flask --app wsgi run
```

Abra http://localhost:5000 e entre com o e-mail e a senha do `.env`.
Para dar acesso a mais alguém: `flask --app wsgi criar-usuario pessoa@exemplo.com`.

## Publicar no Render

1. **New > Web Service**, escolha este repositório e preencha:
   - Root Directory: `agencia-posts`
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn wsgi:app --preload --workers 2 --bind 0.0.0.0:$PORT`
2. Variáveis de ambiente: `SECRET_KEY` (texto longo aleatório), `APP_URL` (o endereço do site, ex.: `https://agencia.onrender.com`), `ADMIN_EMAILS`, `ADMIN_INITIAL_PASSWORD` e `DATABASE_URL`.
3. `DATABASE_URL` pode apontar para o mesmo PostgreSQL do Precifica Fácil. As tabelas daqui começam com `ag_`, então não se misturam com as de lá.

Use sempre PostgreSQL em produção. O disco do Render é apagado a cada deploy, e por isso o SQLite não serve lá.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```
