# Header for timestamp
std_msgs/Header header

# Override details
string override_type         # emergency_stop, safety_limits, position_override
bool active                  # Whether override is active
string source               # Source of the override
string reason               # Reason for override
int32 priority              # Override priority
float32[] target_position   # Target position (if applicable)
float32 timeout             # Override timeout
bool allow_interruption     # Whether override can be interrupted