from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import User, Stock, PortfolioHolding
from app.auth.dependencies import get_current_user
from app.schemas_portfolio import HoldingCreate, HoldingResponse
from app.services.ingestion_trigger import ensure_fundamentals_ingested
from app.data_ingestion.yfinance_client import fetch_ohlcv

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _to_response(holding: PortfolioHolding) -> HoldingResponse:
    return HoldingResponse(
        id=holding.id, symbol=holding.stock.symbol, quantity=holding.quantity,
        buy_price=holding.buy_price, buy_date=holding.buy_date, notes=holding.notes,
    )


@router.get("", response_model=list[HoldingResponse])
def list_holdings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    holdings = db.query(PortfolioHolding).filter_by(user_id=current_user.id).all()
    return [_to_response(h) for h in holdings]


@router.post("", response_model=HoldingResponse, status_code=status.HTTP_201_CREATED)
def add_holding(
    req: HoldingCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    symbol = req.symbol.upper()

    # Validate the symbol actually resolves to a real NSE stock BEFORE
    # creating anything — without this, a typo like "RELAINCE" silently
    # succeeds, the user only discovers something's wrong much later when
    # the score never loads (and background ingestion would silently fail
    # too, per its own error handling). A small lookback keeps this check
    # fast — we only need to know the symbol resolves, not its full history.
    try:
        fetch_ohlcv(symbol, lookback_days=5)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{symbol}' doesn't look like a valid NSE symbol — no price data found. "
                "Double-check the spelling (e.g. RELIANCE, TCS, INFY, HDFCBANK)."
            ),
        )

    stock = db.query(Stock).filter_by(symbol=symbol).first()
    if stock is None:
        # get-or-create — safe now that we've confirmed the symbol is real.
        stock = Stock(symbol=symbol)
        db.add(stock)
        db.flush()

    holding = PortfolioHolding(
        user_id=current_user.id, stock_id=stock.id, quantity=req.quantity,
        buy_price=req.buy_price, buy_date=req.buy_date, notes=req.notes,
    )
    db.add(holding)
    db.commit()
    db.refresh(holding)

    # If this is a symbol we've never analyzed, kick off fundamentals
    # ingestion in the background — the user doesn't need to know or
    # care that this happens via a script; adding a stock to their
    # portfolio is the trigger.
    ensure_fundamentals_ingested(symbol, db, background_tasks)

    return _to_response(holding)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(
    holding_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    holding = db.query(PortfolioHolding).filter_by(id=holding_id).first()

    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    if holding.user_id != current_user.id:
        # Same 404 as "doesn't exist" rather than 403 — doesn't confirm
        # to a probing user that a holding with this ID exists at all,
        # just belongs to someone else.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")

    db.delete(holding)
    db.commit()
