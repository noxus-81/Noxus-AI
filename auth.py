"""
auth.py — Module d'authentification sécurisé pour Noxus AI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sécurité :
  • Les mots de passe ne sont JAMAIS stockés en clair.
  • Chaque mot de passe est hashé avec PBKDF2-HMAC-SHA256
    + un sel aléatoire unique de 32 octets (256 bits).
  • 260 000 itérations (recommandation OWASP 2024).
  • Comparaison en temps constant (secrets.compare_digest).
  • Migration automatique des anciennes bases de données.
"""

import sqlite3
import hashlib
import secrets

DB_PATH    = "users.db"
ITERATIONS = 260_000


# ── Initialisation + migration automatique ─────────────────
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        # Création de la table si elle n'existe pas encore
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT    NOT NULL,
                salt          TEXT    NOT NULL DEFAULT '',
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration : ajouter les colonnes manquantes sur une ancienne DB
        # Note : SQLite n'accepte que des valeurs constantes dans ALTER TABLE ADD COLUMN
        existing = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "salt" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN salt TEXT DEFAULT ''")
        if "created_at" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT '2024-01-01 00:00:00'")
        conn.commit()


# ── Hachage du mot de passe ────────────────────────────────
def _hash_password(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS,
    )
    return raw.hex()


# ── Inscription ────────────────────────────────────────────
def register_user(username: str, password: str) -> tuple[bool, str]:
    init_db()
    username = username.strip()

    if len(username) < 3:
        return False, "Le nom d'utilisateur doit contenir au moins 3 caractères."
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères."

    salt          = secrets.token_hex(32)        # 256 bits aléatoires
    password_hash = _hash_password(password, salt)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                (username, password_hash, salt),
            )
            conn.commit()
        return True, f"✅ Compte « {username} » créé avec succès !"
    except sqlite3.IntegrityError:
        return False, "❌ Ce nom d'utilisateur est déjà pris, choisissez-en un autre."


# ── Connexion ──────────────────────────────────────────────
def login_user(username: str, password: str) -> tuple[bool, str]:
    init_db()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT password_hash, salt FROM users WHERE username = ? COLLATE NOCASE",
            (username.strip(),),
        ).fetchone()

    # Utilisateur inconnu — même message que mauvais MDP (sécurité)
    if row is None:
        return False, "❌ Identifiants incorrects."

    stored_hash, salt = row

    # Ancien compte créé avant la migration (pas de sel) → demander recréation
    if not salt:
        return False, (
            "⚠️ Votre compte a été créé avec une ancienne version de Noxus AI. "
            "Pour des raisons de sécurité, veuillez créer un nouveau compte avec l'onglet Inscription."
        )

    candidate_hash = _hash_password(password, salt)

    # Comparaison en temps constant → protégé contre les attaques par timing
    if secrets.compare_digest(candidate_hash, stored_hash):
        return True, f"Bienvenue, {username} !"

    return False, "❌ Identifiants incorrects."
