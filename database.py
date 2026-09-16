import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from random import randint

from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
DB_PATH = INSTANCE_DIR / "canteen.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(conn, table_name, columns):
    existing = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_names = {col[1] for col in existing}
    for column_name, definition in columns.items():
        if column_name not in existing_names:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS canteens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN'
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canteen_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            image TEXT,
            available INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(canteen_id) REFERENCES canteens(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            canteen_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            pickup_time TEXT,
            payment_method TEXT,
            pickup_token TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'PLACED',
            payment_status TEXT DEFAULT 'Pending',
            payment_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(canteen_id) REFERENCES canteens(id)
        )
        """
    )

    ensure_columns(conn, 'orders', {
        'payment_status': 'TEXT DEFAULT "Pending"',
        'payment_id': 'TEXT',
        'upi_transaction_id': 'TEXT',
        'updated_at': 'TEXT',
    })

    conn.execute("UPDATE orders SET updated_at = COALESCE(updated_at, created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(food_id) REFERENCES foods(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            gateway_payment_id TEXT,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            payment_method TEXT,
            transaction_id TEXT,
            gateway_order_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )
        """
    )

    conn.execute(
        """
        INSERT INTO payments (order_id, amount, status, payment_method, transaction_id)
        SELECT o.id, o.total_amount, o.payment_status, o.payment_method, o.upi_transaction_id
        FROM orders o
        WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.id)
        """
    )
    conn.execute("UPDATE orders SET payment_status = 'CASH / PENDING' WHERE UPPER(payment_method) = 'CASH' AND UPPER(payment_status) IN ('PENDING', 'CASH / PENDING')")
    conn.execute("UPDATE orders SET payment_status = 'PENDING VERIFICATION' WHERE UPPER(payment_method) = 'UPI' AND UPPER(payment_status) IN ('PENDING', 'PENDING VERIFICATION')")
    conn.execute("UPDATE payments SET status = 'CASH / PENDING' WHERE UPPER(payment_method) = 'CASH' AND UPPER(status) IN ('PENDING', 'CASH / PENDING')")
    conn.execute("UPDATE payments SET status = 'PENDING VERIFICATION' WHERE UPPER(payment_method) = 'UPI' AND UPPER(status) IN ('PENDING', 'PENDING VERIFICATION')")

    conn.commit()
    seed_data(conn)
    conn.close()


def seed_data(conn):
    canteen = conn.execute("SELECT id FROM canteens WHERE name = ?", ("Main College Canteen",)).fetchone()
    if not canteen:
        conn.execute(
            "INSERT INTO canteens (name, location, status) VALUES (?, ?, ?)",
            ("Main College Canteen", "Main Block", "OPEN"),
        )
        canteen_id = conn.execute("SELECT id FROM canteens WHERE name = ?", ("Main College Canteen",)).fetchone()[0]
    else:
        canteen_id = canteen[0]

    foods = [
        (canteen_id, "Dosa", "Breakfast", "Crispy South Indian classic", 30.00, 25, "", 1),
        (canteen_id, "Idly", "Breakfast", "Soft steamed rice cakes", 25.00, 30, "", 1),
        (canteen_id, "Biryani", "Lunch", "Spiced rice with rich gravy", 100.00, 18, "", 1),
        (canteen_id, "Meals", "Lunch", "Balanced meal with sides", 80.00, 22, "", 1),
        (canteen_id, "Fried Rice", "Lunch", "Wok-fried rice with vegetables", 90.00, 20, "", 1),
        (canteen_id, "Tea", "Drinks", "Fresh hot tea", 15.00, 40, "", 1),
        (canteen_id, "Coffee", "Drinks", "Classic hot coffee", 20.00, 35, "", 1),
        (canteen_id, "Juice", "Drinks", "Refreshing fruit juice", 30.00, 28, "", 1),
    ]

    existing = conn.execute("SELECT COUNT(*) FROM foods WHERE canteen_id = ?", (canteen_id,)).fetchone()[0]
    if existing == 0:
        conn.executemany(
            "INSERT INTO foods (canteen_id, name, category, description, price, stock, image, available) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            foods,
        )

    admin_email = os.getenv("ADMIN_EMAIL", "admin@canteen.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@123")
    admin = conn.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users (name, email, password, phone, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "Admin",
                admin_email,
                generate_password_hash(admin_password),
                "0000000000",
                "admin",
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    conn.commit()


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, hashed):
    return check_password_hash(hashed, password)


def normalize_indian_mobile(phone):
    if phone is None:
        return None
    cleaned = re.sub(r"[^0-9+]", "", str(phone).strip())
    if cleaned.startswith("00"):
        cleaned = cleaned[2:]
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) > 10:
        cleaned = cleaned[2:]
    if not re.fullmatch(r"[6-9]\d{9}", cleaned):
        return None
    return f"+91{cleaned}"


def validate_phone_number(phone):
    return normalize_indian_mobile(phone) is not None


def get_user_by_email(email):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_phone(phone):
    normalized = normalize_indian_mobile(phone)
    if not normalized:
        return None
    national = normalized[3:]
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE phone IN (?, ?, ?, ?)",
        (normalized, national, f"91{national}", f"+{national}"),
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_phone_exact(phone):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    return dict(user) if user else None


def create_user(name, email, password, phone=None, role="student"):
    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if user:
        conn.close()
        return None
    cursor = conn.execute(
        "INSERT INTO users (name, email, password, phone, role) VALUES (?, ?, ?, ?, ?)",
        (name, email, hash_password(password), phone, role),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def create_verified_user(name, email, password_hash, phone, role="student"):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password, phone, role) VALUES (?, ?, ?, ?, ?)",
        (name, email, password_hash, phone, role),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_all_canteens():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM canteens ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_foods_by_canteen(canteen_id=None, category=None, search=None):
    conn = get_connection()
    query = "SELECT * FROM foods WHERE 1 = 1"
    params = []
    if canteen_id:
        query += " AND canteen_id = ?"
        params.append(canteen_id)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND LOWER(name) LIKE ?"
        params.append(f"%{search.lower()}%")
    rows = conn.execute(query + " ORDER BY name", params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_food_by_id(food_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM foods WHERE id = ?", (food_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_orders_for_user(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT o.*, u.name AS customer_name, u.email AS customer_email, u.phone AS customer_phone FROM orders o JOIN users u ON u.id = o.user_id WHERE o.user_id = ? ORDER BY o.created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_order_detail(order_id):
    conn = get_connection()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    items = conn.execute(
        "SELECT oi.*, f.name AS food_name FROM order_items oi JOIN foods f ON f.id = oi.food_id WHERE oi.order_id = ?",
        (order_id,),
    ).fetchall()
    conn.close()
    return dict(order) if order else None, [dict(item) for item in items]


def save_order(user_id, canteen_id, cart, pickup_time, payment_method, payment_status='PENDING', payment_id=None):
    if not cart:
        return None
    total_amount = 0.0
    for food_id, qty in cart.items():
        food = get_food_by_id(food_id)
        if food and food["available"] and food["stock"] >= qty:
            total_amount += float(food["price"]) * int(qty)
        else:
            return None

    order_id = f"ORD-{datetime.utcnow().strftime('%d%H%M%S')}-{randint(100, 999)}"
    pickup_token = f"PICK-{randint(1000, 9999)}"
    conn = get_connection()
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.execute(
        "INSERT INTO orders (order_id, user_id, canteen_id, total_amount, pickup_time, payment_method, pickup_token, status, payment_status, payment_id, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'PLACED', ?, ?, ?)",
        (order_id, user_id, canteen_id, total_amount, pickup_time, payment_method, pickup_token, payment_status, payment_id, now),
    )
    order_pk = cursor.lastrowid
    conn.execute(
        "INSERT INTO payments (order_id, amount, status, payment_method) VALUES (?, ?, ?, ?)",
        (order_pk, total_amount, payment_status, payment_method.upper()),
    )

    for food_id, qty in cart.items():
        food = get_food_by_id(food_id)
        conn.execute(
            "INSERT INTO order_items (order_id, food_id, quantity, price) VALUES (?, ?, ?, ?)",
            (order_pk, int(food_id), int(qty), float(food["price"])),
        )
        conn.execute(
            "UPDATE foods SET stock = stock - ? WHERE id = ?",
            (int(qty), int(food_id)),
        )

    conn.commit()
    conn.close()
    return order_pk, order_id, pickup_token


def get_all_orders():
    conn = get_connection()
    rows = conn.execute(
        "SELECT o.*, u.name AS user_name FROM orders o JOIN users u ON u.id = o.user_id ORDER BY o.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_count():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    conn.close()
    return count


def get_admin_orders(search=None):
    conn = get_connection()
    query = """
         SELECT o.*, o.user_id AS customer_id, u.name AS customer_name, u.email AS customer_email,
             u.phone AS customer_phone,
             COALESCE(GROUP_CONCAT(f.name || ' x' || oi.quantity, ', '), 'No items') AS item_summary,
             COALESCE((SELECT p2.transaction_id FROM payments p2 WHERE p2.order_id = o.id ORDER BY p2.id DESC LIMIT 1), o.upi_transaction_id) AS transaction_id,
             COALESCE((SELECT p2.status FROM payments p2 WHERE p2.order_id = o.id ORDER BY p2.id DESC LIMIT 1), o.payment_status) AS display_payment_status
        FROM orders o
        JOIN users u ON u.id = o.user_id
         LEFT JOIN order_items oi ON oi.order_id = o.id
         LEFT JOIN foods f ON f.id = oi.food_id
        WHERE 1 = 1
    """
    params = []
    if search:
        search = f"%{search.lower()}%"
        query += " AND (LOWER(o.order_id) LIKE ? OR CAST(o.user_id AS TEXT) LIKE ? OR LOWER(u.name) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(u.phone) LIKE ? OR LOWER(COALESCE(o.upi_transaction_id, '')) LIKE ? OR EXISTS (SELECT 1 FROM payments p2 WHERE p2.order_id = o.id AND LOWER(COALESCE(p2.transaction_id, '')) LIKE ?))"
        params.extend([search, search, search, search, search, search])
        params.append(search)
    query += " GROUP BY o.id ORDER BY o.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_admin_order_detail(order_id):
    conn = get_connection()
    order = conn.execute(
        """
        SELECT o.*, o.user_id AS customer_id, u.name AS customer_name, u.email AS customer_email, u.phone AS customer_phone,
               p.gateway_payment_id, p.amount AS paid_amount, p.status AS payment_status,
               p.transaction_id, p.gateway_order_id, p.payment_method, p.created_at AS payment_created_at
        FROM orders o
        JOIN users u ON u.id = o.user_id
        LEFT JOIN payments p ON p.order_id = o.id
        WHERE o.id = ?
        ORDER BY p.id DESC
        LIMIT 1
        """,
        (order_id,),
    ).fetchone()
    items = conn.execute(
        "SELECT oi.*, f.name AS product_name FROM order_items oi JOIN foods f ON f.id = oi.food_id WHERE oi.order_id = ?",
        (order_id,),
    ).fetchall()
    conn.close()
    return dict(order) if order else None, [dict(item) for item in items]


def get_order_item_count(order_id):
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM order_items WHERE order_id = ?", (order_id,)).fetchone()[0]
    conn.close()
    return count


def update_order_status(order_id, status):
    conn = get_connection()
    conn.execute("UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def get_all_payments(filter_value='all'):
    conn = get_connection()
    query = """
        SELECT p.*, o.order_id, u.name AS customer_name, u.email AS customer_email
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        JOIN users u ON u.id = o.user_id
        WHERE 1 = 1
    """
    params = []
    status_filters = {
        'pending': 'PENDING VERIFICATION',
        'pending_verification': 'PENDING VERIFICATION',
        'cash_pending': 'CASH / PENDING',
    }
    if filter_value and filter_value != 'all':
        query += " AND UPPER(p.status) = ?"
        params.append(status_filters.get(filter_value.lower(), filter_value).upper())
    query += " ORDER BY p.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_latest_payment(order_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1",
        (order_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_payment_by_gateway_order(gateway_order_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM payments WHERE gateway_order_id = ? ORDER BY id DESC LIMIT 1",
        (gateway_order_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_gateway_order_id(order_id, gateway_order_id):
    conn = get_connection()
    conn.execute(
        "UPDATE payments SET gateway_order_id = ? WHERE id = (SELECT id FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1)",
        (gateway_order_id, order_id),
    )
    conn.commit()
    conn.close()


def record_gateway_payment(order_id, payment_status, gateway_payment_id=None, transaction_id=None):
    conn = get_connection()
    conn.execute(
        "UPDATE payments SET status = ?, gateway_payment_id = COALESCE(?, gateway_payment_id), transaction_id = COALESCE(?, transaction_id) WHERE id = (SELECT id FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1)",
        (payment_status, gateway_payment_id, transaction_id, order_id),
    )
    conn.execute(
        "UPDATE orders SET payment_status = ?, payment_id = COALESCE(?, payment_id), upi_transaction_id = COALESCE(?, upi_transaction_id), updated_at = CURRENT_TIMESTAMP, status = CASE WHEN ? = 'PAID' THEN 'CONFIRMED' ELSE status END WHERE id = ?",
        (payment_status, gateway_payment_id, transaction_id, payment_status, order_id),
    )
    conn.commit()
    conn.close()


def submit_payment_reference(order_id, transaction_id):
    conn = get_connection()
    conn.execute(
        "UPDATE orders SET upi_transaction_id = ?, payment_status = 'PENDING VERIFICATION', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (transaction_id, order_id),
    )
    existing = conn.execute("SELECT id FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    if existing:
        conn.execute("UPDATE payments SET transaction_id = ?, status = 'PENDING VERIFICATION', payment_method = 'UPI' WHERE id = ?", (transaction_id, existing[0]))
    else:
        order = conn.execute("SELECT total_amount FROM orders WHERE id = ?", (order_id,)).fetchone()
        conn.execute("INSERT INTO payments (order_id, amount, status, payment_method, transaction_id) VALUES (?, ?, 'PENDING VERIFICATION', 'UPI', ?)", (order_id, order[0], transaction_id))
    conn.commit()
    conn.close()


def update_payment_for_admin(order_id, status):
    conn = get_connection()
    payment = conn.execute("SELECT id FROM payments WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
    if payment:
        conn.execute("UPDATE payments SET status = ? WHERE id = ?", (status, payment[0]))
    conn.execute("UPDATE orders SET payment_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def get_food_analytics():
    conn = get_connection()
    rows = conn.execute(
        "SELECT f.name, f.stock, SUM(oi.quantity) AS sold, f.category FROM foods f LEFT JOIN order_items oi ON oi.food_id = f.id GROUP BY f.id ORDER BY sold DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def dashboard_stats():
    conn = get_connection()
    totals = {
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "revenue": conn.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM orders WHERE status != 'COMPLETED'").fetchone()[0],
        "foods": conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0],
        "low_stock": conn.execute("SELECT COUNT(*) FROM foods WHERE stock < 10").fetchone()[0],
    }
    conn.close()
    return totals


def get_food_summary():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM foods ORDER BY stock ASC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_food(canteen_id, name, category, description, price, stock, image, available):
    conn = get_connection()
    conn.execute(
        "INSERT INTO foods (canteen_id, name, category, description, price, stock, image, available) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (canteen_id, name, category, description, float(price), int(stock), image, 1 if available else 0),
    )
    conn.commit()
    conn.close()


def update_food(food_id, name, category, description, price, stock, available):
    conn = get_connection()
    conn.execute(
        "UPDATE foods SET name=?, category=?, description=?, price=?, stock=?, available=? WHERE id=?",
        (name, category, description, float(price), int(stock), 1 if available else 0, food_id),
    )
    conn.commit()
    conn.close()


def delete_food(food_id):
    conn = get_connection()
    conn.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()


def get_food_categories():
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT category FROM foods ORDER BY category").fetchall()
    conn.close()
    return [row[0] for row in rows]
