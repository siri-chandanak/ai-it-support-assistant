# from locust import HttpUser, between, task


# class AISupportUser(HttpUser):
#     wait_time = between(1, 3)

#     @task
#     def health(self) -> None:
#         self.client.get("/api/v1/health")

import os

from locust import HttpUser, between, task

from performance.scenarios.agent import (
    register_agent_tasks,
)
from performance.scenarios.approvals import (
    register_approval_tasks,
)
from performance.scenarios.mcp import (
    MCPPerformanceUser,
)
from performance.scenarios.rag import (
    register_rag_tasks,
)
from performance.scenarios.retrieval import (
    register_retrieval_tasks,
)


class AISupportUser(HttpUser):
    host = os.getenv(
        "API_PERF_HOST",
        "http://127.0.0.1:8000",
    )

    wait_time = between(1, 3)

    def on_start(self) -> None:
        token = os.getenv("PERF_TEST_TOKEN")

        if token:
            self.auth_headers = {
                "Authorization": (f"Bearer {token}"),
            }
        else:
            self.auth_headers = {}

    @task(1)
    def health(self) -> None:
        with self.client.get(
            "/api/v1/health",
            name="/api/v1/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
                return

            response.failure(f"Health check failed: {response.status_code}")


register_retrieval_tasks(AISupportUser)

register_rag_tasks(AISupportUser)

register_agent_tasks(AISupportUser)

register_approval_tasks(AISupportUser)


# Keep imported so Locust discovers the
# separate MCP HttpUser class.
__all__ = [
    "AISupportUser",
    "MCPPerformanceUser",
]
