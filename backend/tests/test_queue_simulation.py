from app.simulation.queue_simulator import run_queue_simulation


def test_queue_simulation_has_no_orphaned_slots():
    result = run_queue_simulation(total=25, max_concurrency=5)
    assert result.total == 25
    assert result.completed + result.escalated == 25
    assert result.orphaned_slots == 0
