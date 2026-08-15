"""
Defines the tools the chatbot can call, and their handler functions.
Each handler wraps an EXISTING service function from the screener
(no new data logic here) — the chatbot is a natural-language layer on
top of the same code paths /stock/{symbol}/score and
/stock/{symbol}/ohlcv already use.

Tool schemas follow the OpenAI-compatible "function" format, which
Groq's tool-calling API expects (same shape as OpenAI's).
"""
import json
from sqlalchemy.orm import Session

from app.services.stock_summary import compute_full_score
from app.data_ingestion.yfinance_client import fetch_ohlcv
from app.rag.store import search as rag_search


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_score",
            "description": (
                "Get the technical, fundamental, and smart-money scores for an "
                "NSE-listed stock from the user's own screener. Use this when the "
                "user asks about a specific stock's score, whether it's a good buy "
                "per the screener's checklist, its ROE/ROCE/PEG/debt levels, "
                "promoter holding, or similar — NOT for general finance concepts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Bare NSE trading symbol, e.g. RELIANCE, TCS, INFY (no exchange suffix).",
                    }
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_summary",
            "description": (
                "Get recent price action for an NSE-listed stock: latest close, "
                "period high/low, and % change over the lookback window. Use this "
                "when the user asks about a stock's current price, recent "
                "performance, or how much it's moved — NOT for full candlestick "
                "chart data (the frontend renders that separately)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Bare NSE trading symbol, e.g. RELIANCE, TCS, INFY.",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "How many calendar days of history to summarize. Default 30.",
                    },
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Search this screener's own knowledge base — includes the "
                "screener's scoring methodology (what each condition means and "
                "how scores are calculated) and, for stocks that have been "
                "ingested, excerpts from that company's annual reports/filings "
                "(management commentary, capex plans, order book, business "
                "outlook). Use this when the user asks 'why did X score this way', "
                "'what does condition Y mean IN THIS SCREENER specifically', or "
                "asks about qualitative information from a company's filings "
                "(e.g. 'what did management say about capex') that isn't a "
                "structured number get_stock_score would return."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to search for.",
                    },
                    "symbol": {
                        "type": "string",
                        "description": (
                            "Optional. If the question is about a specific company's "
                            "filings, pass its NSE symbol to search only that "
                            "company's ingested documents. Omit for methodology "
                            "questions."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _handle_get_stock_score(db: Session, symbol: str) -> dict:
    try:
        result = compute_full_score(symbol, db)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "symbol": result.symbol,
        "technical_score": result.technical.score,
        "technical_breakdown": result.technical.breakdown,
        "fundamental_score": result.fundamental.score,
        "fundamental_breakdown": result.fundamental.breakdown,
        "smart_money_score": result.smart_money.score,
        "smart_money_interpretation": result.smart_money.interpretation,
        "smart_money_breakdown": result.smart_money.breakdown,
    }


def _handle_get_price_summary(symbol: str, lookback_days: int = 30) -> dict:
    try:
        df = fetch_ohlcv(symbol, lookback_days=lookback_days)
    except ValueError as e:
        return {"error": str(e)}

    latest_close = float(df["close"].iloc[-1])
    period_start_close = float(df["close"].iloc[0])
    pct_change = round((latest_close / period_start_close - 1) * 100, 2)

    return {
        "symbol": symbol,
        "lookback_days": lookback_days,
        "latest_close": round(latest_close, 2),
        "period_high": round(float(df["high"].max()), 2),
        "period_low": round(float(df["low"].min()), 2),
        "pct_change_over_period": pct_change,
    }


def _handle_search_knowledge_base(db: Session, query: str, symbol: str | None = None) -> dict:
    results = rag_search(db, query=query, top_k=5, symbol=symbol)
    if not results:
        return {"results": [], "note": "No matching content found in the knowledge base for this query."}

    return {
        "results": [
            {"title": r.title, "content": r.content, "source_type": r.source_type, "relevance": r.score}
            for r in results
        ]
    }


def execute_tool_call(db: Session, tool_name: str, arguments: dict) -> str:
    """
    Dispatches a tool call by name and returns a JSON string — the
    format Groq/OpenAI-compatible tool-calling APIs expect for the
    "tool" role message content that gets fed back to the model.
    Unknown tool names or handler exceptions come back as a JSON error
    object rather than raising, so a bad/hallucinated tool call from
    the model doesn't crash the whole chat turn.
    """
    try:
        if tool_name == "get_stock_score":
            result = _handle_get_stock_score(db, **arguments)
        elif tool_name == "get_price_summary":
            result = _handle_get_price_summary(**arguments)
        elif tool_name == "search_knowledge_base":
            result = _handle_search_knowledge_base(db, **arguments)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
    except TypeError as e:
        # e.g. model passed an argument that doesn't match the schema
        result = {"error": f"Invalid arguments for {tool_name}: {e}"}

    return json.dumps(result)
