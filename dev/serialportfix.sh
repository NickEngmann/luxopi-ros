#!/bin/bash

# Serial Port Configuration Script for Raspberry Pi
# This script will:
# 1. Create a udev rule for persistent permissions on /dev/ttyAMA10
# 2. Add current user to the dialout group
# 3. Disable serial console in cmdline.txt if enabled

# Function to check if script is running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "This script must be run as root. Please use sudo."
        exit 1
    fi
}

# Function to create udev rule
create_udev_rule() {
    echo "Creating udev rule for /dev/ttyAMA10..."
    
    # Create the udev rule file
    cat > /etc/udev/rules.d/99-serial.rules << EOF
# Set persistent permissions for Raspberry Pi serial port
KERNEL=="ttyAMA10", SUBSYSTEM=="tty", GROUP="dialout", MODE="0666"
EOF
    
    echo "Udev rule created successfully."
    
    # Reload udev rules
    echo "Reloading udev rules..."
    udevadm control --reload-rules && udevadm trigger
    echo "Udev rules reloaded."
}

# Function to add user to dialout group
add_user_to_dialout() {
    # Get the actual username (even when run with sudo)
    if [ -n "$SUDO_USER" ]; then
        REAL_USER="$SUDO_USER"
    else
        REAL_USER="$(whoami)"
    fi
    
    echo "Adding user '$REAL_USER' to dialout group..."
    usermod -a -G dialout "$REAL_USER"
    echo "User added to dialout group. This will take effect after logging out and back in."
}

# Function to check and disable serial console
check_serial_console() {
    echo "Checking for serial console in cmdline.txt..."
    
    # First check if the file exists in traditional location
    CMDLINE_PATH="/boot/cmdline.txt"
    if [ ! -f "$CMDLINE_PATH" ]; then
        # Try Ubuntu-specific location
        CMDLINE_PATH="/boot/firmware/cmdline.txt"
        if [ ! -f "$CMDLINE_PATH" ]; then
            echo "cmdline.txt not found in /boot or /boot/firmware. Skipping this step."
            return
        fi
    fi
    
    # Check if serial console is enabled
    if grep -q "console=serial0" "$CMDLINE_PATH" || grep -q "console=ttyAMA10" "$CMDLINE_PATH"; then
        echo "Serial console appears to be enabled in $CMDLINE_PATH"
        echo "Current cmdline.txt content:"
        cat "$CMDLINE_PATH"
        
        # Backup the file
        cp "$CMDLINE_PATH" "${CMDLINE_PATH}.backup"
        echo "Backup created at ${CMDLINE_PATH}.backup"
        
        # Remove serial console references
        NEW_CONTENT=$(cat "$CMDLINE_PATH" | sed 's/console=serial0,[0-9]\+ //g' | sed 's/console=ttyAMA10,[0-9]\+ //g')
        
        echo "Writing new cmdline.txt without serial console reference:"
        echo "$NEW_CONTENT"
        echo "$NEW_CONTENT" > "$CMDLINE_PATH"
        
        echo "Serial console disabled. A reboot is required for this change to take effect."
    else
        echo "Serial console does not appear to be enabled in cmdline.txt. No changes needed."
    fi
}

# Main execution
echo "=== Raspberry Pi Serial Port Configuration Tool ==="
echo "This script will configure your Raspberry Pi for reliable serial communication."

check_root
create_udev_rule
add_user_to_dialout
check_serial_console

echo ""
echo "=== Configuration Complete ==="
echo "For all changes to take effect, please REBOOT your Raspberry Pi."
echo "If you're still experiencing issues after rebooting, try the following:"
echo "1. Check if the serial interface is enabled in raspi-config"
echo "2. Verify that no other service is using the serial port"
echo "3. Check physical connections and hardware"
echo ""
