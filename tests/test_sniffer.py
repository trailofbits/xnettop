"""Tests for PacketSniffer."""

from __future__ import annotations

import queue
import threading
from unittest.mock import MagicMock, patch

from xnettop.sniffer import PacketInfo, PacketSniffer


class TestPacketSnifferStartStop:
    """Test start/stop idempotency and thread safety."""

    def test_start_is_idempotent(self):
        """Calling start() multiple times should only create one sniffer."""
        with patch("xnettop.sniffer.AsyncSniffer") as mock_sniffer_class:
            mock_sniffer = MagicMock()
            mock_sniffer_class.return_value = mock_sniffer

            sniffer = PacketSniffer(interface=None)
            try:
                sniffer.start()
                sniffer1 = sniffer._sniffer

                sniffer.start()
                sniffer2 = sniffer._sniffer

                assert sniffer1 is sniffer2
                assert sniffer._running is True
                assert mock_sniffer_class.call_count == 1
            finally:
                sniffer.stop()

    def test_stop_is_idempotent(self):
        """Calling stop() multiple times should not raise."""
        sniffer = PacketSniffer(interface=None)
        sniffer.stop()
        sniffer.stop()
        sniffer.stop()

    def test_stop_without_start(self):
        """Calling stop() without start() should not raise."""
        sniffer = PacketSniffer(interface=None)
        sniffer.stop()

    def test_concurrent_start_calls(self):
        """Concurrent start() calls should only create one sniffer."""
        with patch("xnettop.sniffer.AsyncSniffer") as mock_sniffer_class:
            mock_sniffer = MagicMock()
            mock_sniffer_class.return_value = mock_sniffer

            sniffer = PacketSniffer(interface=None)
            sniffers_seen = []
            errors = []

            def call_start():
                try:
                    sniffer.start()
                    sniffers_seen.append(sniffer._sniffer)
                except Exception as e:
                    errors.append(e)

            try:
                callers = [threading.Thread(target=call_start) for _ in range(10)]
                for t in callers:
                    t.start()
                for t in callers:
                    t.join()

                assert len(errors) == 0
                assert all(s is sniffers_seen[0] for s in sniffers_seen)
            finally:
                sniffer.stop()


class TestPacketSnifferQueue:
    """Test queue handling and overflow behavior."""

    def test_drain_packets_returns_all(self):
        """drain_packets() should return all queued packets."""
        sniffer = PacketSniffer(interface=None)
        packet1 = PacketInfo("1.1.1.1", "2.2.2.2", 1000, 80, "tcp", 100, False)
        packet2 = PacketInfo("3.3.3.3", "4.4.4.4", 2000, 443, "tcp", 200, False)

        sniffer.packet_queue.put(packet1)
        sniffer.packet_queue.put(packet2)

        packets = sniffer.drain_packets()
        assert len(packets) == 2
        assert packets[0] is packet1
        assert packets[1] is packet2

    def test_drain_packets_clears_queue(self):
        """drain_packets() should clear the queue."""
        sniffer = PacketSniffer(interface=None)
        packet = PacketInfo("1.1.1.1", "2.2.2.2", 1000, 80, "tcp", 100, False)
        sniffer.packet_queue.put(packet)

        sniffer.drain_packets()

        assert sniffer.packet_queue.empty()

    def test_drain_packets_empty_queue(self):
        """drain_packets() should return empty list for empty queue."""
        sniffer = PacketSniffer(interface=None)
        packets = sniffer.drain_packets()
        assert packets == []

    def test_queue_overflow_drops_oldest(self):
        """When queue is full, oldest packet should be dropped."""
        small_queue = queue.Queue(maxsize=2)
        sniffer = PacketSniffer(interface=None)
        sniffer.packet_queue = small_queue

        packet1 = PacketInfo("1.1.1.1", "2.2.2.2", 1, 80, "tcp", 100, False)
        packet2 = PacketInfo("1.1.1.1", "2.2.2.2", 2, 80, "tcp", 100, False)
        packet3 = PacketInfo("1.1.1.1", "2.2.2.2", 3, 80, "tcp", 100, False)

        small_queue.put(packet1)
        small_queue.put(packet2)

        mock_packet = MagicMock()
        with patch.object(sniffer, "_parse_packet", return_value=packet3):
            sniffer._packet_callback(mock_packet)

        packets = sniffer.drain_packets()
        assert len(packets) == 2
        src_ports = {p.src_port for p in packets}
        assert 3 in src_ports


class TestPacketSnifferIsRunning:
    """Test is_running property."""

    def test_is_running_initially_false(self):
        """is_running should be False before start()."""
        sniffer = PacketSniffer(interface=None)
        assert sniffer.is_running is False

    def test_is_running_true_after_start(self):
        """is_running should be True after start()."""
        with patch("xnettop.sniffer.AsyncSniffer") as mock_sniffer_class:
            mock_sniffer = MagicMock()
            mock_sniffer_class.return_value = mock_sniffer

            sniffer = PacketSniffer(interface=None)
            try:
                sniffer.start()
                assert sniffer.is_running is True
            finally:
                sniffer.stop()

    def test_is_running_false_after_stop(self):
        """is_running should be False after stop()."""
        with patch("xnettop.sniffer.AsyncSniffer") as mock_sniffer_class:
            mock_sniffer = MagicMock()
            mock_sniffer_class.return_value = mock_sniffer

            sniffer = PacketSniffer(interface=None)
            sniffer.start()
            sniffer.stop()
            assert sniffer.is_running is False
