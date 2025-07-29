#!/usr/bin/env python3
"""
System Monitor Node for Lux Robot
Publishes CPU, RAM, and temperature metrics for the Raspberry Pi 5
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
import psutil
import os
import time

class SystemMonitor(Node):
    def __init__(self):
        super().__init__('system_monitor')
        
        # Declare parameters
        self.declare_parameter('publish_rate', 2.0)  # Hz
        self.declare_parameter('temperature_source', '/sys/class/thermal/thermal_zone0/temp')  # RPi CPU temp
        self.declare_parameter('cpu_average_window', 5.0)  # seconds
        
        # Get parameters
        self.publish_rate = self.get_parameter('publish_rate').value
        self.temp_source = self.get_parameter('temperature_source').value
        self.cpu_window = self.get_parameter('cpu_average_window').value
        
        # Create publishers
        self.cpu_pub = self.create_publisher(Float32, '/system/cpu_usage', 10)
        self.ram_pub = self.create_publisher(Float32, '/system/ram_usage', 10)
        self.temp_pub = self.create_publisher(Float32, '/system/temperature', 10)
        
        # CPU tracking for smoothed readings
        self.cpu_readings = []
        self.max_cpu_readings = int(self.cpu_window * self.publish_rate)
        
        # Create timer for periodic publishing
        self.timer = self.create_timer(1.0 / self.publish_rate, self.publish_metrics)
        
        # Initialize CPU monitoring (first reading is often inaccurate)
        psutil.cpu_percent(interval=None)
        
        self.get_logger().info(f'System Monitor started - publishing at {self.publish_rate}Hz')
        self.get_logger().info(f'Temperature source: {self.temp_source}')
        self.get_logger().info(f'CPU averaging window: {self.cpu_window}s')
    
    def get_cpu_usage(self):
        """Get CPU usage percentage with smoothing"""
        try:
            # Get current CPU usage (non-blocking)
            current_cpu = psutil.cpu_percent(interval=None)
            
            # Add to rolling window
            self.cpu_readings.append(current_cpu)
            if len(self.cpu_readings) > self.max_cpu_readings:
                self.cpu_readings.pop(0)
            
            # Return smoothed average
            if self.cpu_readings:
                return sum(self.cpu_readings) / len(self.cpu_readings)
            else:
                return current_cpu
                
        except Exception as e:
            self.get_logger().error(f"Error reading CPU usage: {e}")
            return 0.0
    
    def get_ram_usage(self):
        """Get RAM usage percentage"""
        try:
            memory = psutil.virtual_memory()
            return memory.percent
        except Exception as e:
            self.get_logger().error(f"Error reading RAM usage: {e}")
            return 0.0
    
    def get_temperature(self):
        """Get CPU temperature in Celsius"""
        try:
            # Try Raspberry Pi thermal zone first
            if os.path.exists(self.temp_source):
                with open(self.temp_source, 'r') as f:
                    temp_raw = f.read().strip()
                    # RPi thermal zone reports in millidegrees
                    temp_celsius = float(temp_raw) / 1000.0
                    return temp_celsius
            
            # Fallback to psutil sensors (if available)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try common sensor names
                    for sensor_name in ['cpu_thermal', 'coretemp', 'k10temp']:
                        if sensor_name in temps:
                            return temps[sensor_name][0].current
                    
                    # If no known sensors, use first available
                    first_sensor = list(temps.values())[0]
                    if first_sensor:
                        return first_sensor[0].current
            except:
                pass
            
            # If all else fails, return a reasonable default
            self.get_logger().debug("Could not read temperature, using default")
            return 45.0
            
        except Exception as e:
            self.get_logger().error(f"Error reading temperature: {e}")
            return 45.0
    
    def publish_metrics(self):
        """Publish all system metrics"""
        try:
            # Get metrics
            cpu_usage = self.get_cpu_usage()
            ram_usage = self.get_ram_usage()
            temperature = self.get_temperature()
            
            # Create and publish messages
            cpu_msg = Float32()
            cpu_msg.data = cpu_usage
            self.cpu_pub.publish(cpu_msg)
            
            ram_msg = Float32()
            ram_msg.data = ram_usage
            self.ram_pub.publish(ram_msg)
            
            temp_msg = Float32()
            temp_msg.data = temperature
            self.temp_pub.publish(temp_msg)
            
            # Log periodically for debugging
            if hasattr(self, '_last_log_time'):
                if time.time() - self._last_log_time > 10.0:  # Log every 10 seconds
                    self.get_logger().info(
                        f"System metrics - CPU: {cpu_usage:.1f}%, "
                        f"RAM: {ram_usage:.1f}%, Temp: {temperature:.1f}°C"
                    )
                    self._last_log_time = time.time()
            else:
                self._last_log_time = time.time()
                
        except Exception as e:
            self.get_logger().error(f"Error publishing metrics: {e}")
    
    def destroy_node(self):
        """Clean shutdown"""
        self.get_logger().info("System Monitor shutting down")
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = SystemMonitor()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in System Monitor: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()