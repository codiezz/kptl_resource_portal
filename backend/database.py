"""
database.py

Thin connection layer for MySQL. Deliberately minimal — no ORM, no
connection pool, no migrations framework. Matches the project's
"keep it simple" philosophy.

Usage:
    from database import get_connection

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
"""

import pymysql
import pymysql.cursors

import config


def get_connection():
    """
    Return a new PyMySQL connection.

    Each call opens a fresh connection — fine for this portal's traffic
    level. If this ever becomes a bottleneck, swap this function's body
    for a pooled connection (e.g. DBUtils) without touching any caller.

    cursorclass=DictCursor means rows come back as dicts (e.g. row["email"])
    instead of plain tuples, which keeps the calling code in models.py readable.
    """
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def init_db():
    """
    Create the database (if missing) and the users table (if missing).

    Safe to call every time the app starts — uses CREATE ... IF NOT EXISTS,
    so it won't touch existing data or schema on repeated runs.
    """
    # First connect without selecting a database, in case it doesn't exist yet.
    bootstrap_conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        with bootstrap_conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        bootstrap_conn.close()

    # Now connect to the actual database and create the table.
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    role ENUM('USER', 'ADMIN') NOT NULL DEFAULT 'USER',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME NULL
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                """
            )
    finally:
        conn.close()