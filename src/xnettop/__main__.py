"""CLI entry point for xnettop."""

from __future__ import annotations

import argparse
import os
import signal
import sys
from types import FrameType

from xnettop import __version__
from xnettop.aggregator import TrafficAggregator
from xnettop.connections import ConnectionMonitor
from xnettop.sniffer import PacketSniffer
from xnettop.ui import XnettopApp


def check_root() -> None:
    """Check if running with root privileges."""
    if os.geteuid() != 0:
        print("Error: xnettop requires root privileges for packet capture.", file=sys.stderr)
        print("Please run with: sudo xnettop", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="xnettop",
        description="Cross-platform network traffic monitor by process",
    )
    parser.add_argument(
        "-i",
        "--interface",
        help="Network interface to capture on (default: all)",
        default=None,
    )
    parser.add_argument(
        "-r",
        "--refresh",
        type=float,
        default=1.0,
        help="UI refresh rate in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-c",
        "--connection-refresh",
        type=float,
        default=1.0,
        help="Connection table refresh rate in seconds (default: 1.0)",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"xnettop {__version__}",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()
    check_root()
    connection_monitor = ConnectionMonitor(refresh_interval=args.connection_refresh)
    packet_sniffer = PacketSniffer(interface=args.interface)
    aggregator = TrafficAggregator(
        connection_monitor=connection_monitor,
        packet_sniffer=packet_sniffer,
    )

    def shutdown_handler(signum: int, frame: FrameType | None) -> None:
        aggregator.stop()
        packet_sniffer.stop()
        connection_monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    try:
        connection_monitor.start()
        packet_sniffer.start()
        aggregator.start()
        app = XnettopApp(aggregator=aggregator, refresh_rate=args.refresh)
        app.run()
    finally:
        aggregator.stop()
        packet_sniffer.stop()
        connection_monitor.stop()


if __name__ == "__main__":
    main()
