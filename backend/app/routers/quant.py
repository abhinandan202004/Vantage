"""
RESERVED for future quant/backtesting features — deliberately just a
stub for now. Details haven't been specified yet; this exists so the
routing pattern and registration point are already in place (see
main.py) rather than needing to wire up a new router from scratch
later. Delete or flesh out once requirements are known — see the
"Adding a new feature module" section in README.md for the pattern
every other router in this project follows.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/quant", tags=["quant"])


@router.get("/status")
def status():
    return {
        "status": "not yet implemented",
        "note": "Reserved for backtesting / quant features — see README.",
    }
