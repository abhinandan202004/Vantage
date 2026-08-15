from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central app settings. Values are read from environment variables
    or a .env file in the backend/ directory.
    """
    database_url: str = "postgresql+psycopg://screener_user:screener_pass@localhost:5432/screener_db"
    nifty_symbol: str = "^NSEI"  # yfinance ticker for Nifty 50 index
    default_lookback_days: int = 400  # enough for 200 EMA + buffer
    groq_api_key: str = ""  # get one free at console.groq.com — required for /chat to work
    groq_model: str = "llama-3.3-70b-versatile"

    class Config:
        env_file = ".env"


settings = Settings()
