# 🌸 StockFlow — Allury Perfumaria

Dashboard completo de controle de estoque e vendas com autenticação segura, recuperação de senha por e-mail e integração com iFood.

---

## ✨ Funcionalidades

### 🔐 Autenticação
- Login com hash de senha (SHA-256) e tokens de sessão (8h)
- **Recuperação de senha em 3 passos:**
  1. Informe o e-mail cadastrado
  2. Digite o código de 6 dígitos recebido por e-mail
  3. Defina a nova senha
- Alterar senha pelo próprio usuário no painel
- Perfil de usuário (nome completo + e-mail)
- Código de recuperação expira em **15 minutos**
- Máximo de 5 tentativas erradas antes de bloquear o código
- Rate-limit: 1 código a cada 60 segundos

### 📦 Estoque & Vendas
- CRUD completo de produtos com busca em tempo real
- Alertas de estoque crítico (≤3) e esgotado
- Registrar vendas: iFood, Loja Física, WhatsApp, Instagram
- Importar planilha Excel (.xlsx) ou CSV
- Exportar produtos e vendas para CSV
- Assistente IA local: detecta preços inválidos, estoque baixo, categorias erradas
- Categorias de perfumaria: Masculinos, Femininos, Unissex, Body Splash, Kits, etc.
- Stats em tempo real no topo do dashboard

---

## 🚀 Como rodar

### Opção 1 — Windows (fácil)
Dê dois cliques em `run_server.bat` ou no PowerShell:
```powershell
.\run_server.ps1
```
Acesse: **http://localhost:9000**

### Opção 2 — Manual (qualquer OS)
```bash
pip install -r requirements.txt
python ifood_server.py
```

### Opção 3 — Docker
```bash
docker compose up -d
```

---

## 🔐 Login padrão

| Usuário | Senha    |
|---------|----------|
| admin   | admin123 |

> ⚠️ **Importante:** Após o primeiro acesso, vá em **👤 Perfil** e cadastre seu e-mail.  
> Sem e-mail cadastrado, a recuperação de senha não funciona.

---

## 📧 Configurar e-mail (Gmail)

1. Ative a **verificação em 2 etapas** no Gmail
2. Acesse [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Crie uma "Senha de app" para "Mail"
4. Copie `.env.example` para `.env` e preencha:

```env
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
SMTP_FROM_NAME=Allury Perfumaria
```

5. Reinicie o servidor

> **Modo DEV (sem .env):** os códigos são impressos no terminal em vez de enviados por e-mail.

---

## 📊 Importar Planilha

Colunas necessárias (qualquer ordem):

| Código de Barras | Nome | Preço | Qtd. Atual Estoque |
|-----------------|------|-------|---------------------|

Formatos: `.xlsx`, `.xls`, `.csv`

---

## 🐳 Deploy em produção

### Railway / Render / Fly.io
1. Push para o GitHub
2. Crie um serviço Web apontando para o repositório
3. Adicione as variáveis de ambiente (`SMTP_USER`, `SMTP_PASSWORD`, etc.)
4. Porta: `9000`

### VPS (Ubuntu/Debian)
```bash
git clone https://github.com/matheushk58-pixel/ifood-dashboard.git
cd ifood-dashboard
cp .env.example .env  # edite com suas configs
docker compose up -d
```

---

## 📁 Estrutura

```
ifood-dashboard/
├── ifood_server.py        # Backend FastAPI v3.0
├── ifood_dashboard.html   # Frontend SPA
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example           # Modelo de configuração
├── .gitignore
├── run_server.bat         # Atalho Windows CMD
├── run_server.ps1         # Atalho Windows PowerShell
└── README.md
```

---

## 🛠️ Tecnologias

- **Backend:** Python 3.12, FastAPI, SQLite, Uvicorn
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **E-mail:** smtplib (Gmail SMTP)
- **Planilhas:** SheetJS (xlsx)
- **Deploy:** Docker, Docker Compose

---

## 📝 Licença

Projeto privado — Allury Perfumaria © 2025
