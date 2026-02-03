"""Tests for TrafficAggregator."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from xnettop.aggregator import ProcessStats, TrafficAggregator
from xnettop.connections import ConnectionMonitor
from xnettop.sniffer import PacketSniffer


class TestTrafficAggregatorStartStop:
    """Test start/stop idempotency and thread safety."""

    def test_start_is_idempotent(self):
        """Calling start() multiple times should only create one thread."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)
        mock_sniffer.drain_packets.return_value = []

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
            update_interval=0.5,
        )
        try:
            aggregator.start()
            thread1 = aggregator._thread

            aggregator.start()
            thread2 = aggregator._thread

            assert thread1 is thread2
            assert aggregator._running is True
        finally:
            aggregator.stop()

    def test_stop_is_idempotent(self):
        """Calling stop() multiple times should not raise."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
        )
        aggregator.stop()
        aggregator.stop()
        aggregator.stop()

    def test_stop_without_start(self):
        """Calling stop() without start() should not raise."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
        )
        aggregator.stop()

    def test_concurrent_start_calls(self):
        """Concurrent start() calls should only create one thread."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)
        mock_sniffer.drain_packets.return_value = []

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
            update_interval=0.5,
        )
        threads_seen = []
        errors = []

        def call_start():
            try:
                aggregator.start()
                threads_seen.append(aggregator._thread)
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
            aggregator.stop()


class TestGetStatsReturnsCopies:
    """Test that get_stats() returns copies, not live references."""

    def test_get_stats_returns_copies(self):
        """Modifying returned stats should not affect internal state."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)
        mock_sniffer.drain_packets.return_value = []

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
        )
        aggregator._stats[1234] = ProcessStats(
            pid=1234,
            name="test",
            upload_bytes=100,
            download_bytes=200,
        )

        stats = aggregator.get_stats()
        assert len(stats) == 1
        stats[0].upload_bytes = 9999

        internal_stats = aggregator._stats[1234]
        assert internal_stats.upload_bytes == 100

    def test_get_stats_snapshot_is_not_same_object(self):
        """Returned ProcessStats should be different objects."""
        mock_monitor = MagicMock(spec=ConnectionMonitor)
        mock_sniffer = MagicMock(spec=PacketSniffer)

        aggregator = TrafficAggregator(
            connection_monitor=mock_monitor,
            packet_sniffer=mock_sniffer,
        )
        aggregator._stats[1234] = ProcessStats(pid=1234, name="test")

        stats = aggregator.get_stats()
        assert stats[0] is not aggregator._stats[1234]


class TestProcessStats:
    """Test ProcessStats rate calculation."""

    def test_calculate_rate_empty_samples(self):
        """Rate should be 0 with no samples."""
        stats = ProcessStats(pid=1234, name="test")
        stats.calculate_rate()
        assert stats.upload_rate == 0.0
        assert stats.download_rate == 0.0

    def test_calculate_rate_with_samples(self):
        """Rate should be calculated from samples within window."""
        stats = ProcessStats(pid=1234, name="test")
        now = time.time()
        stats.add_traffic(1000, 2000, now - 1.0)
        stats.add_traffic(1000, 2000, now - 0.5)
        stats.calculate_rate(window_seconds=2.0)

        assert stats.upload_rate > 0
        assert stats.download_rate > 0

    def test_add_traffic_accumulates(self):
        """Traffic should accumulate over multiple calls."""
        stats = ProcessStats(pid=1234, name="test")
        stats.add_traffic(100, 200, time.time())
        stats.add_traffic(100, 200, time.time())

        assert stats.upload_bytes == 200
        assert stats.download_bytes == 400
