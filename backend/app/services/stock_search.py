"""
Powers the stock search/autocomplete endpoint. Searches the local
`stocks` table (populated by scripts/ingest_equity_universe.py plus
any symbol a user has ever looked up or added to a portfolio) — never
hits NSE/Yahoo live per keystroke, which would be far too slow for a
typeahead UI.

Ranking is a simple, explainable tiered scheme rather than a fuzzy-
match/ML ranking model — deliberately: for a symbol search box, exact
and prefix matches on the ticker are almost always what the user
wants, and a transparent ranking is easier to reason about (and debug
when a result looks "wrong") than a black-box similarity score. If
this ever needs fuzzy typo-tolerance (e.g. "relaince" -> RELIANCE),
that's a well-defined future upgrade (e.g. trigram similarity or a
Levenshtein-distance library) — noted, not built, since exact/prefix
matching already solves the common case (a user typing the start of
a symbol or company name).
"""
from dataclasses import dataclass
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.tables import Stock


@dataclass
class StockSearchResult:
    symbol: str
    name: str | None
    match_rank: int  # lower = better match; exposed mainly for debugging/tests


def search_stocks(db: Session, query: str, limit: int = 10) -> list[StockSearchResult]:
    """
    Returns up to `limit` stocks matching `query`, ranked:
        0 = exact symbol match
        1 = symbol starts with query
        2 = company name starts with query
        3 = symbol contains query
        4 = company name contains query
    Empty/whitespace-only query returns an empty list rather than
    every stock in the table (an autocomplete box shouldn't dump its
    entire index when nothing's been typed yet).
    """
    q = query.strip().upper()
    if not q:
        return []

    candidates = (
        db.query(Stock)
        .filter(or_(Stock.symbol.ilike(f"%{q}%"), Stock.name.ilike(f"%{q}%")))
        .all()
    )

    def rank(stock: Stock) -> int:
        symbol = (stock.symbol or "").upper()
        name = (stock.name or "").upper()
        if symbol == q:
            return 0
        if symbol.startswith(q):
            return 1
        if name.startswith(q):
            return 2
        if q in symbol:
            return 3
        return 4  # must be a name-contains match, since it passed the initial filter

    scored = [(s, rank(s)) for s in candidates]
    # secondary sort key: shorter symbol first within the same rank tier
    # (e.g. "TCS" before "TCSTECH" when both start with "TCS") — a cheap
    # proxy for "more likely to be the well-known/primary match"
    scored.sort(key=lambda pair: (pair[1], len(pair[0].symbol)))

    return [
        StockSearchResult(symbol=s.symbol, name=s.name, match_rank=r)
        for s, r in scored[:limit]
    ]
