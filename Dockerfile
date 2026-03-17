# ── Build Stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9000 \
    HOST=0.0.0.0

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY ifood_server.py .
COPY ifood_dashboard.html .

# Cria volume para persistência do banco
VOLUME ["/app/data"]

# Porta exposta
EXPOSE 9000

# Comando de inicialização
CMD ["python", "ifood_server.py"]
