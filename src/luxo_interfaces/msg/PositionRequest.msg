# Header for timestamp
std_msgs/Header header

# Request details
string request_type            # collision_adjustment, voice_following, home_position, etc.
float32[] positions           # Target joint positions
float32 speed                 # Movement speed
string description            # Human-readable description
int32 priority                # Request priority (1-10)
bool allow_interruption       # Whether this can be interrupted
float32 timeout               # Request timeout in seconds