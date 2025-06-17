# Header for timestamp
std_msgs/Header header

# Voice following details
float32 target_angle_deg      # Target angle in degrees
float32 influence             # Voice influence factor (0.0-1.0)
bool has_variation           # Whether variation is applied
float32[] positions          # Target joint positions
bool active                  # Whether voice following is active
string direction             # Direction description