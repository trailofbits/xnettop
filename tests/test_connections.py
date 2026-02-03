"""Tests for ConnectionMonitor."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

from xnettop.connections import ConnectionMonitor


class TestConnectionMonitorStartStop:
    """Test start/stop idempotency and thread safety."""

    def test_start_is_idempotent(self, mock_psutil_net_if_addrs, mock_psutil_connections):
        """Calling start() multiple times should only create one thread."""
        with patch("psutil.Process") as mock_proc_class:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "test"
            mock_proc.cmdline.return_value = []
            mock_proc_class.return_value = mock_proc

            monitor = ConnectionMonitor(refresh_interval=0.5)
            try:
                monitor.start()
                thread1 = monitor._thread

                monitor.start()
                thread2 = monitor._thread

                assert thread1 is thread2
                assert monitor._running is True
            finally:
                monitor.stop()

    def test_stop_is_idempotent(self, mock_psutil_net_if_addrs):
        """Calling stop() multiple times should not raise."""
        monitor = ConnectionMonitor(refresh_interval=0.5)
        monitor.stop()
        monitor.stop()
        monitor.stop()

    def test_stop_without_start(self, mock_psutil_net_if_addrs):
        """Calling stop() without start() should not raise."""
        monitor = ConnectionMonitor(refresh_interval=0.5)
        monitor.stop()

    def test_concurrent_start_calls(self, mock_psutil_net_if_addrs, mock_psutil_connections):
        """Concurrent start() calls should only create one thread."""
        with patch("psutil.Process") as mock_proc_class:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "test"
            mock_proc.cmdline.return_value = []
            mock_proc_class.return_value = mock_proc

            monitor = ConnectionMonitor(refresh_interval=0.5)
            threads_seen = []
            errors = []

            def call_start():
                try:
                    monitor.start()
                    threads_seen.append(monitor._thread)
                except Exception as e:
                    errors.append(e)

            try:
                callers = [threading.Thread(target=call_start) for _ in range(10)]
                for t in callers:
                    t.start()
                for t in callers:
                    t.join()

                assert len(errors) == 0
                assert all(t is threads_seen[0] for t in threads_seen)
            finally:
                monitor.stop()


class TestConnectionMonitorProcessCache:
    """Test process info caching behavior."""

    def test_process_info_is_cached(self, mock_psutil_net_if_addrs):
        """Process info should be cached after first lookup."""
        with patch("psutil.Process") as mock_proc_class:
            mock_proc = MagicMock()
            mock_proc.name.return_value = "cached_process"
            mock_proc.cmdline.return_value = ["cached_process"]
            mock_proc_class.return_value = mock_proc

            monitor = ConnectionMonitor(refresh_interval=0.5)
            info1 = monitor._get_process_info(1234)
            info2 = monitor._get_process_info(1234)

            assert info1 is info2
            assert mock_proc_class.call_count == 1

    def test_process_info_handles_no_such_process(self, mock_psutil_net_if_addrs):
        """Should return None for non-existent processes."""
        import psutil

        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(9999)):
            monitor = ConnectionMonitor(refresh_interval=0.5)
            info = monitor._get_process_info(9999)
            assert info is None

    def test_process_info_handles_access_denied(self, mock_psutil_net_if_addrs):
        """Should return None when access is denied."""
        import psutil

        with patch("psutil.Process", side_effect=psutil.AccessDenied(1)):
            monitor = ConnectionMonitor(refresh_interval=0.5)
            info = monitor._get_process_info(1)
            assert info is None


class TestConnectionMonitorLookup:
    """Test connection lookup functionality."""

    def test_is_local_addr(self, mock_psutil_net_if_addrs):
        """Should correctly identify local addresses."""
        monitor = ConnectionMonitor(refresh_interval=0.5)
        monitor._refresh_local_addrs()

        assert monitor.is_local_addr("192.168.1.100") is True
        assert monitor.is_local_addr("127.0.0.1") is True
        assert monitor.is_local_addr("::1") is True
        assert monitor.is_local_addr("8.8.8.8") is False

    def test_lookup_connection_returns_none_when_empty(self, mock_psutil_net_if_addrs):
        """Should return None when connection table is empty."""
        monitor = ConnectionMonitor(refresh_interval=0.5)
        result = monitor.lookup_connection("127.0.0.1", 8080, "192.168.1.1", 443, "tcp")
        assert result is None
