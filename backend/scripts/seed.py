"""Populate the database with synthetic reference/demand data.

Usage:
    python scripts/seed.py [--reset]

--reset drops and recreates all tables first (alembic downgrade/upgrade is
the safer path for real schema changes; this is just for iterating on the
seed data itself during POC development).
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401
from app.seed.generate import seed_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Truncate all tables before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            print("Truncating all tables...")
            with engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(table.delete())

        print("Seeding data...")
        stats = seed_all(db)
        print("\nDone. Summary:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
