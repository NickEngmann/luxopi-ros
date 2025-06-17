# Header for timestamp
std_msgs/Header header

# Front collision status
bool front_active
float32 front_distance
string front_severity
int32 front_consecutive_count

# Left collision status  
bool left_active
float32 left_distance
string left_severity
int32 left_consecutive_count

# Right collision status
bool right_active
float32 right_distance
string right_severity
int32 right_consecutive_count

# Overall status
bool any_collision_active
bool escape_mode_active
bool persistent_head_collision