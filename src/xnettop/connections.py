"""Connection monitor using psutil to map network connections to processes."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ConnectionInfo:
    """Information about a network connection."""

    pid: int
    process_name: str
    local_addr: tuple[str, int]
    remote_addr: tuple[str, int] | None
    protocol: str
    status: str


@dataclass
class ProcessInfo:
    """Cached process information."""

    pid: int
    name: str
    cmdline: str


# (local_ip, local_port, remote_ip, remote_port, proto)
ConnectionKey = tuple[str, int, str, int, str]


def make_connection_key(
    local_ip: str, local_port: int, remote_ip: str, remote_port: int, protocol: str
) -> ConnectionKey:
    """Create a normalized connection key for lookups."""
    return (local_ip, local_port, remote_ip, remote_port, protocol.lower())


@dataclass
class ConnectionMonitor:
    """Monitor network connections and map them to processes."""

    refresh_interval: float = 1.0
    _connections: dict[ConnectionKey, ConnectionInfo] = field(default_factory=dict)
    _processes: dict[int, ProcessInfo] = field(default_factory=dict)
    _local_addrs: set[str] = field(default_factory=set)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _running: bool = False
    _thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the connection monitor background thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._refresh_local_addrs()
        self._refresh_connections()
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the connection monitor."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            thread = self._thread
            self._thread = None
        if thread:
            thread.join(timeout=2.0)

    def _monitor_loop(self) -> None:
        """Background loop to refresh connections."""
        while True:
            with self._lock:
                if not self._running:
                    break
            self._refresh_connections()
            time.sleep(self.refresh_interval)

    def _refresh_local_addrs(self) -> None:
        """Refresh the set of local IP addresses."""
        addrs = set()
        for _, iface_addrs in psutil.net_if_addrs().items():
            for addr in iface_addrs:
                if addr.family.name in ("AF_INET", "AF_INET6"):
                    addrs.add(addr.address)
        addrs.add("127.0.0.1")
        addrs.add("::1")
        addrs.add("0.0.0.0")
        addrs.add("::")
        with self._lock:
            self._local_addrs = addrs

    def _get_process_info(self, pid: int) -> ProcessInfo | None:
        """Get cached process info, refreshing if needed."""
        with self._lock:
            if pid in self._processes:
                return self._processes[pid]
        try:
            proc = psutil.Process(pid)
            info = ProcessInfo(
                pid=pid,
                name=proc.name(),
                cmdline=" ".join(proc.cmdline()) if proc.cmdline() else proc.name(),
            )
            with self._lock:
                self._processes[pid] = info
            return info
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def _refresh_connections(self) -> None:
        """Refresh the connection table."""
        new_connections: dict[ConnectionKey, ConnectionInfo] = {}
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.pid is None:
                    continue
                proc_info = self._get_process_info(conn.pid)
                if proc_info is None:
                    continue
                local_addr = conn.laddr if conn.laddr else ("", 0)
                remote_addr = conn.raddr if conn.raddr else None
                protocol = "tcp" if conn.type.name == "SOCK_STREAM" else "udp"
                remote_ip = remote_addr[0] if remote_addr else ""
                remote_port = remote_addr[1] if remote_addr else 0
                key = make_connection_key(
                    local_addr[0], local_addr[1], remote_ip, remote_port, protocol
                )
                info = ConnectionInfo(
                    pid=conn.pid,
                    process_name=proc_info.name,
                    local_addr=local_addr,
                    remote_addr=remote_addr,
                    protocol=protocol,
                    status=conn.status if hasattr(conn, "status") else "",
                )
                new_connections[key] = info
        except psutil.AccessDenied:
            pass
        with self._lock:
            self._connections = new_connections
            self._cleanup_stale_processes()

    def _cleanup_stale_processes(self) -> None:
        """Remove process info for PIDs no longer in connection table."""
        active_pids = {info.pid for info in self._connections.values()}
        stale_pids = set(self._processes.keys()) - active_pids
        for pid in stale_pids:
            del self._processes[pid]

    def is_local_addr(self, ip: str) -> bool:
        """Check if an IP address is local to this machine."""
        with self._lock:
            return ip in self._local_addrs

    def lookup_connection(
        self, local_ip: str, local_port: int, remote_ip: str, remote_port: int, protocol: str
    ) -> ConnectionInfo | None:
        """Look up a connection by its addresses."""
        key = make_connection_key(local_ip, local_port, remote_ip, remote_port, protocol)
        with self._lock:
            if key in self._connections:
                return self._connections[key]
            reverse_key = make_connection_key(
                remote_ip, remote_port, local_ip, local_port, protocol
            )
            return self._connections.get(reverse_key)

    def get_all_connections(self) -> list[ConnectionInfo]:
        """Get all current connections."""
        with self._lock:
            return list(self._connections.values())

    def for_each_connection(self, callback: Callable[[ConnectionInfo], None]) -> None:
        """Call a function for each connection."""
        with self._lock:
            for conn in self._connections.values():
                callback(conn)
