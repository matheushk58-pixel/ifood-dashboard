#!/usr/bin/env python3
"""
Allury Perfumaria — StockFlow Dashboard
Backend API v3.0
"""
import os
import sqlite3
import time
import secrets
import hashlib
import smtplib
import random
from contextlib import asynccontextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_data_dir = os.path.join(BASE_DIR, "data")
os.makedirs(_data_dir, exist_ok=True)
DB_PATH   = os.path.join(_data_dir, "inventory.db")

# ── Config e-mail (lido de variáveis de ambiente ou .env) ────────────────────
# Para Gmail: ative "Senhas de app" em myaccount.google.com/apppasswords
# e defina as variáveis abaixo no ambiente ou crie um arquivo .env
SMTP_HOST     = os.environ.get("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER",     "")   # seu-email@gmail.com
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")   # senha de app do Gmail
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Allury Perfumaria")

# ── Sessões em memória (token → username, expira em 8h) ──────────────────────
_sessions: dict[str, tuple[str, float]] = {}
SESSION_TTL = 8 * 3600

# ── Códigos de recuperação em memória (email → {code, expires, attempts}) ────
_reset_codes: dict[str, dict] = {}
RESET_TTL      = 15 * 60   # 15 minutos
RESET_MAX_TRIES = 5


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(username: str) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = (username, time.time() + SESSION_TTL)
    return token


def validate_token(token: str) -> Optional[str]:
    entry = _sessions.get(token)
    if not entry:
        return None
    username, expires = entry
    if time.time() > expires:
        del _sessions[token]
        return None
    return username


def revoke_token(token: str):
    _sessions.pop(token, None)


# ── Banco de dados ────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            email    TEXT,
            full_name TEXT,
            phone    TEXT
        )
    """)

    # Migração: adiciona colunas se não existirem (banco antigo)
    existing_cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in existing_cols:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "full_name" not in existing_cols:
        db.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    if "phone" not in existing_cols:
        db.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    # Usuário padrão
    default_pwd = hash_password("admin123")
    try:
        db.execute(
            "INSERT INTO users (username, password, email, full_name) VALUES ('admin', ?, NULL, 'Administrador')",
            (default_pwd,)
        )
        db.commit()
    except sqlite3.IntegrityError:
        pass

    db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT    NOT NULL,
            price          REAL    NOT NULL,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            category       TEXT,
            sku            TEXT    UNIQUE
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER,
            quantity    INTEGER NOT NULL,
            total_price REAL    NOT NULL,
            source      TEXT    NOT NULL,
            sale_date   REAL    NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    """)
    db.commit()
    return db


db = get_db()


# ── App ───────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app):
    yield
    db.close()


app = FastAPI(title="Allury Perfumaria — StockFlow API", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Token não fornecido")
    username = validate_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente.")
    return username


# ── E-mail ────────────────────────────────────────────────────────────────────
def send_reset_email(to_email: str, username: str, code: str) -> bool:
    """Envia o código de 6 dígitos por e-mail via Gmail SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        # Modo dev: apenas imprime o código no terminal
        print(f"\n{'='*50}")
        print(f"  [DEV] Código de recuperação para {to_email}: {code}")
        print(f"{'='*50}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🔐 Código de Recuperação — Allury Perfumaria"
        msg["From"]    = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"]      = to_email

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="center" style="padding:40px 20px;">
                <table width="520" cellpadding="0" cellspacing="0"
                       style="background:white;border-radius:12px;overflow:hidden;
                              box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                  <!-- Header -->
                  <tr>
                    <td style="background:#ea1d2c;padding:32px 40px;text-align:center;">
                      <h1 style="color:white;margin:0;font-size:24px;letter-spacing:1px;">
                        🌸 Allury Perfumaria
                      </h1>
                      <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:14px;">
                        StockFlow Dashboard
                      </p>
                    </td>
                  </tr>
                  <!-- Body -->
                  <tr>
                    <td style="padding:40px;">
                      <p style="color:#333;font-size:16px;margin:0 0 8px;">
                        Olá, <strong>{username}</strong>!
                      </p>
                      <p style="color:#555;font-size:14px;margin:0 0 28px;">
                        Recebemos uma solicitação para redefinir sua senha.
                        Use o código abaixo. Ele é válido por <strong>15 minutos</strong>.
                      </p>

                      <!-- Código -->
                      <div style="text-align:center;margin:0 0 28px;">
                        <div style="display:inline-block;background:#f8f8f8;
                                    border:2px dashed #ea1d2c;border-radius:12px;
                                    padding:20px 40px;">
                          <p style="margin:0;font-size:11px;color:#999;
                                    text-transform:uppercase;letter-spacing:2px;">
                            Seu código
                          </p>
                          <p style="margin:8px 0 0;font-size:42px;font-weight:bold;
                                    color:#ea1d2c;letter-spacing:10px;">
                            {code}
                          </p>
                        </div>
                      </div>

                      <p style="color:#888;font-size:12px;margin:0;text-align:center;">
                        Se você não solicitou a recuperação de senha,
                        ignore este e-mail.
                      </p>
                    </td>
                  </tr>
                  <!-- Footer -->
                  <tr>
                    <td style="background:#f8f8f8;padding:16px 40px;text-align:center;
                                border-top:1px solid #eee;">
                      <p style="margin:0;font-size:11px;color:#aaa;">
                        Allury Perfumaria © 2025 · Este é um e-mail automático
                      </p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        return True
    except Exception as e:
        print(f"[ERRO] Falha ao enviar e-mail: {e}")
        return False


# ── Categorias ────────────────────────────────────────────────────────────────
CATEGORIES = {
    "Perfumes Masculinos": [
        "POLO", "AVENTUS", "SAUVAGE", "BLEU", "INVICTUS", "ACQUA DI GIO",
        "BOSS", "1 MILLION", "ALLURE HOMME", "FAHRENHEIT", "EAU SAUVAGE",
        "MASCULINO", "HOMME", "MAN ", "MEN ", "FOR HIM", "POUR HOMME",
    ],
    "Perfumes Femininos": [
        "CHANEL N°", "COCO MADEMOISELLE", "MISS DIOR", "LA VIE EST BELLE",
        "GOOD GIRL", "DAISY", "FLOWERBOMB", "OLYMPÉA", "SI ", "JADORE",
        "FEMININO", "FEMME", "WOMAN ", "WOMEN ", "FOR HER", "POUR FEMME",
        "MADEMOISELLE", "ROSE ",
    ],
    "Perfumes Unissex": [
        "UNISSEX", "UNISEX", "OUD", "NEROLI", "CK ONE", "ACQUA", "EAU DE PARFUM",
    ],
    "Body Splash & Colônias": [
        "BODY SPLASH", "COLÔNIA", "COLONIA", "BODY MIST", "SPLASH",
        "ACQUA DI COLONIA",
    ],
    "Kits & Presentes": [
        "KIT ", "PRESENTE", "GIFT", "SET ", "COFFRET",
    ],
    "Hidratantes & Body Care": [
        "HIDRATANTE", "LOÇÃO", "LOCAO", "BODY LOTION", "MANTEIGA DE CORPO",
        "ÓLEO CORPORAL", "OLEO CORPORAL", "CREME CORPORAL",
    ],
    "Maquiagem": [
        "BATOM", "BASE", "CORRETIVO", "BLUSH", "SOMBRA", "RÍMEL", "RIMEL",
        "EYELINER", "DELINEADOR", "PRIMER", "MÁSCARA", "MASCARA",
        "CONTORNO", "ILUMINADOR", "PÓ FACIAL", "PO FACIAL",
    ],
    "Cuidados com o Rosto": [
        "SÉRUM", "SERUM", "TÔNICO", "TONICO", "ESFOLIANTE", "VITAMINA C",
        "RETINOL", "ÁCIDO", "ACIDO", "CALMING", "ANTI-AGE", "ANTIIDADE",
        "CREME FACIAL", "CREME ANTI", "PROTETOR SOLAR",
    ],
    "Cabelos": [
        "SHAMPOO", "CONDICIONADOR", "MÁSCARA CAPILAR", "MASCARA CAPILAR",
        "LEAVE-IN", "LEAVE IN", "FINALIZADOR", "ÓLEO CAPILAR",
        "OLEO CAPILAR", "AMPOLA", "BTOX", "QUERATINA",
    ],
    "Higiene Pessoal": [
        "DESODORANTE", "SABONETE", "GEL DE BANHO", "PASTA DENTAL",
        "CREME DENTAL", "ENXAGUANTE", "BUCAL",
    ],
    "Acessórios": [
        "DIFUSOR", "VELA", "HOME SPRAY", "PORTA PERFUME", "FUNIL",
        "ATOMIZADOR", "DECANT",
    ],
}


def auto_categorize(name: str) -> str:
    name_upper = name.upper()
    for cat, keywords in CATEGORIES.items():
        if any(kw in name_upper for kw in keywords):
            return cat
    return "Outros"


# ── Models ────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    full_name: str
    phone: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class Product(BaseModel):
    id: Optional[int] = None
    name: str
    price: float
    stock_quantity: int
    category: Optional[str] = None
    sku: Optional[str] = None


class Sale(BaseModel):
    product_id: int
    quantity: int
    source: str = "ifood"


# ── Rotas ─────────────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def read_root():
    return FileResponse(os.path.join(BASE_DIR, "ifood_dashboard.html"))


@app.post("/api/login")
def login(req: LoginRequest):
    hashed = hash_password(req.password)
    # Permite login com username ou e-mail
    user = db.execute(
        "SELECT id, username, email, full_name FROM users WHERE (LOWER(username) = ? OR LOWER(email) = ?) AND password = ?",
        (req.username.strip().lower(), req.username.strip().lower(), hashed)
    ).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")
    token = create_token(user[1])
    return {
        "message": "Login realizado com sucesso",
        "token": token,
        "username": user[1],
        "email": user[2],
        "full_name": user[3]
    }


@app.post("/api/register")
def register(req: RegisterRequest):
    # Validação de senha: min 1 maiúscula, 1 minúscula, min 6 caracteres
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter no mínimo 6 caracteres")
    if not any(c.isupper() for c in req.password):
        raise HTTPException(status_code=400, detail="A senha deve ter no mínimo uma letra maiúscula")
    if not any(c.islower() for c in req.password):
        raise HTTPException(status_code=400, detail="A senha deve ter no mínimo uma letra minúscula")

    hashed = hash_password(req.password)
    try:
        db.execute(
            "INSERT INTO users (username, password, email, full_name, phone) VALUES (?, ?, ?, ?, ?)",
            (req.username.strip().lower(), hashed, req.email.strip().lower(), req.full_name.strip(), req.phone.strip())
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Usuário já cadastrado")
    
    token = create_token(req.username.strip().lower())
    return {
        "message": "Cadastro realizado com sucesso",
        "token": token,
        "username": req.username,
        "email": req.email,
        "full_name": req.full_name
    }


@app.post("/api/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials:
        revoke_token(credentials.credentials)
    return {"message": "Logout realizado"}


# ── Perfil do usuário ─────────────────────────────────────────────────────────
@app.get("/api/me")
def get_me(username: str = Depends(require_auth)):
    row = db.execute(
        "SELECT username, email, full_name FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {"username": row[0], "email": row[1], "full_name": row[2]}


@app.put("/api/me")
def update_profile(req: UpdateProfileRequest, username: str = Depends(require_auth)):
    db.execute(
        "UPDATE users SET email = ?, full_name = ? WHERE username = ?",
        (req.email, req.full_name, username)
    )
    db.commit()
    return {"message": "Perfil atualizado"}


@app.post("/api/change-password")
def change_password(req: ChangePasswordRequest, username: str = Depends(require_auth)):
    current_hash = hash_password(req.current_password)
    user = db.execute(
        "SELECT id FROM users WHERE username = ? AND password = ?",
        (username, current_hash)
    ).fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Senha atual incorreta")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="A nova senha deve ter ao menos 6 caracteres")
    new_hash = hash_password(req.new_password)
    db.execute("UPDATE users SET password = ? WHERE username = ?", (new_hash, username))
    db.commit()
    return {"message": "Senha alterada com sucesso"}


# ── Recuperação de senha ──────────────────────────────────────────────────────
@app.post("/api/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """
    Passo 1: usuário informa o e-mail.
    Gera um código de 6 dígitos e envia por e-mail.
    Por segurança, retorna sempre 200 mesmo se o e-mail não existir.
    """
    email = req.email.strip().lower()

    row = db.execute(
        "SELECT username FROM users WHERE LOWER(email) = ?", (email,)
    ).fetchone()

    if row:
        username = row[0]

        # Rate-limit: evita spam (máx 1 código a cada 60s)
        existing = _reset_codes.get(email)
        if existing and time.time() < existing.get("expires", 0) - RESET_TTL + 60:
            raise HTTPException(
                status_code=429,
                detail="Aguarde 1 minuto antes de solicitar um novo código."
            )

        code = f"{random.randint(0, 999999):06d}"
        _reset_codes[email] = {
            "code":     code,
            "username": username,
            "expires":  time.time() + RESET_TTL,
            "attempts": 0,
            "verified": False,
        }
        send_reset_email(email, username, code)

    # Resposta genérica (não revela se o e-mail existe)
    return {
        "message": "Se este e-mail estiver cadastrado, você receberá um código em breve."
    }


@app.post("/api/verify-reset-code")
def verify_reset_code(req: VerifyCodeRequest):
    """
    Passo 2: verifica se o código digitado está correto.
    Retorna um token temporário para autorizar a troca de senha.
    """
    email = req.email.strip().lower()
    entry = _reset_codes.get(email)

    if not entry:
        raise HTTPException(status_code=400, detail="Nenhum código foi solicitado para este e-mail.")

    if time.time() > entry["expires"]:
        del _reset_codes[email]
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")

    entry["attempts"] += 1
    if entry["attempts"] > RESET_MAX_TRIES:
        del _reset_codes[email]
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Solicite um novo código."
        )

    if req.code.strip() != entry["code"]:
        remaining = RESET_MAX_TRIES - entry["attempts"]
        raise HTTPException(
            status_code=400,
            detail=f"Código incorreto. {remaining} tentativa(s) restante(s)."
        )

    # Marca como verificado — só agora libera a troca de senha
    entry["verified"] = True

    return {"message": "Código verificado com sucesso. Defina sua nova senha."}


@app.post("/api/reset-password")
def reset_password(req: ResetPasswordRequest):
    """
    Passo 3: define a nova senha após o código ser verificado.
    """
    email = req.email.strip().lower()
    entry = _reset_codes.get(email)

    if not entry:
        raise HTTPException(status_code=400, detail="Sessão de recuperação inválida ou expirada.")

    if not entry.get("verified"):
        raise HTTPException(status_code=403, detail="Código não verificado. Volte ao passo anterior.")

    if time.time() > entry["expires"]:
        del _reset_codes[email]
        raise HTTPException(status_code=400, detail="Sessão expirada. Solicite um novo código.")

    if req.code.strip() != entry["code"]:
        raise HTTPException(status_code=400, detail="Código inválido.")

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 6 caracteres.")

    new_hash = hash_password(req.new_password)
    db.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (new_hash, entry["username"])
    )
    db.commit()

    # Invalida todas as sessões do usuário após troca de senha
    for token, (uname, _) in list(_sessions.items()):
        if uname == entry["username"]:
            del _sessions[token]

    del _reset_codes[email]
    return {"message": "Senha redefinida com sucesso! Faça login com a nova senha."}


# ── Produtos ──────────────────────────────────────────────────────────────────
@app.get("/api/products", response_model=List[Product])
def list_products(_: str = Depends(require_auth)):
    rows = db.execute(
        "SELECT id, name, price, stock_quantity, category, sku FROM products ORDER BY name"
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "price": r[2],
         "stock_quantity": r[3], "category": r[4], "sku": r[5]}
        for r in rows
    ]


@app.post("/api/products", status_code=201)
def add_product(product: Product, _: str = Depends(require_auth)):
    if not product.category or product.category in ["Outros", "Geral", ""]:
        product.category = auto_categorize(product.name)
    try:
        cur = db.execute(
            "INSERT INTO products (name, price, stock_quantity, category, sku) VALUES (?, ?, ?, ?, ?)",
            (product.name, product.price, product.stock_quantity, product.category, product.sku)
        )
        db.commit()
        return {"id": cur.lastrowid, **product.model_dump()}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="SKU já cadastrado. Use um código único.")


@app.put("/api/products/{product_id}")
def update_product(product_id: int, product: Product, _: str = Depends(require_auth)):
    existing = db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    try:
        db.execute(
            "UPDATE products SET name=?, price=?, stock_quantity=?, category=?, sku=? WHERE id=?",
            (product.name, product.price, product.stock_quantity, product.category, product.sku, product_id)
        )
        db.commit()
        return {"message": "Produto atualizado"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="SKU já cadastrado em outro produto.")


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, _: str = Depends(require_auth)):
    existing = db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    return {"message": "Produto removido"}


# ── Vendas ────────────────────────────────────────────────────────────────────
@app.post("/api/sales", status_code=201)
def record_sale(sale: Sale, _: str = Depends(require_auth)):
    product = db.execute(
        "SELECT id, price, stock_quantity FROM products WHERE id = ?",
        (sale.product_id,)
    ).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    prod_id, price, stock = product
    if stock < sale.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Estoque insuficiente. Disponível: {stock} unidade(s)."
        )

    total_price = price * sale.quantity
    db.execute(
        "INSERT INTO sales (product_id, quantity, total_price, source, sale_date) VALUES (?, ?, ?, ?, ?)",
        (sale.product_id, sale.quantity, total_price, sale.source, time.time())
    )
    db.execute(
        "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
        (sale.quantity, sale.product_id)
    )
    db.commit()
    return {"message": "Venda registrada", "total_price": total_price}


@app.get("/api/sales")
def list_sales(_: str = Depends(require_auth)):
    rows = db.execute("""
        SELECT s.id, p.name, s.quantity, s.total_price, s.source, s.sale_date
        FROM   sales s
        JOIN   products p ON s.product_id = p.id
        ORDER  BY s.sale_date DESC
    """).fetchall()
    return [
        {"id": r[0], "product_name": r[1], "quantity": r[2],
         "total_price": r[3], "source": r[4], "sale_date": r[5]}
        for r in rows
    ]


# ── Stats ─────────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(_: str = Depends(require_auth)):
    total_sales   = db.execute("SELECT COALESCE(SUM(total_price), 0) FROM sales").fetchone()[0]
    count_sales   = db.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
    count_products = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    low_stock     = db.execute(
        "SELECT COUNT(*) FROM products WHERE stock_quantity <= 3 AND stock_quantity > 0"
    ).fetchone()[0]
    out_of_stock  = db.execute(
        "SELECT COUNT(*) FROM products WHERE stock_quantity = 0"
    ).fetchone()[0]
    by_source = db.execute(
        "SELECT source, COUNT(*), COALESCE(SUM(total_price), 0) FROM sales GROUP BY source"
    ).fetchall()

    return {
        "total_sales":    total_sales,
        "count_sales":    count_sales,
        "count_products": count_products,
        "low_stock":      low_stock,
        "out_of_stock":   out_of_stock,
        "by_source": [{"source": r[0], "count": r[1], "total": r[2]} for r in by_source]
    }


# ── IA ────────────────────────────────────────────────────────────────────────
@app.get("/api/ai/analyze")
def analyze_stock(_: str = Depends(require_auth)):
    rows = db.execute(
        "SELECT id, name, price, stock_quantity, category, sku FROM products"
    ).fetchall()
    issues = []

    for r in rows:
        pid, name, price, stock, cat, sku = r

        if price <= 0:
            issues.append({
                "id": pid, "item": name,
                "issue": "Preço zero ou negativo",
                "fix": "Definir um preço válido", "type": "error"
            })
        elif price > 2000:
            issues.append({
                "id": pid, "item": name,
                "issue": "Preço acima de R$ 2.000 — confirme se está correto",
                "fix": "Verificar valor", "type": "warning"
            })

        if stock == 0:
            issues.append({
                "id": pid, "item": name,
                "issue": "Produto esgotado (estoque = 0)",
                "fix": "Repor estoque", "type": "warning"
            })
        elif stock <= 3:
            issues.append({
                "id": pid, "item": name,
                "issue": f"Estoque crítico: apenas {stock} unidade(s)",
                "fix": "Reabastecer em breve", "type": "warning"
            })

        suggested = auto_categorize(name)
        if suggested != "Outros" and cat != suggested:
            issues.append({
                "id": pid, "item": name,
                "issue": f"Categoria atual: {cat or '—'}",
                "fix": f"Alterar para '{suggested}'",
                "type": "suggestion", "suggested_cat": suggested
            })

        if not sku:
            issues.append({
                "id": pid, "item": name,
                "issue": "SKU/Código de barras ausente",
                "fix": "Adicionar código EAN", "type": "error"
            })

    return {
        "summary": f"Análise concluída. {len(issues)} alerta(s) encontrado(s).",
        "issues": issues
    }


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 9000))
    print(f"\n{'='*52}")
    print(f"  🌸 Allury Perfumaria — StockFlow Dashboard v3.0")
    print(f"{'='*52}")
    print(f"  Servidor: http://{host}:{port}")
    print(f"  Login:    admin / admin123")
    if not SMTP_USER:
        print(f"  E-mail:   [DEV] códigos impressos no terminal")
        print(f"            Configure SMTP_USER e SMTP_PASSWORD no .env")
    else:
        print(f"  E-mail:   {SMTP_USER}")
    print(f"{'='*52}\n")
    uvicorn.run(app, host=host, port=port)
