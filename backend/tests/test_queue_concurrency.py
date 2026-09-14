from concurrent.futures import ThreadPoolExecutor
import threading
from app.core.redis import InMemorySemaphore


def test_one_hundred_workers_never_exceed_ten_slots():
    semaphore = InMemorySemaphore()
    hospital_id = "hospital-stress"
    active = 0
    maximum = 0
    guard = threading.Lock()

    def worker(_):
        nonlocal active, maximum
        with semaphore.acquire(hospital_id, 10) as acquired:
            if not acquired:
                return False
            with guard:
                active += 1
                maximum = max(maximum, active)
            import time
            time.sleep(0.005)
            with guard:
                active -= 1
            return True

    with ThreadPoolExecutor(max_workers=100) as pool:
        results = list(pool.map(worker, range(100)))
    assert maximum <= 10
    assert any(results)
    assert semaphore.active_count(hospital_id) == 0
