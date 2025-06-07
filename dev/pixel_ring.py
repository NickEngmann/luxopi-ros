import usb.core
import usb.util


class PixelRing:
    TIMEOUT = 8000

    def __init__(self, dev):
        self.dev = dev

    def trace(self):
        self.write(0)

    def mono(self, color):
        self.write(1, [(color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF, 0])
    
    def set_color(self, rgb=None, r=0, g=0, b=0):
        if rgb:
            self.mono(rgb)
        else:
            self.write(1, [r, g, b, 0])

    def off(self):
        self.mono(0)

    def listen(self, direction=None):
        self.write(2)

    wakeup = listen

    def speak(self):
        self.write(3)

    def think(self):
        self.write(4)
    
    wait = think

    def spin(self):
        self.write(5)

    def show(self, data):
        self.write(6, data)

    customize = show
        
    def set_brightness(self, brightness):
        self.write(0x20, [brightness])
    
    def set_color_palette(self, a, b):
        self.write(0x21, [(a >> 16) & 0xFF, (a >> 8) & 0xFF, a & 0xFF, 0, (b >> 16) & 0xFF, (b >> 8) & 0xFF, b & 0xFF, 0])

    def set_vad_led(self, state):
        self.write(0x22, [state])

    def set_volume(self, volume):
        self.write(0x23, [volume])

    def arc(self, level):
        """
        Show an arc of LEDs to represent signal strength
        level: 1-12 representing how many LEDs to light up
        """
        # Create a simple arc pattern using the show method
        # Assuming 12 LEDs in a circle, light up 'level' number of them
        if level <= 0:
            self.off()
            return
        
        # Create data for 12 LEDs (4 bytes per LED: R, G, B, W)
        data = []
        for i in range(12):
            if i < level:
                # Green color for active LEDs
                data.extend([0, 255, 0, 0])  # R, G, B, W
            else:
                # Off for inactive LEDs
                data.extend([0, 0, 0, 0])
        
        self.show(data)

    def set_direction(self, angle, channels=4):
        """
        Show direction by lighting up LEDs pointing in that direction
        angle: 0-359 degrees
        channels: Number of audio channels (affects calibration offset)
        """
        # Convert angle to LED position (assuming 12 LEDs around circle)
        # Apply dynamic offset based on channel configuration
        if channels == 6:
            offset = 120  # 120° offset for 6-channel configuration
        else:
            offset = 60   # 60° offset for 4-channel configuration (default)
        
        adjusted_angle = (angle + offset) % 360
        led_position = int((adjusted_angle + 15) / 30) % 12  # 30° per LED with rounding
        
        # Create data for 12 LEDs
        data = []
        for i in range(12):
            if i == led_position:
                # Bright blue for direction
                data.extend([0, 0, 255, 0])  # R, G, B, W
            elif abs(i - led_position) <= 1 or abs(i - led_position) >= 11:
                # Dimmer blue for adjacent LEDs (wrap around)
                data.extend([0, 0, 128, 0])  # R, G, B, W
            else:
                # Off for other LEDs
                data.extend([0, 0, 0, 0])
        
        self.show(data)

    def change_pattern(self, pattern=None):
        print('Not support to change pattern')

    def write(self, cmd, data=[0]):
        self.dev.ctrl_transfer(
            usb.util.CTRL_OUT | usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_DEVICE,
            0, cmd, 0x1C, data, self.TIMEOUT)

    def close(self):
        """
        close the interface
        """
        usb.util.dispose_resources(self.dev)


def find(vid=0x2886, pid=0x0018):
    dev = usb.core.find(idVendor=vid, idProduct=pid)
    if not dev:
        return None

    # configuration = dev.get_active_configuration()

    # interface_number = None
    # for interface in configuration:
    #     interface_number = interface.bInterfaceNumber

    #     if dev.is_kernel_driver_active(interface_number):
    #         dev.detach_kernel_driver(interface_number)

    return PixelRing(dev)


# Create a module-level instance for easy importing
pixel_ring = find()

if __name__ == '__main__':
    import time

    if not pixel_ring:
        print("PixelRing device not found")
        exit(1)

    while True:
        try:
            print("Demo: Wakeup")
            pixel_ring.wakeup(180)
            time.sleep(2)
            
            print("Demo: Listen")
            pixel_ring.listen()
            time.sleep(2)
            
            print("Demo: Think")
            pixel_ring.think()
            time.sleep(2)
            
            print("Demo: Arc levels 1-12")
            for level in range(1, 13):
                pixel_ring.arc(level)
                time.sleep(0.3)
            time.sleep(1)
            
            print("Demo: Direction sweep (0-360°)")
            for angle in range(0, 360, 30):
                pixel_ring.set_direction(angle)
                time.sleep(0.5)
            time.sleep(1)
            
            print("Demo: Volume")
            pixel_ring.set_volume(8)
            time.sleep(2)
            
            print("Demo: Off")
            pixel_ring.off()
            time.sleep(3)
        except KeyboardInterrupt:
            break

    pixel_ring.off()
