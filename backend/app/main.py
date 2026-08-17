from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import stock, chat, auth, portfolio, stocks, quant

app = FastAPI(title="Stock Screener API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite / CRA dev servers
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(stocks.router)
app.include_router(quant.router)  # reserved for future quant/backtesting features


@app.get("/health")
def health():
    return {"status": "ok"}
