import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'makafati.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            student_type TEXT NOT NULL DEFAULT 'مع أهل',
            monthly_reward REAL NOT NULL DEFAULT 990,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT NOT NULL DEFAULT '📦',
            default_percentage REAL NOT NULL DEFAULT 0,
            color TEXT NOT NULL DEFAULT '#6b7280'
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            total_amount REAL NOT NULL DEFAULT 990,
            status TEXT NOT NULL DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, month, year)
        );

        CREATE TABLE IF NOT EXISTS budget_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            budget_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            allocated_amount REAL NOT NULL DEFAULT 0,
            spent_amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (budget_id) REFERENCES budgets(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            transaction_date TEXT NOT NULL DEFAULT (date('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_amount REAL NOT NULL,
            saved_amount REAL NOT NULL DEFAULT 0,
            target_date TEXT,
            icon TEXT NOT NULL DEFAULT '🎯',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT NOT NULL DEFAULT '🏅',
            description TEXT,
            earned_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)

    # Seed default categories if empty
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        categories = [
            ('أكل وشرب',    '🍔', 30, '#f97316'),
            ('مواصلات',      '🚗', 20, '#3b82f6'),
            ('دراسة',        '📚', 15, '#8b5cf6'),
            ('ترفيه',        '🎮', 10, '#ec4899'),
            ('ملابس',        '👕', 10, '#14b8a6'),
            ('صحة',          '💊',  5, '#22c55e'),
            ('ادخار',        '💰', 10, '#eab308'),
            ('أخرى',         '📦',  0, '#6b7280'),
        ]
        cur.executemany(
            "INSERT INTO categories (name, icon, default_percentage, color) VALUES (?,?,?,?)",
            categories
        )

    conn.commit()
    conn.close()


# ─── helpers ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


# ─── users ──────────────────────────────────────────────────────────────────

def create_user(username, email, password, student_type, monthly_reward=990):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, student_type, monthly_reward) VALUES (?,?,?,?,?)",
            (username, email, hash_password(password), student_type, monthly_reward)
        )
        conn.commit()
        return True, "تم إنشاء الحساب بنجاح"
    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return False, "اسم المستخدم مستخدم من قبل"
        return False, "البريد الإلكتروني مستخدم من قبل"
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


# ─── categories ─────────────────────────────────────────────────────────────

def get_all_categories():
    conn = get_db()
    cats = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    return cats


# ─── budgets ────────────────────────────────────────────────────────────────

def get_or_create_budget(user_id, month, year, total_amount):
    conn = get_db()
    budget = conn.execute(
        "SELECT * FROM budgets WHERE user_id=? AND month=? AND year=?",
        (user_id, month, year)
    ).fetchone()

    if not budget:
        conn.execute(
            "INSERT INTO budgets (user_id, month, year, total_amount) VALUES (?,?,?,?)",
            (user_id, month, year, total_amount)
        )
        conn.commit()
        budget = conn.execute(
            "SELECT * FROM budgets WHERE user_id=? AND month=? AND year=?",
            (user_id, month, year)
        ).fetchone()

        # Create budget_categories from defaults
        categories = conn.execute("SELECT * FROM categories").fetchall()
        for cat in categories:
            allocated = round(total_amount * cat['default_percentage'] / 100, 2)
            conn.execute(
                "INSERT INTO budget_categories (budget_id, category_id, allocated_amount) VALUES (?,?,?)",
                (budget['id'], cat['id'], allocated)
            )
        conn.commit()

    conn.close()
    return budget


def get_budget_with_categories(budget_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT bc.*, c.name, c.icon, c.color
        FROM budget_categories bc
        JOIN categories c ON bc.category_id = c.id
        WHERE bc.budget_id = ?
        ORDER BY bc.allocated_amount DESC
    """, (budget_id,)).fetchall()
    conn.close()
    return rows


# ─── transactions ────────────────────────────────────────────────────────────

def add_transaction(user_id, category_id, amount, note, transaction_date):
    conn = get_db()
    conn.execute(
        "INSERT INTO transactions (user_id, category_id, amount, note, transaction_date) VALUES (?,?,?,?,?)",
        (user_id, category_id, amount, note, transaction_date)
    )
    # Update spent_amount in budget_categories for the current month
    d = datetime.strptime(transaction_date, '%Y-%m-%d')
    budget = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND month=? AND year=?",
        (user_id, d.month, d.year)
    ).fetchone()
    if budget:
        conn.execute("""
            UPDATE budget_categories
            SET spent_amount = spent_amount + ?
            WHERE budget_id = ? AND category_id = ?
        """, (amount, budget['id'], category_id))
    conn.commit()
    conn.close()


def get_transactions(user_id, limit=50):
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*, c.name as category_name, c.icon, c.color
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return rows


def delete_transaction(transaction_id, user_id):
    conn = get_db()
    tx = conn.execute(
        "SELECT * FROM transactions WHERE id=? AND user_id=?",
        (transaction_id, user_id)
    ).fetchone()
    if not tx:
        conn.close()
        return False
    d = datetime.strptime(tx['transaction_date'], '%Y-%m-%d')
    budget = conn.execute(
        "SELECT id FROM budgets WHERE user_id=? AND month=? AND year=?",
        (user_id, d.month, d.year)
    ).fetchone()
    if budget:
        conn.execute("""
            UPDATE budget_categories
            SET spent_amount = MAX(0, spent_amount - ?)
            WHERE budget_id = ? AND category_id = ?
        """, (tx['amount'], budget['id'], tx['category_id']))
    conn.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
    conn.commit()
    conn.close()
    return True


def get_monthly_spending_by_category(user_id, month, year):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.name, c.icon, c.color, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = ?
          AND strftime('%m', t.transaction_date) = ?
          AND strftime('%Y', t.transaction_date) = ?
        GROUP BY c.id
        ORDER BY total DESC
    """, (user_id, f"{month:02d}", str(year))).fetchall()
    conn.close()
    return rows


def get_total_spent(user_id, month, year):
    conn = get_db()
    row = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions
        WHERE user_id = ?
          AND strftime('%m', transaction_date) = ?
          AND strftime('%Y', transaction_date) = ?
    """, (user_id, f"{month:02d}", str(year))).fetchone()
    conn.close()
    return row['total'] if row else 0


# ─── goals ───────────────────────────────────────────────────────────────────

def get_goals(user_id):
    conn = get_db()
    goals = conn.execute(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return goals


def add_goal(user_id, title, target_amount, target_date, icon):
    conn = get_db()
    conn.execute(
        "INSERT INTO goals (user_id, title, target_amount, target_date, icon) VALUES (?,?,?,?,?)",
        (user_id, title, target_amount, target_date, icon)
    )
    conn.commit()
    conn.close()


def update_goal_savings(goal_id, user_id, amount):
    conn = get_db()
    conn.execute(
        "UPDATE goals SET saved_amount = MIN(target_amount, saved_amount + ?) WHERE id=? AND user_id=?",
        (amount, goal_id, user_id)
    )
    conn.commit()
    conn.close()


def delete_goal(goal_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM goals WHERE id=? AND user_id=?", (goal_id, user_id))
    conn.commit()
    conn.close()


# ─── achievements ────────────────────────────────────────────────────────────

def grant_achievement(user_id, badge_name, badge_icon, description):
    conn = get_db()
    exists = conn.execute(
        "SELECT id FROM achievements WHERE user_id=? AND badge_name=?",
        (user_id, badge_name)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT INTO achievements (user_id, badge_name, badge_icon, description) VALUES (?,?,?,?)",
            (user_id, badge_name, badge_icon, description)
        )
        conn.commit()
    conn.close()


def get_achievements(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM achievements WHERE user_id=? ORDER BY earned_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def check_and_grant_achievements(user_id, month, year):
    transactions = get_transactions(user_id, limit=9999)
    month_txs = [t for t in transactions
                 if t['transaction_date'].startswith(f"{year}-{month:02d}")]

    if len(transactions) >= 1:
        grant_achievement(user_id, 'first_transaction', '🌟',
                          'سجّلت أول مصروف لك — أول خطوة نحو الوعي المالي!')

    if len(month_txs) >= 10:
        grant_achievement(user_id, 'consistent_tracker', '📊',
                          'سجّلت 10 معاملات في الشهر — طالب ملتزم!')

    total_spent = get_total_spent(user_id, month, year)
    user = get_user_by_id(user_id)
    if user and total_spent <= user['monthly_reward'] * 0.5:
        from datetime import date
        today = date.today()
        if today.month == month and today.year == year and today.day >= 15:
            grant_achievement(user_id, 'mid_month_safe', '🛡️',
                              'وصلت منتصف الشهر وأنت بأمان — رائع!')
