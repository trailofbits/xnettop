"""Shared test fixtures for xnettop tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from xnettop.aggregator import ProcessStats, TrafficAggregator
from xnettop.connections import ConnectionInfo, ConnectionMonitor
from xnettop.sniffer import PacketInfo, PacketSniffer


@pytest.fixture
def mock_psutil_connections():
    """Mock psutil.net_connections to return test data."""
    mock_conn = MagicMock()
    mock_conn.pid = 1234
    mock_conn.laddr = ("127.0.0.1", 8080)
    mock_conn.raddr = ("192.168.1.1", 443)
    mock_conn.type.name = "SOCK_STREAM"
    mock_conn.status = "ESTABLISHED"

    with patch("psutil.net_connections", return_value=[mock_conn]):
        yield [mock_conn]


@pytest.fixture
def mock_psutil_process():
    """Mock psutil.Process to return test data."""
    mock_proc = MagicMock()
    mock_proc.name.return_value = "test_process"
    mock_proc.cmdline.return_value = ["test_process", "--arg"]

    with patch("psutil.Process", return_value=mock_proc):
        yield mock_proc


@pytest.fixture
def mock_psutil_net_if_addrs():
    """Mock psutil.net_if_addrs to return test data."""
    mock_addr = MagicMock()
    mock_addr.family.name = "AF_INET"
    mock_addr.address = "192.168.1.100"

    with patch("psutil.net_if_addrs", return_value={"eth0": [mock_addr]}):
        yield {"eth0": [mock_addr]}


@pytest.fixture
def connection_monitor(mock_psutil_net_if_addrs):
    """Create a ConnectionMonitor instance for testing."""
    monitor = ConnectionMonitor(refresh_interval=0.1)
    yield monitor
    monitor.stop()


@pytest.fixture
def packet_sniffer():
    """Create a PacketSniffer instance for testing (without starting capture)."""
    sniffer = PacketSniffer(interface=None)
    yield sniffer
    sniffer.stop()


@pytest.fixture
def traffic_aggregator(connection_monitor, packet_sniffer):
    """Create a TrafficAggregator instance for testing."""
    aggregator = TrafficAggregator(
        connection_monitor=connection_monitor,
        packet_sniffer=packet_sniffer,
        update_interval=0.1,
    )
    yield aggregator
    aggregator.stop()


@pytest.fixture
def sample_packet_info():
    """Create sample PacketInfo for testing."""
    return PacketInfo(
        src_ip="192.168.1.100",
        dst_ip="8.8.8.8",
        src_port=12345,
        dst_port=443,
        protocol="tcp",
        size=1500,
        is_ipv6=False,
    )


@pytest.fixture
def sample_connection_info():
    """Create sample ConnectionInfo for testing."""
    return ConnectionInfo(
        pid=1234,
        process_name="test_process",
        local_addr=("192.168.1.100", 12345),
        remote_addr=("8.8.8.8", 443),
        protocol="tcp",
        status="ESTABLISHED",
    )


@pytest.fixture
def sample_process_stats():
    """Create sample ProcessStats for testing."""
    return ProcessStats(
        pid=1234,
        name="test_process",
        upload_bytes=1000,
        download_bytes=2000,
        upload_rate=100.0,
        download_rate=200.0,
    )
