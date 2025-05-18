#!/bin/bash

# Serial Port Configuration and Diagnostic Script for Raspberry Pi 5 running Ubuntu
echo "=== Raspberry Pi 5 Serial Port Diagnostic Tool ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root. Please use sudo."
    exit 1
fi

# Step 1: Identify all available serial ports
echo -e "\n=== Available Serial Ports ==="
ls -l /dev/ttyAMA* /dev/ttyS* /dev/serial* 2>/dev/null
echo "Note: On Pi 5 with Ubuntu, the main UART might appear as ttyAMA0, ttyS0, or other names."

# Step 2: Check config.txt for UART settings
echo -e "\n=== UART Configuration in config.txt ==="
CONFIG_PATH="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_PATH" ]; then
    CONFIG_PATH="/boot/config.txt"
fi

if [ -f "$CONFIG_PATH" ]; then
    grep -E "uart|serial" "$CONFIG_PATH"
    
    # Check if UART is enabled and enable if not
    if ! grep -q "enable_uart=1" "$CONFIG_PATH"; then
        echo "UART not explicitly enabled. Adding enable_uart=1 to $CONFIG_PATH"
        echo "enable_uart=1" >> "$CONFIG_PATH"
        echo "Added enable_uart=1 to $CONFIG_PATH"
    else
        echo "UART is enabled in $CONFIG_PATH"
    fi
else
    echo "Config file not found at expected locations"
fi

# Step 3: Check cmdline.txt for serial console
echo -e "\n=== Serial Console in cmdline.txt ==="
CMDLINE_PATH="/boot/firmware/cmdline.txt"
if [ ! -f "$CMDLINE_PATH" ]; then
    CMDLINE_PATH="/boot/cmdline.txt"
fi

if [ -f "$CMDLINE_PATH" ]; then
    echo "Current cmdline.txt content:"
    cat "$CMDLINE_PATH"
    
    # Check if serial console is enabled
    if grep -q "console=ttyAMA" "$CMDLINE_PATH" || grep -q "console=serial" "$CMDLINE_PATH" || grep -q "console=ttyS" "$CMDLINE_PATH"; then
        echo "Serial console appears to be enabled, which might interfere with hardware serial usage"
        echo "Backing up cmdline.txt to ${CMDLINE_PATH}.backup"
        cp "$CMDLINE_PATH" "${CMDLINE_PATH}.backup"
        
        # Remove serial console references
        NEW_CONTENT=$(cat "$CMDLINE_PATH" | sed -E 's/console=(serial|ttyAMA|ttyS)[0-9]+,[0-9]+ //g')
        
        echo "New cmdline.txt content without serial console:"
        echo "$NEW_CONTENT"
        echo "$NEW_CONTENT" > "$CMDLINE_PATH"
        echo "Serial console disabled. A reboot will be required."
    else
        echo "No serial console found in cmdline.txt. This is good for hardware serial usage."
    fi
else
    echo "cmdline.txt not found at expected locations"
fi

# Step 4: Check user groups
echo -e "\n=== User Group Configuration ==="
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER="$(whoami)"
fi

echo "Checking if user '$REAL_USER' is in the dialout group:"
if groups "$REAL_USER" | grep -q "dialout"; then
    echo "User is already in the dialout group"
else
    echo "Adding user to dialout group"
    usermod -a -G dialout "$REAL_USER"
    echo "User added to dialout group. This will take effect after logging out and back in."
fi

# Step 5: Create/update udev rules for all possible serial ports
echo -e "\n=== Setting up udev rules ==="
cat > /etc/udev/rules.d/99-serial.rules << EOF
# Set persistent permissions for Raspberry Pi serial ports
KERNEL=="ttyAMA[0-9]*", SUBSYSTEM=="tty", GROUP="dialout", MODE="0666"
KERNEL=="ttyS[0-9]*", SUBSYSTEM=="tty", GROUP="dialout", MODE="0666"
EOF

echo "Udev rules created for all serial ports"
echo "Reloading udev rules..."
udevadm control --reload-rules && udevadm trigger
echo "Udev rules reloaded"

# Step 6: Check for processes using serial ports
echo -e "\n=== Checking for Processes Using Serial Ports ==="
echo "Processes using ttyAMA ports:"
lsof | grep ttyAMA || echo "None found"
echo "Processes using ttyS ports:"
lsof | grep ttyS || echo "None found"

# Step 7: Prevent serial-getty service from using the port
echo -e "\n=== Checking for serial-getty services ==="
for port in ttyAMA0 ttyAMA10 ttyS0 ttyS1; do
    service="serial-getty@$port.service"
    if systemctl is-enabled $service &>/dev/null; then
        echo "Disabling $service"
        systemctl disable $service
        systemctl stop $service
        echo "$service disabled and stopped"
    else
        echo "$service is not enabled"
    fi
done

echo -e "\n=== Configuration Complete ==="
echo "For all changes to take effect, please REBOOT your Raspberry Pi 5."
echo -e "\nAfter rebooting, you can test the serial port with:"
echo "1. For basic testing: 'cat /dev/ttyAMA0' or 'cat /dev/ttyAMA10' (depending on your actual port)"
echo "2. Or using a serial tool: 'sudo apt install minicom && sudo minicom -D /dev/ttyAMA10 -b 115200'"
echo -e "\nIf issues persist after reboot, run 'dmesg | grep tty' to see kernel messages about serial ports"