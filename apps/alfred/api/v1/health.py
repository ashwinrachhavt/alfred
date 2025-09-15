from fastapi import APIRouter

router = APIRouter(prefix="/healthz", tags=["health"])


@router.get("")
def health():
    return {"ok": True}
