"""
Run once to create all tables in the configured Postgres database:
    python -m scripts.init_db
"""
from app.db import Base, engine
from app.models import tables  # noqa: F401 — import registers models on Base.metadata

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created:", list(Base.metadata.tables.keys()))
