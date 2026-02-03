"""Traffic aggregator that maps packets to processes and tracks bandwidth."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xnettop.connections import ConnectionMonitor
    from xnettop.sniffer import PacketInfo, PacketSniffer


@dataclass
class TrafficSample:
    """A timestamped traffic sample."""

    timestamp: float
    upload_bytes: int
    download_bytes: int


@dataclass
class ProcessStats:
    """Traffic statistics for a single process."""

    pid: int
    name: str
    upload_bytes: int = 0
    download_bytes: int = 0
    upload_rate: float = 0.0
    download_rate: float = 0.0
    _samples: deque[TrafficSample] = field(default_factory=lambda: deque(maxlen=60))

    def add_traffic(self, upload: int, download: int, timestamp: float) -> None:
        """Add traffic to this process."""
        self.upload_bytes += upload
        self.download_bytes += download
        self._samples.append(TrafficSample(timestamp, upload, download))

    def calculate_rate(self, window_seconds: float = 2.0) -> None:
        """Calculate upload/download rate over the sliding window."""
        now = time.time()
        cutoff = now - window_seconds
        upload_sum = 0
        download_sum = 0
        earliest_time = now
        for sample in self._samples:
            if sample.timestamp >= cutoff:
                upload_sum += sample.upload_bytes
                download_sum += sample.download_bytes
                if sample.timestamp < earliest_time:
                    earliest_time = sample.timestamp
        duration = now - earliest_time
        if duration > 0:
            self.upload_rate = upload_sum / duration
            self.download_rate = download_sum / duration
        else:
            self.upload_rate = 0.0
            self.download_rate = 0.0


UNKNOWN_PID = -1
UNKNOWN_PROCESS_NAME = "(unknown)"


@dataclass
class TrafficAggregator:
    """Aggregate traffic stats by process."""

    connection_monitor: ConnectionMonitor
    packet_sniffer: PacketSniffer
    _stats: dict[int, ProcessStats] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _running: bool = False
    _thread: threading.Thread | None = None
    update_interval: float = 0.5

    def start(self) -> None:
        """Start the aggregator background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
        thread = threading.Thread(target=self._aggregator_loop, daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the aggregator."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            thread = self._thread
            self._thread = None
        if thread:
            thread.join(timeout=2.0)

    def _aggregator_loop(self) -> None:
        """Background loop to process packets."""
        while True:
            with self._lock:
                if not self._running:
                    break
            self._process_packets()
            self._update_rates()
            time.sleep(self.update_interval)

    def _process_packets(self) -> None:
        """Process all queued packets."""
        packets = self.packet_sniffer.drain_packets()
        now = time.time()
        with self._lock:
            for packet in packets:
                self._attribute_packet(packet, now)

    def _attribute_packet(self, packet: PacketInfo, timestamp: float) -> None:
        """Attribute a packet to a process."""
        is_upload = self.connection_monitor.is_local_addr(packet.src_ip)
        is_download = self.connection_monitor.is_local_addr(packet.dst_ip)
        if is_upload and is_download:
            return
        if is_upload:
            local_ip, local_port = packet.src_ip, packet.src_port
            remote_ip, remote_port = packet.dst_ip, packet.dst_port
        elif is_download:
            local_ip, local_port = packet.dst_ip, packet.dst_port
            remote_ip, remote_port = packet.src_ip, packet.src_port
        else:
            return
        conn = self.connection_monitor.lookup_connection(
            local_ip, local_port, remote_ip, remote_port, packet.protocol
        )
        if conn:
            pid = conn.pid
            name = conn.process_name
        else:
            pid = UNKNOWN_PID
            name = UNKNOWN_PROCESS_NAME
        if pid not in self._stats:
            self._stats[pid] = ProcessStats(pid=pid, name=name)
        upload = packet.size if is_upload else 0
        download = packet.size if is_download else 0
        self._stats[pid].add_traffic(upload, download, timestamp)

    def _update_rates(self) -> None:
        """Update rate calculations for all processes."""
        with self._lock:
            for stats in self._stats.values():
                stats.calculate_rate()

    def get_stats(self) -> list[ProcessStats]:
        """Get current stats for all processes, sorted by total rate.

        Returns snapshots of ProcessStats objects to avoid TOCTOU races with
        the background aggregator thread.
        """
        with self._lock:
            stats_list = [
                ProcessStats(
                    pid=s.pid,
                    name=s.name,
                    upload_bytes=s.upload_bytes,
                    download_bytes=s.download_bytes,
                    upload_rate=s.upload_rate,
                    download_rate=s.download_rate,
                )
                for s in self._stats.values()
            ]
        stats_list.sort(key=lambda s: s.upload_rate + s.download_rate, reverse=True)
        return stats_list

    def get_stats_by_pid(self, pid: int) -> ProcessStats | None:
        """Get stats for a specific process."""
        with self._lock:
            return self._stats.get(pid)

    def clear_stats(self) -> None:
        """Clear all accumulated stats."""
        with self._lock:
            self._stats.clear()
