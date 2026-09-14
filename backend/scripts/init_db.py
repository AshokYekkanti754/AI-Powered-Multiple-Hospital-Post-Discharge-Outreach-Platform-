"""
Database setup CLI.

Usage (from repository root):
    .venv\\Scripts\\python.exe backend/scripts/init_db.py            # create tables + seed demo data
    .venv\\Scripts\\python.exe backend/scripts/init_db.py --no-seed  # only create tables

Tables are created from the SQLAlchemy metadata; in development, demo data is
seeded automatically when the users table is empty.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the platform database.")
    parser.add_argument("--no-seed", action="store_true", help="Skip demo data seeding")
    args = parser.parse_args()

    from app.db.base import Base
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    print("Tables ready:", sorted(Base.metadata.tables.keys()))

    if not args.no_seed:
        from app.db.seed import seed_demo_data

        db = SessionLocal()
        try:
            result = seed_demo_data(db)
        finally:
            db.close()
        if result.get("seeded"):
            print("Seeded demo data:")
            print(f"  Platform admin : {result['platform_admin']} / {result['demo_password']}")
            for hospital in result["hospitals"]:
                print(f"  Hospital        : {hospital['name']} (id={hospital['id']})")
            print("  Hospital logins: admin@stmarys.demo, campaign@stmarys.demo, clinical@stmarys.demo")
            print("                  admin@riverside.demo, campaign@riverside.demo, clinical@riverside.demo")
            print("  Password       :", result["demo_password"])
        else:
            print("Seed skipped:", result.get("reason"))


if __name__ == "__main__":
    main()