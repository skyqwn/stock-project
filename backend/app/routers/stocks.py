from fastapi import APIRouter, HTTPException

from app import kis_client

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stocks/{code}/price")
async def stock_price(code: str) -> dict:
    try:
        return await kis_client.get_price(code)
    except kis_client.KisError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
