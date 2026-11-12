# 🐾 Hotel Pet

Sistema de gestão para hotel de cães e gatos: reservas, entrada e saída, ficha dos pets com vacinas,
diário da hospedagem, recebimentos e mapa de ocupação. Feito para usar no computador da recepção e no celular.

## O que o sistema faz

| Área | Funcionalidades |
|---|---|
| **Painel do dia** | Pets hospedados, ocupação de hoje, chegadas e saídas do dia (e atrasadas), próximos 7 dias, valor a receber e alerta de vacinas vencidas |
| **Mapa de ocupação** | Grade acomodações × 14 dias; clique num espaço livre para reservar |
| **Reservas** | Escolha de tutor, pets, datas e acomodação com disponibilidade na hora. Bloqueia conflito de datas, gato em baia de cão, porte acima do permitido e pets demais |
| **Entrada / saída** | Check-in com registro dos pertences e trava de vacinas (exige confirmação da carteira física); check-out avisa se ainda há valor pendente |
| **Diário da hospedagem** | Registro de alimentação, medicação, passeio, banho e saúde, com horário e quem registrou |
| **WhatsApp** | Um clique para enviar ao tutor: confirmação da reserva, novidades do dia (com o diário) e cobrança do saldo |
| **Tutores e pets** | Ficha completa: raça, porte, ração e horários, medicações, alergias, comportamento, veterinário, contato de emergência; histórico de hospedagens |
| **Vacinas** | Validade por vacina, avisos de “vence logo” e “vencida” considerando a data de saída |
| **Valores** | Diária por pet (gravada na reserva), serviços extras (banho, transporte...), desconto, pagamentos parciais (Pix, dinheiro, cartão) e comprovante para imprimir/PDF |
| **Financeiro** | Recebido no mês por forma de pagamento, faturamento, diárias vendidas, ticket médio e lista do que está a receber |
| **Equipe** | Logins para funcionários; administradores veem financeiro, acomodações e equipe |

## Rodar no computador

```bash
cd hotel-pet
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # ajuste ADMIN_EMAIL e ADMIN_INITIAL_PASSWORD
DEMO_DATA=1 flask --app wsgi run
```

Abra http://localhost:5000. Com `DEMO_DATA=1` o banco vazio ganha acomodações, tutores, pets e reservas de
exemplo — entre com **demo@hotelpet.com / demo123**. Também dá para criar os exemplos com `flask --app wsgi demo`.

Testes: `pytest`

## Publicar (Render)

No Render: **New > Blueprint**, escolha o repositório e aponte para `hotel-pet/render.yaml`. Preencha
`ADMIN_EMAIL`, `ADMIN_INITIAL_PASSWORD` e `APP_URL`. Para uso real, troque `DEMO_DATA` para `0`
**antes** do primeiro start (ou apague os dados de exemplo).

## Stack

Python 3.12 · Flask · SQLAlchemy · PostgreSQL (SQLite no desenvolvimento) · Jinja · CSS próprio com tema claro/escuro.
