import asyncio

import httpx2
from mcp import Client
from mcp.client.streamable_http import (
    streamable_http_client,
)


async def main() -> None:
    token = "TOKEN"

    async with httpx2.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
        },
        timeout=60.0,
    ) as http_client:
        transport = streamable_http_client(
            "http://127.0.0.1:8001/mcp",
            http_client=http_client,
        )

        async with Client(transport) as client:
            tools_result = await client.list_tools()

            print("TOOLS:")
            for tool in tools_result.tools:
                print(f"- {tool.name}")

            # result = await client.call_tool(
            # "get_service_status",
            # {
            #     "service_name": "vpn-gateway",
            # },
            # "get_kubernetes_state",
            # {
            #     "resource_type": "deployment",
            #     "resource_name": "demo-api",
            #     "namespace": "ai-it-support-test",
            # },
            # "search_knowledge",
            # {
            #     "query": "How do I troubleshoot VPN login failure?",
            #     "top_k": 5,
            # },
            # "propose_incident",
            # {
            #     "title": "VPN authentication degradation",
            #     "description": (
            #         "Multiple users are reporting elevated "
            #         "authentication latency while connecting to VPN."
            #     ),
            #     "severity": "medium",
            #     "service_name": "vpn-gateway",
            # },
            # "propose_restart_deployment",
            # {
            #     "deployment_name": "demo-api",
            #     "namespace": "ai-it-support-test",
            # },
            # )

            # print("\nRESULT:")
            # print(result)
            templates_result = await client.list_resource_templates()

            print("\nRESOURCE TEMPLATES:")
            for template in templates_result.resource_templates:
                print(f"- {template.uri_template}")

            # resource = await client.read_resource(
            #     "action://APR-B856DB80"
            # )

            # print("\nRESOURCE:")
            # print(resource)


if __name__ == "__main__":
    asyncio.run(main())
