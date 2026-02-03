# xnettop

Cross-platform network traffic monitor by process. Inspired by [nettop](https://github.com/Emanem/nettop).

## Features

- Real-time network traffic monitoring per process
- Supported platforms: Linux and macOS
- Interactive TUI with sorting and filtering
- Shows upload/download rates and totals

> **Note:** Windows is not supported. The tool requires raw packet capture capabilities that are not available on Windows without additional drivers.

## Requirements

- Python 3.11+
- Root/sudo privileges (required for packet capture)
- On Linux: libpcap-dev

## Installation

Install directly from GitHub:

```bash
uv tool install git+https://github.com/trailofbits/xnettop
sudo xnettop
```

Or clone and install locally:

```bash
git clone https://github.com/trailofbits/xnettop
cd xnettop
uv sync
sudo uv run xnettop
```

For development:

```bash
uv sync --dev
```

### Options

- `-i, --interface`: Network interface to capture (default: all)
- `-r, --refresh`: UI refresh rate in seconds (default: 1.0)
- `-c, --connection-refresh`: Connection table refresh rate (default: 1.0)

### Keyboard Shortcuts

- `q`: Quit
- `d`: Sort by download rate
- `u`: Sort by upload rate
- `t`: Sort by total rate
- `n`: Sort by process name
- `c`: Clear accumulated stats

## Docker (Linux testing)

```bash
docker build -t xnettop .
docker run --rm -it --cap-add=NET_RAW --cap-add=NET_ADMIN --net=host xnettop
```

## License

Apache-2.0
