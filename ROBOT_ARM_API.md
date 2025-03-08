# Robot Arm API Documentation

## Basic Commands

### Reset

#### CMD_MOVE_INIT - Move to the Initial Position
```json
{"T":100}
```
- **100**: Indicates this command is CMD_MOVE_INIT, which rotates all joints to their initial positions
- Under normal circumstances, the robotic arm automatically moves to its initial position when powered on
- This command will cause the process to block

## Joint Angle Control

### CMD_SINGLE_JOINT_CTRL - Single Joint Control (in radians)
```json
{"T":101,"joint":0,"rad":0,"spd":0,"acc":10}
```
- **101**: Indicates this command is CMD_SINGLE_JOINT_CTRL
- **joint**: Joint numbers
  - 1: BASE_JOINT
  - 2: SHOULDER_JOINT
  - 3: ELBOW_JOINT
  - 4: EOAT_JOINT
- **rad**: Rotation angle in radians
  - BASE_JOINT: Default 0, range 3.14 to -3.14. Increasing turns left, decreasing turns right
  - SHOULDER_JOINT: Default 0, range 1.57 to -1.57. Increasing rotates forward, decreasing rotates backward
  - ELBOW_JOINT: Default 1.570796, range 3.14 to -1.11. Increasing rotates downward, decreasing rotates upward
  - EOAT_JOINT: Default 3.141593. For clamp, range 1.08 to 3.14; decreasing opens clamp. For wrist joint, range 1.08 to 5.20; increasing rotates downward, decreasing rotates upward
- **spd**: Rotation speed in steps/second (one full rotation = 4096 steps); 0 = maximum speed
- **acc**: Acceleration (0-254, in 100 steps/second²); smaller values = smoother acceleration/deceleration; 0 = maximum acceleration

### CMD_JOINTS_RAD_CTRL - All Angle Control (in radians)
```json
{"T":102,"base":0,"shoulder":0,"elbow":1.57,"hand":3.14,"spd":0,"acc":10}
```
- **102**: Indicates this command controls rotation of all joints in radians
- **base**: Base joint angle in radians
- **shoulder**: Shoulder joint angle in radians
- **elbow**: Elbow joint angle in radians
- **hand**: Clamp/wrist joint angle in radians
- **spd**: Rotation speed (steps/second); 0 = maximum speed
- **acc**: Acceleration (0-254, in 100 steps/second²); 0 = maximum acceleration

### CMD_EOAT_HAND_CTRL - EoAT Control (in radians)
```json
{"T":106,"cmd":3.14,"spd":0,"acc":0}
```
- **106**: Indicates this command controls the clamp/wrist joint
- **cmd**: Rotation angle in radians (default initial angle is 3.141593)
  - Clamp: Range 1.08 to 3.14; decreasing opens the clamp
  - Wrist: Range 1.08 to 5.20; increasing rotates downward, decreasing rotates upward
- **spd**: Rotation speed; 0 = maximum speed
- **acc**: Acceleration (0-254, in 100 steps/second²); 0 = maximum acceleration

### CMD_SINGLE_JOINT_ANGLE - Single Joint Control (in degrees)
```json
{"T":121,"joint":1,"angle":0,"spd":10,"acc":10}
```
- **121**: Indicates this command controls joint rotation in degrees
- **joint**: Joint number (1=BASE, 2=SHOULDER, 3=ELBOW, 4=EOAT)
- **angle**: Rotation angle in degrees
  - BASE_JOINT: Default 0°, range 180° to -180°; increasing turns left, decreasing turns right
  - SHOULDER_JOINT: Default 0°, range 90° to -90°; increasing rotates forward, decreasing rotates backward
  - ELBOW_JOINT: Default 90°, range 180° to -45°; increasing rotates downward, decreasing rotates upward
  - EOAT_JOINT: Default 180°
    - Clamp: Range 45° to 180°; decreasing opens the clamp
    - Wrist: Range 45° to 315°; increasing rotates downward, decreasing rotates upward
- **spd**: Rotation speed in °/s; 0 = maximum speed
- **acc**: Acceleration in °/s²; 0 = maximum acceleration

### CMD_JOINTS_ANGLE_CTRL - All Joints Control (in degrees)
```json
{"T":122,"b":0,"s":0,"e":90,"h":180,"spd":10,"acc":10}
```
- **122**: Indicates this command controls all joints in degrees
- **b**: Base joint angle
- **s**: Shoulder joint angle
- **e**: Elbow joint angle
- **h**: Clamp/wrist joint angle
- **spd**: Rotation speed in °/s; 0 = maximum speed
- **acc**: Acceleration in °/s²; 0 = maximum acceleration

## 3D Cartesian Coordinate Control

The robot arm uses the right-hand rule coordinate system:
- X-axis: Positive directly in front of the robot arm
- Y-axis: Positive to the left from the front of the robot arm
- Z-axis: Positive directly above the robot arm

### CMD_SINGLE_AXIS_CRTL - Individual Axis Position Control (inverse kinematics)
```json
{"T":103,"axis":2,"pos":0,"spd":0.25}
```
- **103**: Indicates this command controls a single axis position
- **axis**: Axis number (1=X, 2=Y, 3=Z, 4=T [clamp/wrist angle in radians])
- **pos**: Position in mm
- **spd**: Movement speed (larger value = faster); includes curve speed control
- This command causes the process to block

### CMD_XYZT_GOAL_CTRL - EoAT Control (inverse kinematics)
```json
{"T":104,"x":235,"y":0,"z":234,"t":3.14,"spd":0.25}
```
- **104**: Indicates this command controls the EoAT position
- **x, y, z**: Position coordinates in mm
- **t**: Clamp/wrist angle in radians
- **spd**: Movement speed; includes curve speed control
- This command may cause the movement to be blocked

### CMD_XYZT_DIRECT_CTRL - EoAT Position Control (inverse kinematics)
```json
{"T":1041,"x":235,"y":0,"z":234,"t":3.14}
```
- **1041**: Indicates this command directly controls the EoAT position
- **x, y, z**: Position coordinates in mm
- **t**: Clamp/wrist angle in radians
- Note: This command doesn't block execution and has no interpolation calculation. The arm moves at maximum speed to the target. Suitable for continuous target updates with small position differences.

### CMD_SERVO_RAD_FEEDBACK - Get Feedback from Robotic Arm
```json
{"T":105}
```
- **105**: Requests feedback on coordinates, joint angles, and load
- Response example:
```json
{"T":1051,"x":309.04,"y":3.32,"z":238.24,"b":0.01,"s":-0.004,"e":1.57,"t":3.14,"torB":-56,"torS":-20,"torE":0,"torH":0}
```
- **x, y, z**: EoAT coordinates in mm
- **b, s, e, t**: Joint angles in radians (base, shoulder, elbow, EoAT)
- **torB, torS, torE, torH**: Load values for each joint

### CMD_CONSTANT_CTRL - Continuous Movement Control
```json
{"T":123,"m":0,"axis":0,"cmd":0,"spd":0}
```
- **123**: Indicates this command controls continuous movement
- **m**: Movement control mode (0=angle control, 1=coordinate control)
- **axis**: 
  - In angle control mode (m=0): 1=Base, 2=Shoulder, 3=Elbow, 4=Hand
  - In coordinate mode (m=1): 1=X, 2=Y, 3=Z, 4=Hand
- **cmd**: Movement status
  - 0: STOP movement
  - 1: INCREASE (angle or coordinate)
  - 2: DECREASE (angle or coordinate)
- **spd**: Speed coefficient (0-20 recommended); larger value = faster

## Torque Control

### CMD_TORQUE_CTRL - Torque Lock Control
```json
{"T":210,"cmd":0}
```
- **210**: Indicates this command controls torque lock
- **cmd**: Torque lock switch mode
  - 0: Turn off torque lock (allows manual movement)
  - 1: Turn on torque lock (prevents manual movement)
- Note: After turning off, torque lock automatically reactivates when any joint receives a rotation command

### CMD_DYNAMIC_ADAPTATION - Dynamic Force Self-Adaptation
```json
{"T":112,"mode":1,"b":60,"s":110,"e":50,"h":50}
```
or
```json
{"T":112,"mode":0,"b":1000,"s":1000,"e":1000,"h":1000}
```
- **112**: Indicates this command controls dynamic external force adaptation
- **mode**: 
  - 0: Function off (cannot manually move joints when powered on)
  - 1: Function on (arm returns to previous position after external movement)
- **b, s, e, h**: Maximum torque limits for Base, Shoulder, Elbow, and Hand joints
- When on, applied force exceeding limits moves the arm, which then rebounds
- Higher torque limits require more force but result in faster rebounds
- When off, default torque limit for all joints is 1000

## Delay Command

### CMD_DELAY_MILLIS - Add Delay
```json
{"T":111,"cmd":3000}
```
- **111**: Indicates this command adds a delay
- **cmd**: Delay duration in milliseconds

## EoAT Control

### CMD_EOAT_GRAB_TORQUE - Set Grab Torque
```json
{"T":107,"tor":200}
```
- **107**: Indicates this command sets the grab torque
- **tor**: Torque value

## Joints PID Control

### CMD_SET_JOINT_PID - Set Joint PID Parameters
```json
{"T":108,"joint":3,"p":16,"i":0}
```
- **108**: Indicates this command sets joint PID parameters
- **joint**: Joint number
- **p**: Proportional gain
- **i**: Integral gain

### CMD_RESET_PID - Reset PID Parameters
```json
{"T":109}
```
- **109**: Resets PID parameters to defaults

## X-Axis Configuration

### CMD_SET_NEW_X - Set New X-Axis
```json
{"T":110,"xAxisAngle":0}
```
- **110**: Indicates this command sets a new X-axis
- **xAxisAngle**: Angle for the new X-axis

## Mission & Steps Editing

### CMD_CREATE_MISSION - Create New Mission
```json
{"T":220,"name":"mission_a","intro":"test mission created in flash."}
```
- **220**: Indicates this command creates a new mission
- **name**: Mission name
- **intro**: Mission description

### CMD_MISSION_CONTENT - Get Mission Content
```json
{"T":221,"name":"mission_a"}
```
- **221**: Requests mission content
- **name**: Mission name

### CMD_APPEND_STEP_JSON - Append Step as JSON
```json
{"T":222,"name":"mission_a","step":"{\"T\":104,\"x\":235,\"y\":0,\"z\":234,\"t\":3.14,\"r\":0,\"g\":0,\"spd\":0.25}"}
```
- **222**: Indicates this command appends a step
- **name**: Mission name
- **step**: Step content as JSON string

### CMD_APPEND_STEP_FB - Append Current Position
```json
{"T":223,"name":"mission_a","spd":0.25}
```
- **223**: Indicates this command appends current position
- **name**: Mission name
- **spd**: Speed for this step

### CMD_APPEND_DELAY - Append Delay
```json
{"T":224,"name":"mission_a","delay":3000}
```
- **224**: Indicates this command appends a delay
- **name**: Mission name
- **delay**: Delay duration in milliseconds

### CMD_INSERT_STEP_JSON - Insert Step as JSON
```json
{"T":225,"name":"mission_a","stepNum":3,"step":"{\"T\":114,\"led\":255}"}
```
- **225**: Indicates this command inserts a step
- **name**: Mission name
- **stepNum**: Step number to insert at
- **step**: Step content as JSON string

### CMD_INSERT_STEP_FB - Insert Current Position
```json
{"T":226,"name":"mission_a","stepNum":3,"spd":0.25}
```
- **226**: Indicates this command inserts current position
- **name**: Mission name
- **stepNum**: Step number to insert at
- **spd**: Speed for this step

### CMD_INSERT_DELAY - Insert Delay
```json
{"T":227,"stepNum":3,"delay":3000}
```
- **227**: Indicates this command inserts a delay
- **stepNum**: Step number to insert at
- **delay**: Delay duration in milliseconds

### CMD_REPLACE_STEP_JSON - Replace Step with JSON
```json
{"T":228,"name":"mission_a","stepNum":3,"step":"{\"T\":114,\"led\":255}"}
```
- **228**: Indicates this command replaces a step
- **name**: Mission name
- **stepNum**: Step number to replace
- **step**: New step content as JSON string

### CMD_REPLACE_STEP_FB - Replace Step with Current Position
```json
{"T":229,"name":"mission_a","stepNum":3}
```
- **229**: Indicates this command replaces step with current position
- **name**: Mission name
- **stepNum**: Step number to replace

### CMD_REPLACE_DELAY - Replace Step with Delay
```json
{"T":230,"name":"mission_a","stepNum":3,"delay":3000}
```
- **230**: Indicates this command replaces step with a delay
- **name**: Mission name
- **stepNum**: Step number to replace
- **delay**: Delay duration in milliseconds

### CMD_DELETE_STEP - Delete Step
```json
{"T":231,"name":"mission_a","stepNum":3}
```
- **231**: Indicates this command deletes a step
- **name**: Mission name
- **stepNum**: Step number to delete

### CMD_MOVE_TO_STEP - Move to Step Position
```json
{"T":241,"name":"mission_a","stepNum":3}
```
- **241**: Indicates this command moves to step position
- **name**: Mission name
- **stepNum**: Step number to move to

### CMD_MISSION_PLAY - Execute Mission
```json
{"T":242,"name":"mission_a","times":3}
```
- **242**: Indicates this command plays a mission
- **name**: Mission name
- **times**: Number of times to execute the mission

## File System Control

### CMD_SCAN_FILES - Scan Files
```json
{"T":200}
```
- **200**: Scans files in the system

### CMD_CREATE_FILE - Create File
```json
{"T":201,"name":"file.txt","content":"inputContentHere."}
```
- **201**: Indicates this command creates a file
- **name**: File name
- **content**: File content

### CMD_READ_FILE - Read File
```json
{"T":202,"name":"file.txt"}
```
- **202**: Indicates this command reads a file
- **name**: File name to read

### CMD_DELETE_FILE - Delete File
```json
{"T":203,"name":"file.txt"}
```
- **203**: Indicates this command deletes a file
- **name**: File name to delete

### CMD_APPEND_LINE - Append Line to File
```json
{"T":204,"name":"file.txt","content":"inputContentHere."}
```
- **204**: Indicates this command appends a line
- **name**: File name
- **content**: Content to append

### CMD_INSERT_LINE - Insert Line to File
```json
{"T":205,"name":"file.txt","lineNum":3,"content":"content"}
```
- **205**: Indicates this command inserts a line
- **name**: File name
- **lineNum**: Line number to insert at
- **content**: Content to insert

### CMD_REPLACE_LINE - Replace Line in File
```json
{"T":206,"name":"file.txt","lineNum":3,"content":"Content"}
```
- **206**: Indicates this command replaces a line
- **name**: File name
- **lineNum**: Line number to replace
- **content**: New content

### CMD_READ_LINE - Read Line from File
```json
{"T":207,"name":"file.txt","lineNum":3}
```
- **207**: Indicates this command reads a line
- **name**: File name
- **lineNum**: Line number to read

### CMD_DELETE_LINE - Delete Line from File
```json
{"T":208,"name":"file.txt","lineNum":3}
```
- **208**: Indicates this command deletes a line
- **name**: File name
- **lineNum**: Line number to delete

## Switch Control

### CMD_SWITCH_CTRL - Switch Control
```json
{"T":113,"pwm_a":-255,"pwm_b":-255}
```
- **113**: Indicates this command controls switches
- **pwm_a**: PWM value for switch A
- **pwm_b**: PWM value for switch B

### CMD_LIGHT_CTRL - Light Control
```json
{"T":114,"led":255}
```
- **114**: Indicates this command controls lights
- **led**: LED brightness value

### CMD_SWITCH_OFF - Switch Off
```json
{"T":115}
```
- **115**: Turns off switches

## Servo Settings

### CMD_SET_SERVO_ID - Set Servo ID
```json
{"T":501,"raw":1,"new":11}
```
- **501**: Indicates this command sets servo ID
- **raw**: Current servo ID
- **new**: New servo ID

### CMD_SET_MIDDLE - Set Middle Position
```json
{"T":502,"id":11}
```
- **502**: Indicates this command sets middle position
- **id**: Servo ID

### CMD_SET_SERVO_PID - Set Servo PID Parameters
```json
{"T":503,"id":14,"p":16}
```
- **503**: Indicates this command sets servo PID parameters
- **id**: Servo ID
- **p**: Proportional gain value

## ESP32 Settings

### CMD_REBOOT - Reboot System
```json
{"T":600}
```
- **600**: Reboots the system

### CMD_FREE_FLASH_SPACE - Get Free Flash Space
```json
{"T":601}
```
- **601**: Gets free flash space information

### CMD_BOOT_MISSION_INFO - Get Boot Mission Info
```json
{"T":602}
```
- **602**: Gets boot mission information

### CMD_RESET_BOOT_MISSION - Reset Boot Mission
```json
{"T":603}
```
- **603**: Resets the boot mission

### CMD_NVS_CLEAR - Clear Non-Volatile Storage
```json
{"T":604}
```
- **604**: Clears non-volatile storage

### CMD_INFO_PRINT - Print Information
```json
{"T":605,"cmd":1}
```
- **605**: Indicates this command prints information
- **cmd**: Information type to print