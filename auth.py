# auth.py
"""
Módulo de autenticación usando python-jose (JWT).
- Endpoints: /register, /login, /token/refresh, /me (protegida)
- Funciones exportadas: create_access_token, create_refresh_token, token_required (decorador)
Guardar como auth.py y conectarlo en tu app Flask o usar tal cual.
Requisitos (pip):
  pip install Flask SQLAlchemy passlib[bcrypt] python-jose python-dotenv
"""

import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import bcrypt
from jose import jwt, JWTError
from dotenv import load_dotenv

# Cargar .env si existe
load_dotenv()

# ---------- Configuración ----------
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "cambia_esto_por_un_secreto_muy_fuerte")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", "15"))
REFRESH_TOKEN_EXPIRES_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", "7"))

DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///auth.db")

# ---------- App & DB (auto-contained para ejemplo) ----------
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# ---------- Modelos ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # optional: token_version para invalidar refresh tokens al hacer logout/cambiar contraseña
    token_version = db.Column(db.Integer, default=0, nullable=False)

    def verify_password(self, plain):
        return bcrypt.verify(plain, self.password_hash)

    def set_password(self, plain):
        self.password_hash = bcrypt.hash(plain)


# crear tablas si no existen
with app.app_context():
    db.create_all()


# ---------- Helpers JWT ----------
def _now_ts():
    return int(datetime.utcnow().timestamp())


def create_access_token(user_id: int):
    """
    Token de corta vida (access).
    Payload mínimo: sub=user_id, type=access, iat, exp
    """
    now = datetime.utcnow()
    exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def create_refresh_token(user_id: int, token_version: int = 0):
    """
    Refresh token de mayor duración. Incluye token_version para revocación simple.
    Payload: sub, type=refresh, iat, exp, tv (token_version)
    """
    now = datetime.utcnow()
    exp = now + timedelta(days=REFRESH_TOKEN_EXPIRES_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "tv": int(token_version),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_token(token: str):
    """
    Decodifica token y devuelve payload o lanza JWTError.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise


# ---------- Decorador para rutas protegidas ----------
def token_required(fn):
    """
    Decorador que espera header Authorization: Bearer <access_token>
    En la función decorada puede usarse `g.current_user` (User instance).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return jsonify({"msg": "Authorization header missing"}), 401

        parts = auth.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify({"msg": "Invalid Authorization header format. Use: Bearer <token>"}), 401

        token = parts[1]
        try:
            payload = decode_token(token)
        except JWTError:
            return jsonify({"msg": "Invalid or expired token"}), 401

        if payload.get("type") != "access":
            return jsonify({"msg": "Invalid token type"}), 401

        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"msg": "Token missing subject"}), 401

        user = User.query.get(int(user_id))
        if not user:
            return jsonify({"msg": "User not found"}), 404

        # Attach user to flask.g
        g.current_user = user
        return fn(*args, **kwargs)
    return wrapper


# ---------- Endpoints mínimos ----------
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"msg": "username and password required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"msg": "username already exists"}), 409

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"msg": "user registered", "user": {"id": user.id, "username": user.username}}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"msg": "username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.verify_password(password):
        return jsonify({"msg": "invalid credentials"}), 401

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id, token_version=user.token_version)
    return jsonify({
        "access_token": access,
        "refresh_token": refresh,
        "user": {"id": user.id, "username": user.username}
    }), 200


@app.route("/token/refresh", methods=["POST"])
def refresh():
    """
    Espera JSON: { "refresh_token": "..." }
    Devuelve nuevo access token.
    """
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"msg": "refresh_token required"}), 400

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        return jsonify({"msg": "invalid or expired refresh token"}), 401

    if payload.get("type") != "refresh":
        return jsonify({"msg": "token is not a refresh token"}), 401

    user_id = payload.get("sub")
    token_version = int(payload.get("tv", 0))
    if not user_id:
        return jsonify({"msg": "invalid token payload"}), 401

    user = User.query.get(int(user_id))
    if not user:
        return jsonify({"msg": "user not found"}), 404

    # validar token_version (simple revocación)
    if user.token_version != token_version:
        return jsonify({"msg": "refresh token revoked"}), 401

    new_access = create_access_token(user.id)
    return jsonify({"access_token": new_access}), 200


@app.route("/me", methods=["GET"])
@token_required
def me():
    user = g.current_user
    return jsonify({"id": user.id, "username": user.username}), 200


@app.route("/logout", methods=["POST"])
@token_required
def logout():
    """
    Ejemplo simple de 'logout' que invalida refresh tokens incrementando token_version.
    (No invalida access token ya emitido; estos caducan pronto).
    """
    user = g.current_user
    user.token_version = user.token_version + 1
    db.session.commit()
    return jsonify({"msg": "logged out, refresh tokens revoked"}), 200


# ---------- Exportar funciones útiles para usar desde otros módulos ----------
def get_user_from_access_token(token: str):
    """
    Helper: decodifica un access token y devuelve el User o None.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return User.query.get(int(user_id))


# ---------- Ejecutar servidor (solo si se ejecuta directamente) ----------
if __name__ == "__main__":
    # Modo desarrollo
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
