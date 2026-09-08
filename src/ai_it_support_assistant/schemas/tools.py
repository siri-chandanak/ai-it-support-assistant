from typing import Literal

from pydantic import BaseModel

ServiceHealth = Literal[
    "healthy",
    "degraded",
    "unavailable",
]


class ServiceStatus(BaseModel):
    service_name: str
    status: ServiceHealth
    message: str
