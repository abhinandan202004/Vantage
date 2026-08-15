from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, JSON, func
)
from sqlalchemy.orm import relationship

from app.db import Base


class Stock(Base):
    """
    Master table of tracked stocks. `symbol` is the NSE trading symbol
    (e.g. RELIANCE, TCS) — used as the join key everywhere else.
    """
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128))
    sector = Column(String(64))
    sector_index_symbol = Column(String(32))  # e.g. "NIFTY BANK" mapping for relative-strength scoring
    exchange = Column(String(8), default="NSE")

    ohlcv = relationship("OHLCV", back_populates="stock", cascade="all, delete-orphan")
    fundamentals = relationship("Fundamental", back_populates="stock", cascade="all, delete-orphan")
    shareholding = relationship("Shareholding", back_populates="stock", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="stock", cascade="all, delete-orphan")


class OHLCV(Base):
    """
    Daily price bars. One row per (stock, date).
    Source is free-text so we know if a row came from NSE, yfinance, or bhavcopy —
    useful since the three sources occasionally disagree on adjusted closes.
    """
    __tablename__ = "ohlcv_daily"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_ohlcv_stock_date"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    source = Column(String(16), default="yfinance")

    stock = relationship("Stock", back_populates="ohlcv")


class Fundamental(Base):
    """
    One row per (stock, period). period_type distinguishes quarterly vs
    annual/TTM rows since the checklist mixes both timeframes.
    """
    __tablename__ = "fundamentals"
    __table_args__ = (UniqueConstraint("stock_id", "period_end", "period_type", name="uq_fund_stock_period"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    period_type = Column(String(16), nullable=False)  # "quarterly" | "annual" | "ttm"

    sales = Column(Float)
    net_profit = Column(Float)
    operating_cash_flow = Column(Float)
    total_debt = Column(Float)
    total_equity = Column(Float)
    roe = Column(Float)
    roce = Column(Float)
    pe_ratio = Column(Float)
    peg_ratio = Column(Float)
    sales_cagr_pct = Column(Float)
    profit_cagr_pct = Column(Float)
    earnings_growth_trend = Column(String(16))  # "accelerating" | "decelerating" | "flat"

    stock = relationship("Stock", back_populates="fundamentals")


class Shareholding(Base):
    """Quarterly shareholding pattern snapshot."""
    __tablename__ = "shareholding"
    __table_args__ = (UniqueConstraint("stock_id", "period_end", name="uq_share_stock_period"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    period_end = Column(Date, nullable=False)
    promoter_pct = Column(Float)
    fii_pct = Column(Float)
    dii_pct = Column(Float)
    public_pct = Column(Float)

    stock = relationship("Stock", back_populates="shareholding")


class Score(Base):
    """
    One row per (stock, as_of_date). Stores the computed technical and
    fundamental scores plus a JSON-ish breakdown so the UI can show
    which individual conditions passed.
    """
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("stock_id", "as_of_date", name="uq_score_stock_date"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    as_of_date = Column(Date, nullable=False)

    technical_score = Column(Float)   # 0-100
    fundamental_score = Column(Float)  # 0-100
    smart_money_score = Column(Float)  # 0-100, weighted (see scoring/smart_money_score.py)
    technical_breakdown = Column(String)   # JSON string: {"price_above_20ema": true, ...}
    fundamental_breakdown = Column(String)  # JSON string
    smart_money_breakdown = Column(String)  # JSON string
    smart_money_interpretation = Column(String)  # e.g. "Strong institutional accumulation"

    computed_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock", back_populates="scores")


class DocumentChunk(Base):
    """
    One row per chunk of an ingested document, for RAG retrieval.

    Embeddings are stored as a plain JSON array of floats rather than
    using pgvector — deliberately avoids that extra native-compiled
    Postgres extension (which needs Visual Studio's C++ toolchain to
    build on Windows). Similarity search is brute-force cosine
    similarity in Python (see app/rag/store.py) — perfectly fine at
    the document volumes a personal project will have; revisit only
    if the corpus grows into the tens of thousands of chunks.

    `source_type` distinguishes what kind of content this chunk came
    from, so retrieval can filter by it (e.g. "only search this
    stock's own filings, not the general glossary").
    """
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    source_type = Column(String(32), nullable=False, index=True)
    # "company_filing" | "general_knowledge" | "project_methodology"
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=True, index=True)
    # null for source_type in (general_knowledge, project_methodology) — those aren't stock-specific

    title = Column(String(256))          # e.g. "RELIANCE Annual Report FY2026"
    source_url = Column(String(512))     # where this content came from, for citation/debugging
    content = Column(String, nullable=False)  # the chunk's raw text
    embedding = Column(JSON, nullable=False)  # list[float], length == EMBEDDING_DIM (see rag/embeddings.py)

    created_at = Column(DateTime, server_default=func.now())

    stock = relationship("Stock")
