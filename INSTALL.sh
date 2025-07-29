#!/bin/bash
# Complete ROS2 Jazzy Installation with X11 Forwarding Setup and Tailscale Support
# For Ubuntu 24.04 Server on Raspberry Pi
# This script installs ROS2 Jazzy, configures X11 forwarding, and optimizes for Tailscale remote access

set -e  # Exit on error

echo "====================================================================================="
echo "ROS2 Jazzy Installation with X11 Forwarding and Tailscale Support for Ubuntu 24.04"
echo "====================================================================================="

# 1. Set locale
echo "Setting up locale..."
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Verify locale settings
locale

# 2. Add the ROS 2 apt repository
echo "Adding ROS2 apt repository..."
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository universe

# Add ROS2 GPG key
sudo apt update && sudo apt install -y curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

# Add the repository to sources list
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# 3. Install Tailscale (if not already installed)
echo "Installing Tailscale..."
if ! command -v tailscale &> /dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sudo bash
    echo "Tailscale installed. Remember to run 'sudo tailscale up' to connect to your Tailnet."
else
    echo "Tailscale is already installed."
fi

# 4. Install X11 server and required dependencies for GUI forwarding
echo "Installing X11 server and required dependencies..."
sudo apt update
sudo apt install -y \
  xauth \
  x11-apps \
  x11-utils \
  mesa-utils \
  libxcb-xinerama0 \
  openssh-server

# 5. Install development tools and ROS tools
echo "Installing development tools and ROS tools..."
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
  python3-flake8-docstrings \
  python3-pip \
  python3-pytest-cov \
  ros-dev-tools

# 6. Install additional Python packages for Ubuntu 24.04
echo "Installing additional Python packages..."
sudo apt install -y \
  python3-flake8-blind-except \
  python3-flake8-builtins \
  python3-flake8-class-newline \
  python3-flake8-comprehensions \
  python3-flake8-deprecated \
  python3-flake8-import-order \
  python3-flake8-quotes \
  python3-pytest-repeat \
  python3-pytest-rerunfailures \
  python3-tk \
  python3-pil.imagetk

# 7. Install ROS2 packages
echo "Installing ROS2 Jazzy packages..."
sudo apt update
sudo apt install -y ros-jazzy-desktop

# 8. Install additional GUI-specific packages for ROS2 visualization
echo "Installing ROS2 visualization packages..."
sudo apt install -y \
  ros-jazzy-rqt \
  ros-jazzy-rqt-common-plugins \
  ros-jazzy-rviz2 \
  ros-jazzy-xacro \
  ros-jazzy-joint-state-publisher-gui \
  ros-jazzy-depthai-ros \
  qtbase5-dev \
  qtchooser \
  qt5-qmake \
  qtbase5-dev-tools \
  libcanberra-gtk-module \
  libcanberra-gtk3-module

# 9. Install development tools
echo "Installing development tools..."
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-colcon-mixin \
  python3-rosdep \
  python3-vcstool

# 10. Initialize rosdep
echo "Initializing rosdep..."
sudo rosdep init || echo "rosdep already initialized"
rosdep update

# 11. Create workspace and get the code
echo "Creating workspace and downloading ROS2 code..."
mkdir -p ~/ros2_jazzy_ws/src
cd ~/ros2_jazzy_ws

# 12. Install dependencies using rosdep
echo "Installing dependencies with rosdep..."
sudo apt upgrade -y
rosdep update
rosdep install --from-paths src --ignore-src -y --skip-keys "fastcdr rti-connext-dds-6.0.1 urdfdom_headers"

# 13. Configure SSH for X11 forwarding with broader access
echo "Configuring SSH for X11 forwarding..."
if grep -q "^#X11Forwarding" /etc/ssh/sshd_config; then
  sudo sed -i 's/^#X11Forwarding.*/X11Forwarding yes/' /etc/ssh/sshd_config
elif grep -q "^X11Forwarding" /etc/ssh/sshd_config; then
  sudo sed -i 's/^X11Forwarding.*/X11Forwarding yes/' /etc/ssh/sshd_config
else
  echo "X11Forwarding yes" | sudo tee -a /etc/ssh/sshd_config
fi

if grep -q "^#X11UseLocalhost" /etc/ssh/sshd_config; then
  sudo sed -i 's/^#X11UseLocalhost.*/X11UseLocalhost no/' /etc/ssh/sshd_config
elif grep -q "^X11UseLocalhost" /etc/ssh/sshd_config; then
  sudo sed -i 's/^X11UseLocalhost.*/X11UseLocalhost no/' /etc/ssh/sshd_config
else
  echo "X11UseLocalhost no" | sudo tee -a /etc/ssh/sshd_config
fi

if grep -q "^#X11DisplayOffset" /etc/ssh/sshd_config; then
  sudo sed -i 's/^#X11DisplayOffset.*/X11DisplayOffset 10/' /etc/ssh/sshd_config
elif grep -q "^X11DisplayOffset" /etc/ssh/sshd_config; then
  sudo sed -i 's/^X11DisplayOffset.*/X11DisplayOffset 10/' /etc/ssh/sshd_config
else
  echo "X11DisplayOffset 10" | sudo tee -a /etc/ssh/sshd_config
fi


sudo apt install -y python3-pip python3-venv git

mkdir -p ~/github/luxonis
cd ~/github/luxonis
git clone https://github.com/luxonis/depthai.git
cd ~/github/luxonis/depthai
python3 -m venv virtualenv
source virtualenv/bin/activate
pip install -U pip
python3 install_requirements.py
sudo apt-get -y install libatlas-base-dev python3-h5py
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' \
    | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules \
    && sudo udevadm trigger
    
# Restart SSH service
#sudo systemctl restart sshd

# 14. Create a .xsessionrc file to set display properties
cat << EOF > ~/.xsessionrc
export DISPLAY=:0
export XAUTHORITY=~/.Xauthority
xhost +si:localuser:$(whoami)
EOF

chmod +x ~/.xsessionrc

# 15. Set up environment with network configuration for Tailscale
echo "Setting up environment with Tailscale network support..."
cat << EOF > ~/ros2_jazzy_ws/setup_ros2.bash
#!/bin/bash
# Source ROS2 Jazzy
source /opt/ros/jazzy/setup.bash

# Source the local workspace if it exists
if [ -f ~/ros2_jazzy_ws/install/local_setup.bash ]; then
  source ~/ros2_jazzy_ws/install/local_setup.bash
fi

# Get Tailscale IP address if available
if command -v tailscale &> /dev/null && tailscale status &> /dev/null; then
  TAILSCALE_IP=\$(tailscale ip -4)
  if [ ! -z "\$TAILSCALE_IP" ]; then
    # Set ROS_DOMAIN_ID to avoid crosstalk with other ROS2 systems
    # Change this to a unique number between 0-101 for your system
    export ROS_DOMAIN_ID=42
    
    # Set ROS network interfaces - use your Tailscale IP
    export ROS_IP=\$TAILSCALE_IP
    
    # Allow ROS2 discovery beyond localhost
    # Comment out the following line if you want to restrict to localhost
    # export ROS_LOCALHOST_ONLY=0
    
    echo "ROS2 configured with Tailscale IP: \$TAILSCALE_IP"
  fi
else
  # Fallback configuration if Tailscale is not running
  # Restricting to localhost for security
  export ROS_LOCALHOST_ONLY=1
  echo "Tailscale not detected, using localhost only mode"
fi

# ROS2 GUI configuration for X11 forwarding
export QT_X11_NO_MITSHM=1
export LIBGL_ALWAYS_SOFTWARE=1

# Force software rendering for OpenGL (uncomment if needed)
# export LIBGL_ALWAYS_INDIRECT=1

# Configure Cyclone DDS settings for better network performance
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><NetworkInterfaceAddress>auto</NetworkInterfaceAddress><AllowMulticast>true</AllowMulticast><EnableMulticastLoopback>true</EnableMulticastLoopback></General></Domain></CycloneDDS>'
EOF

chmod +x ~/ros2_jazzy_ws/setup_ros2.bash

# Add to .bashrc for convenience
if ! grep -q "source ~/ros2_jazzy_ws/setup_ros2.bash" ~/.bashrc; then
  echo "source ~/ros2_jazzy_ws/setup_ros2.bash" >> ~/.bashrc
fi

# 16. Create firewall configuration suitable for ROS2 and Tailscale
echo "Configuring firewall for ROS2 and Tailscale..."
sudo apt install -y ufw
sudo ufw allow ssh
sudo ufw allow in on tailscale0
sudo ufw allow 7400:7500/udp  # ROS2 DDS discovery
sudo ufw allow 7400:7500/tcp  # ROS2 DDS discovery
sudo ufw allow OpenSSH

# Adafruit Library Installation
sudo apt-get install -y i2c-tools libgpiod-dev python3-libgpiod python3-lgpio
pip3 install --upgrade adafruit-blinka --break-system-packages
cd ~
git clone https://github.com/NickEngmann/Adafruit_CircuitPython_APDS9960.git
cd Adafruit_CircuitPython_APDS9960
pip3 install -e . --break-system-packages
pip3 install adafruit-circuitpython-vcnl4200 --break-system-packages
pip3 install adafruit-circuitpython-vl53l4cd --break-system-packages
pip3 install adafruit-circuitpython-ads7830 --break-system-packages
pip3 install RPi.GPIO --break-system-packages

# Install DepthAI lsusb | grep 03e7Camera Code
sudo wget -qO- https://docs.luxonis.com/install_depthai.sh | bash

# Install Respeaker v2.0 requirements
sudo apt-get update
sudo apt install alsa-utils -y
sudo apt install portaudio19-dev -y
sudo pip install pyusb click pyaudio webrtcvad --break-system-packages
cd ~/luxopi-ros/dev/
git clone https://github.com/respeaker/usb_4_mic_array.git
cd usb_4_mic_array
git clone https://github.com/respeaker/mic_array.git
echo 'SUBSYSTEM=="usb", MODE="0666"' | sudo tee -a /etc/udev/rules.d/60-usb.rules
sudo udevadm control -R  # then re-plug the usb device

# Install FBI and give it the correct permissions
sudo apt install fbi -y
sudo usermod -a -G video,tty $USER
newgrp video
newgrp tty
groups
sudo chmod 666 /dev/tty1
sudo chown $USER:$USER /dev/tty1
sudo chmod 660 /dev/tty1
sudo chgrp tty /dev/tty1
sudo chmod 660 /dev/tty1

# Install symbolic link
sudo ln -s /home/pi/luxopi-ros/start_luxopi.sh /usr/local/bin/start_luxopi
chmod +x /home/pi/luxopi-ros/start_luxopi.sh


# Don't enable the firewall automatically - let the user do it
echo "Firewall configured but not enabled. To enable, run: sudo ufw enable"

echo "====================================================================================="
echo "ROS2 Jazzy installation with X11 forwarding and Tailscale support complete!"
echo "====================================================================================="
echo ""
echo "To connect your Raspberry Pi to Tailscale:"
echo "    sudo tailscale up"
echo ""
echo "To test ROS2:"
echo "1. In one terminal: source ~/ros2_jazzy_ws/setup_ros2.bash && ros2 run demo_nodes_cpp talker"
echo "2. In another terminal: source ~/ros2_jazzy_ws/setup_ros2.bash && ros2 run demo_nodes_py listener"
echo ""
echo "To test X11 forwarding over Tailscale:"
echo "1. From your client machine, connect with: ssh -X username@TAILSCALE_IP"
echo "2. Run a test X application: xclock"
echo "3. Try a ROS2 GUI tool: rviz2 or rqt"
echo ""
echo "For cross-machine ROS2 communication:"
echo "1. Use the same ROS_DOMAIN_ID on all machines (default is 42 in this script)"
echo "2. Make sure all machines are on the same Tailscale network"
echo "3. If using a firewall, ensure ports 7400-7500 TCP/UDP are open"
echo ""
echo "Note: If using Windows, install an X server like VcXsrv, Xming, or MobaXterm."
echo "If using macOS, install XQuartz."
echo ""
echo "Please restart your terminal or run 'source ~/.bashrc' to use ROS2."
