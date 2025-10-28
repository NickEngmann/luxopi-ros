ros2 topic echo /touch_sensors/antenna/released

./start_luxopi.sh 2>&1 | grep -E "(Error in antenna|AttributeError)"