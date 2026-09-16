from database import create_user, get_connection
from werkzeug.security import generate_password_hash


def seed_admin():
    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@canteen.com",)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (name, email, password, phone, role) VALUES (?, ?, ?, ?, ?)",
            ("Admin", "admin@canteen.com", generate_password_hash("Admin@123"), "0000000000", "admin"),
        )
        conn.commit()
    conn.close()
    print("Admin seeded: admin@canteen.com / Admin@123")


if __name__ == "__main__":
    seed_admin()
