# scripts/migrate_to_business.py
import os, sys
from sqlalchemy import text
from app import create_app
from extensions import db

app = create_app()

def table_exists(name: str) -> bool:
    row = db.session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone()
    return bool(row)

def column_exists(table: str, column: str) -> bool:
    rows = db.session.execute(text(f"PRAGMA table_info({table});")).fetchall()
    return any(r[1] == column for r in rows)  # r[1] is the column name

with app.app_context():
    # 1) Ensure business table
    if not table_exists("business"):
        db.session.execute(text("""
            CREATE TABLE business (
                id INTEGER PRIMARY KEY,
                name VARCHAR(160) NOT NULL UNIQUE,
                created_at DATETIME
            )
        """))
        print("✅ created business table")

    # 2) Add business_id columns if missing
    for tbl in ("user","product","supplier","sale","purchase"):
        if not column_exists(tbl, "business_id"):
            db.session.execute(text(f"ALTER TABLE {tbl} ADD COLUMN business_id INTEGER;"))
            print(f"✅ added {tbl}.business_id")

    # 3) Add role column on user if missing
    if not column_exists("user", "role"):
        db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'manager';"))
        print("✅ added user.role")

    db.session.commit()  # commit DDL before proceeding

    # 4) Backfill: one business per user.store_name (fallback to email prefix)
    users = db.session.execute(text(
        "SELECT id, email, COALESCE(store_name,'My Business') AS sn, business_id "
        "FROM user;"
    )).fetchall()

    for uid, email, sn, bid in users:
        if bid:
            continue
        name = (sn or "").strip() or (email.split("@")[0] + " Business")
        # create business if not exists
        db.session.execute(text("INSERT OR IGNORE INTO business(name) VALUES (:n)"), {"n": name})
        # fetch id
        new_bid = db.session.execute(text("SELECT id FROM business WHERE name=:n"), {"n": name}).scalar()
        db.session.execute(text("UPDATE user SET business_id=:b WHERE id=:u"), {"b": new_bid, "u": uid})

    db.session.commit()
    print("✅ users linked to business")

    # 5) Backfill business_id for product/supplier/sale/purchase from owning user
    #    (uses a correlated subquery; for any leftovers, set to the first available business)
    for tbl in ("product","supplier","sale","purchase"):
        db.session.execute(text(f"""
            UPDATE {tbl}
               SET business_id = (
                   SELECT business_id FROM user WHERE user.id = {tbl}.user_id LIMIT 1
               )
             WHERE business_id IS NULL
        """))
    db.session.commit()
    print("✅ backfilled business_id from owning user")

    # Safety net: any still-null rows get assigned to the first business (rare)
    default_bid = db.session.execute(text("SELECT id FROM business LIMIT 1")).scalar()
    if default_bid:
        for tbl in ("product","supplier","sale","purchase"):
            db.session.execute(
                text(f"UPDATE {tbl} SET business_id=:b WHERE business_id IS NULL"),
                {"b": default_bid},
            )
        db.session.commit()
        print("✅ assigned remaining rows to first business")

    print("🎉 migration complete")
