from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerCapacity:
    arrival_rate_per_minute: float
    average_execution_minutes: float
    measured_worker_throughput_per_minute: float
    safety_headroom: float

    @property
    def average_concurrent_work(
        self,
    ) -> float:
        """
        Little's Law:

        L = lambda * W

        L = average work in the system
        lambda = arrival rate
        W = average time in system
        """
        return self.arrival_rate_per_minute * self.average_execution_minutes

    @property
    def minimum_throughput_slots(
        self,
    ) -> int:
        if self.measured_worker_throughput_per_minute <= 0:
            raise ValueError("Measured worker throughput must be greater than zero.")

        return math.ceil(self.arrival_rate_per_minute / self.measured_worker_throughput_per_minute)

    @property
    def recommended_slots(
        self,
    ) -> int:
        minimum = max(
            math.ceil(self.average_concurrent_work),
            self.minimum_throughput_slots,
        )

        return math.ceil(minimum * (1 + self.safety_headroom))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Calculate worker capacity using measured throughput and Little's Law.")
    )

    parser.add_argument(
        "--arrival-rate",
        type=float,
        required=True,
        help=("Average incoming jobs per minute."),
    )

    parser.add_argument(
        "--average-duration",
        type=float,
        required=True,
        help=("Average execution duration in minutes."),
    )

    parser.add_argument(
        "--worker-throughput",
        type=float,
        required=True,
        help=("Measured jobs completed per minute by one worker concurrency slot."),
    )

    parser.add_argument(
        "--headroom",
        type=float,
        default=0.25,
        help=("Safety headroom as decimal. Default: 0.25 (25%%)."),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    capacity = WorkerCapacity(
        arrival_rate_per_minute=(args.arrival_rate),
        average_execution_minutes=(args.average_duration),
        measured_worker_throughput_per_minute=(args.worker_throughput),
        safety_headroom=args.headroom,
    )

    print()
    print("Worker Capacity")
    print("---------------")
    print()

    print(f"Arrival rate:               {capacity.arrival_rate_per_minute:.2f} jobs/min")

    print(f"Average execution duration: {capacity.average_execution_minutes:.2f} min")

    print(
        "Measured worker throughput: "
        f"{capacity.measured_worker_throughput_per_minute:.2f} "
        "jobs/min/slot"
    )

    print(f"Little's Law concurrency:   {capacity.average_concurrent_work:.2f}")

    print(f"Minimum throughput slots:   {capacity.minimum_throughput_slots}")

    print(f"Safety headroom:            {capacity.safety_headroom * 100:.0f}%")

    print(f"Recommended slots:          {capacity.recommended_slots}")

    print()


if __name__ == "__main__":
    main()
