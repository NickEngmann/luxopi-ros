# Header for timestamp
std_msgs/Header header

# Action details
string action_type              # collision_avoidance, escape_maneuver, emergency_home
string direction               # front, left, right, multiple
float32 distance               # Distance to obstacle
string severity                # safe, warning, danger
float32[] target_position      # Target joint positions
float32 acceleration           # Acceleration to use
int32 priority                 # Action priority (1-10)