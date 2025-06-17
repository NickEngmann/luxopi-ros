# Header for timestamp
std_msgs/Header header

# Idle request details
string request_type          # animation, head_variation, home_position
string animation_name        # Animation name (if applicable)
float32 speed_multiplier     # Speed multiplier
bool allow_interruption     # Whether request can be interrupted