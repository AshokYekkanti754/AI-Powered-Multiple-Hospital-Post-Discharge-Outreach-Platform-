from __future__ import annotations
import uuid
from dataclasses import dataclass
from app.core.redis import InMemorySemaphore


@dataclass
class SimulationResult:
    total: int
    completed: int
    escalated: int
    orphaned_slots: int


def run_queue_simulation(total: int = 25, max_concurrency: int = 5) -> SimulationResult:
    semaphore = InMemorySemaphore()
    completed = 0
    escalated = 0
    for index in range(total):
        with semaphore.acquire("simulation-hospital", max_concurrency) as acquired:
            if not acquired:
                continue
            if index % 7 == 0:
                escalated += 1
            else:
                completed += 1
    return SimulationResult(total=total, completed=completed, escalated=escalated, orphaned_slots=semaphore.active_count("simulation-hospital"))


if __name__ == "__main__":
    print(run_queue_simulation())
