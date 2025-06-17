# Header for timestamp
std_msgs/Header header

# Activity details
string node_name              # Name of the reporting node
string activity_type          # Type of activity
float32 time_since_activity   # Time since last activity
float32 idle_timeout          # Current idle timeout
bool is_idle                  # Whether system is considered idle