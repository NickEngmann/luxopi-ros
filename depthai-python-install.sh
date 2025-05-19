#!/bin/bash
# Complete Installation of depthai-python

set -e  # Exit on error

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
