# Header for timestamp
std_msgs/Header header

# System state
string robot_state                    # Current robot state
bool emergency_stop_active           # Emergency stop status
bool safety_limits_enabled           # Safety limits status
bool system_healthy                  # Overall system health
string current_movement_source       # Current movement source

# Override information
int32 active_override_count          # Number of active overrides
string current_override_source       # Source of current override
int32 current_override_priority      # Priority of current override
string current_override_reason       # Reason for current override