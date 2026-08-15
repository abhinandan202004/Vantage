"""
Seeds the `project_methodology` knowledge base with original
explanations of the screener's own checklist conditions — so the
chatbot can accurately explain WHY a stock scored the way it did,
grounded in this project's actual methodology rather than the model's
generic (and possibly inconsistent) understanding of these terms.

This content is original writing for this project, not scraped from
any external source — safe to store and retrieve verbatim, unlike
third-party copyrighted material.

Run: python -m app.rag.ingest_methodology
"""
from app.db import SessionLocal
from app.rag.store import add_document

METHODOLOGY_DOCS = [
    {
        "title": "Technical Score — overview",
        "content": (
            "The Technical Score evaluates 10 chart-based conditions built for swing "
            "and positional trades held over days to weeks, not intraday setups. Each "
            "condition contributes equally to the score, which is expressed as a "
            "percentage of the conditions that could be evaluated (conditions with "
            "insufficient data are excluded from both the numerator and denominator, "
            "not counted as failures). The 10 conditions are: price above the 20-day "
            "EMA, 20 EMA above 50 EMA, 50 EMA above 200 EMA (checking short, medium, "
            "and long-term trend alignment), RSI above 55 (momentum), ADX above 25 "
            "(trend strength), volume above 150% of the 20-day average, breakout above "
            "resistance, tight price consolidation before the breakout, no nearby "
            "overhead supply, and the stock's sector index outperforming the Nifty 50."
        ),
    },
    {
        "title": "Fundamental Score — overview",
        "content": (
            "The Fundamental Score evaluates 10 business-quality conditions aimed at "
            "long-term investors underwriting the business, not short-term traders. "
            "Like the Technical Score, each condition contributes equally and "
            "unavailable data is excluded rather than penalized. The 10 conditions "
            "are: Sales CAGR above 15%, Profit CAGR above 15%, Return on Equity (ROE) "
            "above 18%, Return on Capital Employed (ROCE) above 20%, Debt-to-Equity "
            "below 0.50, positive Operating Cash Flow, Promoter Holding above 40%, "
            "increasing FII and DII holdings together, accelerating earnings growth, "
            "and a reasonable valuation via PEG ratio below 2."
        ),
    },
    {
        "title": "Smart Money Score — overview and weighting",
        "content": (
            "The Smart Money Score is a third, independent axis from the other two, "
            "tracking institutional accumulation signals. Unlike the Technical and "
            "Fundamental scores (which weight every condition equally), the Smart "
            "Money Score is WEIGHTED: FII Increasing and Promoter Buying carry the "
            "most weight at 15 points each; DII Increasing, Mutual Fund Buying, High "
            "Delivery Volume, Strong Relative Strength, Breakout with Volume, and "
            "Earnings Growth carry 10 points each; ROCE above 20% and Low Debt carry "
            "5 points each, for a maximum of 100. The score is scaled to only the "
            "conditions that could actually be determined, so a stock with several "
            "unknown factors isn't unfairly capped below 100. Score bands: 85-100 is "
            "'Strong institutional accumulation', 70-84 is 'Positive smart money "
            "signals', 50-69 is 'Mixed signals; monitor closely', and below 50 is "
            "'Limited evidence of institutional accumulation'."
        ),
    },
    {
        "title": "Why three independent scores, not one combined score",
        "content": (
            "This screener deliberately keeps the Technical, Fundamental, and Smart "
            "Money scores separate rather than blending them into a single number. "
            "Technical analysis answers 'does the chart look right for a trade right "
            "now', fundamental analysis answers 'is this a good business to own', and "
            "smart money analysis answers 'are institutions and promoters "
            "accumulating this stock'. A stock can score well on one axis and poorly "
            "on another — for example, a fundamentally excellent business can have "
            "weak current technical setup, or vice versa — and collapsing that "
            "distinction into one score would hide which signal is actually driving "
            "the read. The three scores are meant to be read side by side, not "
            "averaged."
        ),
    },
    {
        "title": "Data limitations in this screener's scoring",
        "content": (
            "Some checklist conditions cannot currently be computed and will show as "
            "null/not-applicable rather than a guessed value: 'no nearby overhead "
            "supply' requires volume-profile analysis that isn't implemented yet; "
            "per-stock FII and DII holding percentages aren't available from the free "
            "NSE data source used (which only reports Promoter vs Public, not the "
            "finer institutional breakdown); mutual fund buying activity would "
            "require AMFI's monthly disclosure data, which isn't wired in. When a "
            "condition can't be computed, it is excluded from that score's "
            "calculation entirely rather than being treated as a failure — this "
            "means two stocks with different amounts of missing data can't be "
            "perfectly compared apples-to-apples on the raw score alone."
        ),
    },
]


def ingest_methodology() -> None:
    db = SessionLocal()
    try:
        total_chunks = 0
        for doc in METHODOLOGY_DOCS:
            n = add_document(
                db, text=doc["content"], source_type="project_methodology",
                title=doc["title"],
            )
            total_chunks += n
            print(f"  [methodology] '{doc['title']}': {n} chunk(s)")
        db.commit()
        print(f"Ingested {len(METHODOLOGY_DOCS)} methodology docs, {total_chunks} chunks total.")
    finally:
        db.close()


if __name__ == "__main__":
    ingest_methodology()
