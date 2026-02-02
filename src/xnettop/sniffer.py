"""Packet sniffer using scapy to capture network traffic."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scapy.all import IP, TCP, UDP, AsyncSniffer, IPv6, conf

if TYPE_CHECKING:
    from scapy.packet import Packet

conf.verb = 0


@dataclass
class PacketInfo:
    """Parsed information from a captured packet."""

    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    size: int
    is_ipv6: bool


@dataclass
class PacketSniffer:
    """Capture and parse network packets using scapy."""

    interface: str | None = None
    packet_queue: queue.Queue[PacketInfo] = field(default_factory=lambda: queue.Queue(maxsize=10000))
    _sniffer: AsyncSniffer | None = None
    _running: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _packet_callback(self, packet: Packet) -> None:
        """Process a captured packet."""
        info = self._parse_packet(packet)
        if info is None:
            return
        try:
            self.packet_queue.put_nowait(info)
        except queue.Full:
            try:
                self.packet_queue.get_nowait()
                self.packet_queue.put_nowait(info)
            except queue.Empty:
                pass

    def _parse_packet(self, packet: Packet) -> PacketInfo | None:
        """Extract relevant info from a packet."""
        ip_layer = None
        is_ipv6 = False
        if IP in packet:
            ip_layer = packet[IP]
        elif IPv6 in packet:
            ip_layer = packet[IPv6]
            is_ipv6 = True
        else:
            return None

        src_ip = ip_layer.src
        dst_ip = ip_layer.dst
        size = len(packet)
        if TCP in packet:
            tcp = packet[TCP]
            return PacketInfo(
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=tcp.sport,
                dst_port=tcp.dport,
                protocol="tcp",
                size=size,
                is_ipv6=is_ipv6,
            )
        if UDP in packet:
            udp = packet[UDP]
            return PacketInfo(
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=udp.sport,
                dst_port=udp.dport,
                protocol="udp",
                size=size,
                is_ipv6=is_ipv6,
            )
        return None

    def start(self) -> None:
        """Start capturing packets."""
        with self._lock:
            if self._running:
                return
            self._running = True
            filter_str = "tcp or udp"
            self._sniffer = AsyncSniffer(
                iface=self.interface,
                filter=filter_str,
                prn=self._packet_callback,
                store=False,
            )
            self._sniffer.start()

    def stop(self) -> None:
        """Stop capturing packets."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._sniffer:
                self._sniffer.stop()
                self._sniffer = None

    def drain_packets(self) -> list[PacketInfo]:
        """Get all queued packets, clearing the queue."""
        packets = []
        while True:
            try:
                packets.append(self.packet_queue.get_nowait())
            except queue.Empty:
                break
        return packets

    @property
    def is_running(self) -> bool:
        """Check if sniffer is running."""
        with self._lock:
            return self._running
