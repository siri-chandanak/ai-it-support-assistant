import os
from itertools import count

from locust import HttpUser, between, task

_request_ids = count(1)


class MCPPerformanceUser(HttpUser):
    host = os.getenv(
        "MCP_BASE_URL",
        "http://127.0.0.1:8001",
    )

    wait_time = between(1, 3)

    def on_start(self) -> None:
        token = os.getenv("PERF_TEST_TOKEN")

        self.mcp_headers = {
            "Content-Type": "application/json",
            "Accept": ("application/json, text/event-stream"),
        }

        if token:
            self.mcp_headers["Authorization"] = f"Bearer {token}"

    def _next_request_id(self) -> int:
        return next(_request_ids)

    @task(1)
    def discover_tools(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {},
        }

        with self._post_mcp(
            payload=payload,
            name="/mcp [tools/list]",
            timeout=10,
        ) as response:
            self._validate_mcp_response(
                response=response,
            )

    @task(3)
    def search_knowledge(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": "search_knowledge",
                "arguments": {
                    "query": ("What should a user do when VPN login fails?"),
                    "top_k": 3,
                },
            },
        }

        with self._post_mcp(
            payload=payload,
            name="/mcp [search_knowledge]",
            timeout=10,
        ) as response:
            self._validate_mcp_response(
                response=response,
            )

    @task(2)
    def get_service_status(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": "get_service_status",
                "arguments": {
                    "service_name": "vpn-gateway",
                },
            },
        }

        with self._post_mcp(
            payload=payload,
            name="/mcp [get_service_status]",
            timeout=10,
        ) as response:
            self._validate_mcp_response(
                response=response,
            )

    @task(1)
    def get_kubernetes_state(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": "get_kubernetes_state",
                "arguments": {
                    "resource_type": "deployment",
                    "resource_name": "ai-support-mcp",
                    "namespace": "ai-support",
                },
            },
        }

        with self._post_mcp(
            payload=payload,
            name="/mcp [get_kubernetes_state]",
            timeout=10,
        ) as response:
            self._validate_mcp_response(
                response=response,
            )

    def _post_mcp(
        self,
        *,
        payload: dict,
        name: str,
        timeout: int,
    ):
        try:
            return self.client.post(
                "/mcp",
                json=payload,
                headers=self.mcp_headers,
                name=name,
                catch_response=True,
                timeout=timeout,
            )

        except Exception as exc:
            raise RuntimeError(f"MCP transport failure for {name}: {exc}") from exc

    @staticmethod
    def _validate_mcp_response(
        *,
        response,
    ) -> None:
        if response.status_code == 0:
            error = getattr(
                response,
                "error",
                None,
            )

            response.failure(f"MCP transport failure: {error!r}")
            return

        if response.status_code != 200:
            response.failure(
                f"MCP HTTP failure: status={response.status_code} body={response.text[:300]}"
            )
            return

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if "application/json" not in content_type and "text/event-stream" not in content_type:
            response.failure(f"Unexpected MCP response content type: {content_type}")
            return

        if "application/json" in content_type:
            try:
                body = response.json()
            except ValueError:
                response.failure("MCP returned invalid JSON.")
                return

            if "error" in body:
                response.failure(f"MCP JSON-RPC error: {body['error']}")
                return

            result = body.get("result")

            if isinstance(result, dict):
                if result.get("isError") is True:
                    response.failure(f"MCP tool returned isError=true: {result}")
                    return

        response.success()
