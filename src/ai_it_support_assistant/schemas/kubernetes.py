from typing import Literal

from pydantic import BaseModel


class DeploymentState(BaseModel):
    resource_type: Literal["deployment"] = "deployment"
    name: str
    namespace: str

    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int


class PodState(BaseModel):
    resource_type: Literal["pod"] = "pod"
    name: str
    namespace: str

    phase: str
    ready: bool
    restart_count: int
