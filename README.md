# xnettop

Cross-platform network traffic monitor by process. Inspired by [nettop](https://github.com/Emanem/nettop).

## Features

- Real-time network traffic monitoring per process
- Cross-platform: Linux and macOS (Windows experimental)
- Interactive TUI with sorting and filtering
- Shows upload/download rates and totals

## Requirements

- Python 3.11+
- Root/sudo privileges (required for packet capture)
- On Linux: libpcap-dev

## Installation

```bash
pip install .
```

## Usage

```bash
sudo xnettop
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
