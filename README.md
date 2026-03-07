# LuxoPi ROS2 Project

![Tests](https://github.com/NickEngmann/luxopi-ros/actions/workflows/test.yml/badge.svg)

A ROS2-based control system for the RoArm-M3 robotic arm with Luxo Jr-style animated behaviors, vision processing, and collision avoidance.

## Overview

LuxoPi provides:
- ROS2 node integration for robotic arm control
- Depth camera vision processing using depthai SDK
- CustomTkinter GUI for visualization and control
- Serial communication for hardware interfacing
- Pure logic tests for non-hardware components

## Installation

### Prerequisites
- Python 3.11 or 3.12
- ROS2 Jazzy distribution
- depthai SDK

### Setup

1. Clone the repository:
```bash
git clone https://github.com/NickEngmann/luxopi-ros.git
cd luxopi-ros
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up serial permissions (if needed for hardware):
```bash
sudo usermod -aG dialout $USER
```

4. Source ROS2 environment:
```bash
source /opt/ros/jazzy/setup.bash
```

## Usage

### Running Tests

Run unit tests (no hardware required):
```bash
pytest -v
```

Run all tests including integration:
```bash
pytest -v --integration
```

### Hardware Interface

The project interfaces with RoArm-M3 robotic arm via serial communication. Serial commands are built using JSON format with hand offset calculations.

### Vision Processing

Depth camera input is processed using the depthai SDK. Configure camera parameters in the vision module.

### GUI

Launch the customtkinter-based GUI for visualization and manual control:
```bash
python src/gui/main.py
```

## Project Structure

```
luxopi-ros/
├── src/
│   ├── luxo_interfaces/    # ROS2 interface definitions
│   ├── roarm_ws_em1/       # ROS2 workspace for arm control
│   └── gui/                # CustomTkinter GUI application
├── tests/
│   ├── test_logic.py       # Pure logic tests (no ROS2/hardware)
│   └── conftest.py         # Test configuration and fixtures
├── requirements.txt        # Python dependencies
└── README.md
```

## Testing

### Test Categories

- **Pure logic tests** (`tests/test_logic.py`): Run without ROS2/hardware dependencies
- **Integration tests**: Require full ROS2 environment and hardware

### Running Tests

```bash
# Unit tests only
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src
```

### Test Fixtures

See `tests/conftest.py` for test configuration and fixtures.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests before submitting
4. Submit a pull request

## Known Issues

- Integration tests require full ROS2 environment not available in CI
- Serial port permissions need manual setup for hardware testing
- Vision processing requires depthai camera hardware

## License

MIT License
