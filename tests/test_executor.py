"""Tests for parallel executor."""


from pinpoint_eda.executor import ScanExecutor


class TestScanExecutor:
    def test_map_parallel_basic(self):
        executor = ScanExecutor(max_workers=3)
        results = executor.map_parallel(lambda x: x * 2, [1, 2, 3])

        values = {item: result for item, result, error in results}
        assert values == {1: 2, 2: 4, 3: 6}
        assert all(error is None for _, _, error in results)

    def test_map_parallel_with_errors(self):
        executor = ScanExecutor(max_workers=3)

        def maybe_fail(x):
            if x == 2:
                raise ValueError("boom")
            return x * 2

        results = executor.map_parallel(maybe_fail, [1, 2, 3])

        errors = {item: error for item, result, error in results if error}
        successes = {item: result for item, result, error in results if not error}

        assert 2 in errors
        assert isinstance(errors[2], ValueError)
        assert successes[1] == 2
        assert successes[3] == 6

    def test_shutdown_flag(self):
        executor = ScanExecutor(max_workers=2)
        assert not executor.should_stop
        executor.request_shutdown()
        assert executor.should_stop

    def test_map_parallel_empty(self):
        executor = ScanExecutor(max_workers=2)
        results = executor.map_parallel(lambda x: x, [])
        assert results == []
