# Queue Simulation Guide

Run from the project root:

```powershell
$env:PYTHONPATH = "backend"
..\.venv\Scripts\python.exe -c "from app.simulation.queue_simulator import run_queue_simulation; print(run_queue_simulation(25, 5))"
```

The simulator drives 25 mock tasks through successful and escalated outcomes under five slots and reports orphaned Redis/in-memory slots. The expected orphaned count is zero.
