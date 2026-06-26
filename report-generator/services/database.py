import sqlite3
import bcrypt
import json
import datetime
from pathlib import Path
import datetime as _dt


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (_dt.date, _dt.datetime)):
            return obj.isoformat()
        return None  # UploadedFile and other non-serializable objects are dropped

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "reports.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0
        )""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    UNIQUE NOT NULL,
            address TEXT    NOT NULL DEFAULT '',
            contact TEXT    NOT NULL DEFAULT ''
        )""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL,
            form_data  TEXT    NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )""")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS final_docs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            report_number TEXT    UNIQUE NOT NULL,
            created_by    INTEGER NOT NULL,
            created_at    TEXT    NOT NULL,
            form_data     TEXT    NOT NULL,
            pdf_blob      BLOB    NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        )""")
    conn.commit()
    conn.close()

# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(username, password, is_admin=False):
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn()
    conn.execute(
        "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
        (username, pw_hash, int(is_admin))
    )
    conn.commit(); conn.close()

def authenticate_user(username, password):
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, username, password, is_admin FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row[2].encode()):
        return {"id": row[0], "username": row[1], "is_admin": bool(row[3])}
    return None

def list_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, username, is_admin FROM users ORDER BY username").fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "is_admin": bool(r[2])} for r in rows]

def delete_user(user_id):
    conn = get_conn()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit(); conn.close()

def change_password(user_id, current_password, new_password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row or not bcrypt.checkpw(current_password.encode(), row[0].encode()):
        conn.close()
        return False
    pw_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn.execute("UPDATE users SET password = ? WHERE id = ?", (pw_hash, user_id))
    conn.commit(); conn.close()
    return True

# ── Customers ──────────────────────────────────────────────────────────────────

# ── Customers ──────────────────────────────────────────────────────────────────

def add_customer(name, address="", contact=""):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO customers (name, address, contact) VALUES (?, ?, ?)",
            (name.strip(), address.strip(), contact.strip())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()

def update_customer(customer_id, name, address, contact):
    conn = get_conn()
    conn.execute(
        "UPDATE customers SET name=?, address=?, contact=? WHERE id=?",
        (name.strip(), address.strip(), contact.strip(), customer_id)
    )
    conn.commit(); conn.close()

def list_customers():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, address, contact FROM customers ORDER BY name"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "address": r[2], "contact": r[3]} for r in rows]

def get_customer_by_name(name):
    conn = get_conn()
    row  = conn.execute(
        "SELECT id, name, address, contact FROM customers WHERE name=?", (name,)
    ).fetchone()
    conn.close()
    return {"id": row[0], "name": row[1], "address": row[2], "contact": row[3]} if row else None
# ── Drafts ─────────────────────────────────────────────────────────────────────

def save_draft(name, user_id, form_data):
    now = datetime.datetime.now().isoformat()
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO drafts (name, created_by, created_at, updated_at, form_data) VALUES (?,?,?,?,?)",
        (name, user_id, now, now, json.dumps(form_data, cls=_JsonEncoder))
    )
    draft_id = cur.lastrowid
    conn.commit(); conn.close()
    return draft_id

def update_draft(draft_id, form_data, name=None):
    now  = datetime.datetime.now().isoformat()
    conn = get_conn()
    if name:
        conn.execute(
            "UPDATE drafts SET form_data=?, updated_at=?, name=? WHERE id=?",
            (json.dumps(form_data, cls=_JsonEncoder), now, name, draft_id)
        )
    else:
        conn.execute(
            "UPDATE drafts SET form_data=?, updated_at=? WHERE id=?",
            (json.dumps(form_data, cls=_JsonEncoder), now, draft_id)
        )
    conn.commit(); conn.close()

def list_drafts():
    conn = get_conn()
    rows = conn.execute("""
        SELECT d.id, d.name, u.username, d.created_at, d.updated_at
        FROM   drafts d JOIN users u ON d.created_by = u.id
        ORDER  BY d.updated_at DESC
    """).fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "created_by": r[2],
             "created_at": r[3], "updated_at": r[4]} for r in rows]

def load_draft(draft_id):
    conn = get_conn()
    row  = conn.execute("SELECT form_data FROM drafts WHERE id=?", (draft_id,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

def delete_draft(draft_id):
    conn = get_conn()
    conn.execute("DELETE FROM drafts WHERE id=?", (draft_id,))
    conn.commit(); conn.close()

# ── Finals ─────────────────────────────────────────────────────────────────────

def next_report_number():
    year = datetime.datetime.now().year
    conn = get_conn()
    rows = conn.execute(
        "SELECT report_number FROM final_docs WHERE report_number LIKE ?",
        (f"LIDT-{year}-%",)
    ).fetchall()
    conn.close()
    last_n = 0
    for (rn,) in rows:
        parts = rn.split("-")
        if len(parts) >= 3:
            try:
                n = int(parts[2])
                if n > last_n:
                    last_n = n
            except ValueError:
                pass
    return f"LIDT-{year}-{last_n + 1:03d}"

def save_final(user_id, form_data, pdf_bytes, report_number=None):
    if report_number is None:
        report_number = next_report_number()
    now  = datetime.datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO final_docs (report_number, created_by, created_at, form_data, pdf_blob) VALUES (?,?,?,?,?)",
        (report_number, user_id, now, json.dumps(form_data, cls=_JsonEncoder), pdf_bytes)
    )
    conn.commit(); conn.close()
    return report_number

def list_finals():
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.id, f.report_number, u.username, f.created_at
        FROM   final_docs f JOIN users u ON f.created_by = u.id
        ORDER  BY f.report_number DESC
    """).fetchall()
    conn.close()
    return [{"id": r[0], "report_number": r[1], "created_by": r[2], "created_at": r[3]}
            for r in rows]

def get_final_pdf(final_id):
    conn = get_conn()
    row  = conn.execute(
        "SELECT pdf_blob, report_number FROM final_docs WHERE id=?", (final_id,)
    ).fetchone()
    conn.close()
    return (bytes(row[0]), row[1]) if row else (None, None)