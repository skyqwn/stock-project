from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
