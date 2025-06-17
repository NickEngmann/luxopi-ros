# Header for timestamp
std_msgs/Header header

# Petting status
string status                # inactive, active, animation_playing, timeout, error
bool active                  # Whether petting is currently active
int32 intensity              # Petting intensity (0-100)
bool animation_active        # Whether petting animation is active
string current_animation     # Current animation name
string state                 # State machine state