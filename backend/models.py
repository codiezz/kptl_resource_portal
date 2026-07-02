"""
models.py

Data-access functions for the `users` table. Keeps raw SQL out of the
route handlers — routes call these functions, these functions talk to
the database.

Password storage note: this phase stores `password_hash` as plain text
(no actual hashing yet) — a deliberate placeholder per project decisions.
All password comparisons go through `verify_password()` below, so when
bcrypt is introduced later, only this one function needs to change.
"""

from database import get_connection
import bcrypt

# REPLACE create_user
def create_user(email, password, role="USER"):
    """
    Insert a new user. Returns the new user's id.

    Raises pymysql.err.IntegrityError if the email already exists
    (enforced by the UNIQUE constraint on users.email) — callers should
    catch this and turn it into a friendly "email already registered" response.
    """
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (%s, %s, %s)
                """,
                (email, password_hash, role),
            )
            return cursor.lastrowid
    finally:
        conn.close()

def get_user_by_email(email):
    """Return the user row (dict) for this email, or None if not found."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return the user row (dict) for this id, or None if not found."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def update_last_login(user_id):
    """Stamp last_login = now() for this user, called after a successful login."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user_id,),
            )
    finally:
        conn.close()


# REPLACE verify_password
def verify_password(plain_password, stored_password_hash):
    """
    Check a plaintext password against the stored bcrypt hash.
    bcrypt.checkpw handles the salt extraction internally.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        stored_password_hash.encode("utf-8")
    )