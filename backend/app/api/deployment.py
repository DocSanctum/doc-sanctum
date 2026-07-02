from fastapi import APIRouter
from pydantic import BaseModel

from ..core.config import settings

router = APIRouter(tags=["deployment"])


class DeploymentStatus(BaseModel):
    mode: str


@router.get("/deployment", response_model=DeploymentStatus)
async def get_deployment_status() -> DeploymentStatus:
    return DeploymentStatus(mode=settings.deployment_mode)
