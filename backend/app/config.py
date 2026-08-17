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

    # INSECURE DEFAULT — this is fine for local dev only. Generate a real
    # secret for anything beyond your own machine:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    # and set JWT_SECRET_KEY in .env. Anyone who knows this default value
    # could forge valid login tokens for your app.
    jwt_secret_key: str = "INSECURE-DEV-ONLY-CHANGE-ME-IN-ENV"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"


settings = Settings()
