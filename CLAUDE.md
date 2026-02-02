# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies
uv sync --dev

# Run the application (requires root)
sudo uv run xnettop

# Lint and format
uv run ruff check --fix
uv run ruff format

# Run tests
pytest -q

# Docker build for Linux testing
docker build -t xnettop .
docker run --rm -it --cap-add=NET_RAW --cap-add=NET_ADMIN --net=host xnettop
```

## Architecture

xnettop is a real-time per-process network traffic monitor with a 4-layer pipeline:

1. **Sniffer** (`sniffer.py`) - Captures TCP/UDP packets via scapy AsyncSniffer, pushes to thread-safe queue
2. **ConnectionMonitor** (`connections.py`) - Maps network connections to PIDs via psutil, refreshes in background thread
3. **TrafficAggregator** (`aggregator.py`) - Correlates packets with connections, calculates per-process rates using sliding window
4. **UI** (`ui.py`) - Textual TUI displaying sortable process traffic table

Data flows: packets → queue → aggregator correlates with connection table → UI polls aggregator stats

## Key Constraints

- **Root required**: Packet capture via scapy requires root/sudo privileges
- **Thread safety**: Sniffer, ConnectionMonitor, and Aggregator run background threads with lock-protected state
- **Platform differences**: Test on both macOS and Linux; Linux requires libpcap-dev
