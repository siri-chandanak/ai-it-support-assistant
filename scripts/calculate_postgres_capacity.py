from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServicePool:
    name: str
    replicas: int
    pool_size: int
    max_overflow: int

    @property
    def capacity_per_replica(
        self,
    ) -> int:
        return self.pool_size + self.max_overflow

    @property
    def maximum_connections(
        self,
    ) -> int:
        return self.replicas * self.capacity_per_replica


def env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)


def main() -> None:
    api = ServicePool(
        name="API",
        replicas=env_int(
            "PERF_API_REPLICAS",
            1,
        ),
        pool_size=env_int(
            "PERF_API_DB_POOL_SIZE",
            5,
        ),
        max_overflow=env_int(
            "PERF_API_DB_MAX_OVERFLOW",
            5,
        ),
    )

    mcp = ServicePool(
        name="MCP",
        replicas=env_int(
            "PERF_MCP_REPLICAS",
            1,
        ),
        pool_size=env_int(
            "PERF_MCP_DB_POOL_SIZE",
            5,
        ),
        max_overflow=env_int(
            "PERF_MCP_DB_MAX_OVERFLOW",
            5,
        ),
    )

    worker = ServicePool(
        name="Worker",
        replicas=env_int(
            "PERF_WORKER_REPLICAS",
            1,
        ),
        pool_size=env_int(
            "PERF_WORKER_DB_POOL_SIZE",
            5,
        ),
        max_overflow=env_int(
            "PERF_WORKER_DB_MAX_OVERFLOW",
            5,
        ),
    )

    reserved_connections = env_int(
        "PERF_DB_RESERVED_CONNECTIONS",
        10,
    )

    postgres_max_connections = env_int(
        "PERF_POSTGRES_MAX_CONNECTIONS",
        100,
    )

    services = [
        api,
        mcp,
        worker,
    ]

    application_connections = sum(service.maximum_connections for service in services)

    total_pressure = application_connections + reserved_connections

    remaining = postgres_max_connections - total_pressure

    usage_ratio = total_pressure / postgres_max_connections if postgres_max_connections > 0 else 0

    print()
    print("PostgreSQL Capacity")
    print("-------------------")
    print()

    for service in services:
        print(
            f"{service.name}: "
            f"{service.replicas} replicas × "
            f"("
            f"{service.pool_size} pool + "
            f"{service.max_overflow} overflow"
            f") "
            f"= "
            f"{service.maximum_connections}"
        )

    print()
    print(f"Application max connections: {application_connections}")
    print(f"Reserved/admin connections:   {reserved_connections}")
    print(f"Potential total pressure:     {total_pressure}")
    print(f"Postgres max_connections:     {postgres_max_connections}")
    print(f"Remaining connections:        {remaining}")
    print(f"Potential usage ratio:        {usage_ratio * 100:.1f}%")

    print()

    if remaining < 0:
        print("RESULT: FAIL - configured pools can exceed PostgreSQL capacity.")
    elif usage_ratio >= 0.90:
        print("RESULT: WARNING - configured pools can consume at least 90% of PostgreSQL capacity.")
    elif usage_ratio >= 0.75:
        print("RESULT: REVIEW - connection pressure is above 75%.")
    else:
        print("RESULT: OK - theoretical pressure is below the initial warning level.")

    print()


if __name__ == "__main__":
    main()
