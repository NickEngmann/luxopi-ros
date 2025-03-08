Reset
CMD_MOVE_INIT - Move to the Initial Position
{"T":100}
100: indicates this command is CMD_MOVE_INIT, which can rotate all joints of the robotic arm to the initial position.
Under normal circumstances, the robotic arm will automatically move to its initial position when powered on.

This command will cause the process to block.

Joint Angle Control
CMD_SINGLE_JOINT_CTRL - Single Joint Control (in radians)
{"T":101,"joint":0,"rad":0,"spd":0,"acc":10}
101: indicating this command is CMD_SINGLE_JOINT_CTRL, the rotation of a joint of the robot arm is controlled in the form of an arc system.
joint: joint numbers.
1: BASE_JOINT
2: SHOULDER_JOINT
3: ELBOW_JOINT
4: EOAT_JOINT
rad: the angle to be rotated (in radians), taking the initial position of each joint, the default angle and rotation direction of each joint are as follows:
The default initial angle of BASE_JOINT is 0, and its rotation range is 3.14 to -3.14. When the angle increases, the base joint turns left. When the angle decreases, the base joint turns right.
The default initial angle of SHOULDER_JOINT is 0, and its rotation range is 1.57 to -1.57. When the angle increases, the shoulder joint rotates forward. When the angle decreases, the shoulder joint rotates backward.
The default initial angle of ELBOW_JOINT is 1.570796, and its rotation range is 3.14 to -1.11. When the angle increases, the elbow joint rotates downward. When the angle decreases, the elbow joint rotates reversely.
The initial angle of EOAT_JOINT is 3.141593. RoArm-M2-S adopts the clamp by default with a rotation range of 1.08 to 3.14. When the angle decreases, the clamp joint will open. If you adopt the wrist joint, the rotation range is 1.08 to 5.20. When the angle increases, the wrist joint rotates downward. When the angle increases, the wrist joint rotates upward.
spd: The rotation speed, measured in steps per second, is used to control the speed of the servos. In this system, one full rotation of a servo corresponds to 4096 steps. A higher numerical value will result in a faster speed, and when the speed value is set to 0, it will rotate at the maximum speed.
acc: The acceleration at the start and end of rotation can be controlled with a numerical value, which should be a value between 0 and 254, measured in 100 steps per second squared. A smaller numerical value results in smoother acceleration and deceleration. For example, if set to 10, it will accelerate and decelerate at 1000 steps per second squared. When the acceleration value is set to 0, it will use the maximum acceleration.
CMD_JOINTS_RAD_CTRL - All Angle Control (in radians)
{"T":102,"base":0,"shoulder":0,"elbow":1.57,"hand":3.14,"spd":0,"acc":10}
102: indicates the command is CMD_JOINTS_RAD_CTRL, which controls the rotation of all joints for the robotic arm in radians.
base: the angle of the base joints. You can refer to the rotation angle range through the rad key in the "CMD_SINGLE_JOINT_CTRL" command.
shoulder: the angle of shoulder joints
elbow: the angle of elbow joints
hand: the angle of clamp/wrist joints
spd: The speed of rotation, the speed unit is step/second, one revolution of the servo is 4096 steps, the larger the value the faster the speed, when the speed value is 0, it rotates at the maximum speed.
acc: Acceleration at the beginning and end of the rotation, the smaller the value the smoother the start and stop, the value can be 0-254, and the unit is 100 steps per second ^ 2. If the setting is 10, it will be in accordance with the 1000 steps per second of the square of the acceleration and deceleration speed change. When the acceleration value is 0, it will run at the maximum acceleration.
CMD_EOAT_HAND_CTRL - EoAT Control (in radians)
{"T":106,"cmd":3.14,"spd":0,"acc":0}
106: this command is CMD_EOAT_HAND_CTRL for setting the rotation angle of the clamp/wrist joint.
cmd: the rotation angle to be rotated (in radians). the default initial angle of EOAT_JOINT is 3.141593.
RoArm adopts the clamp by default with a rotation range of 1.08 to 3.14. When the angle decreases, the clamp will open.
If you change it to the wrist joint, the rotation range is 1.08 to 5.20. When the angle increases, the wrist joint rotates downward. When the angle decreases, the wrist joint rotates upward.
spd: the speed of rotation, the speed unit is step/second, one revolution of the servo is 4096 steps, the larger the value the faster the speed, when the speed value is 0, it rotates at the maximum speed.
acc: Acceleration at the beginning and end of the rotation, the smaller the value the smoother the start and stop, the value can be 0-254, and the unit is 100 steps per second ^ 2. If the setting is 10, it will be in accordance with the 1000 steps per second of the square of the acceleration and deceleration speed change. When the acceleration value is 0, it will run at the maximum acceleration.
CMD_SINGLE_JOINT_ANGLE - Single Joint Control (in radians)
{"T":121,"joint":1,"angle":0,"spd":10,"acc":10}
121: this command is CMD_SINGLE_JOINT_ANGLE for controlling the rotation of some joints of the robotic arm in radians.
joint: joint number.
1: BASE_JOINT
2: SHOULDER_JOINT
3: ELBOW_JOINT
4: EOAT_JOIN, the angle of the clamp/wrist
angle: the angle to be rotated. Taking the initial position of each joint, the default angle and rotation direction of each joint are as follows:
The default initial angle of BASE_JOINT is 0° with the rotation range of 180° to -180°. When the angle increases, the base joint turns left. When the angle decreases, the base joint turns right.
The default initial angle of SHOULDER_JOINT is 0° with the rotation range of 90° to -90°. When the angle increases, the shoulder joint rotates forward. When the angle decreases, the shoulder joint rotates backward.
The default initial angle of ELBOW_JOINT is 90° with the rotation range of 180° to -45°. When the angle increases, the elbow joint rotates downward. When the angle decreases, the elbow joint rotates upward.
The default initial angle of EOAT_JOINT is 180° with the rotation range of 45°to 180°. When the angle decreases, the clamp will open. If you change it to the wrist joint, the rotation range is 45° to 315°. When the angle increases, the wrist joint rotates downward. When the angle decreases, the wrist joint rotates upward.
spd: The speed of rotation, the speed unit is °/s, the larger the value the faster the speed, when the speed value is 0, it rotates at the maximum speed.
acc: Acceleration at the beginning and end of the rotation, the smaller the value the smoother the start and stop in °/s^2. When the acceleration value is 0, the operation is in accordance with the maximum acceleration.
CMD_JOINTS_ANGLE_CTRL - All Joints Control (In angles)
{"T":122,"b":0,"s":0,"e":90,"h":180,"spd":10,"acc":10}
122: this command is CMD_JOINTS_ANGLE_CTRL controlling the rotation of all joints of the robot arm in angles.
b: the angle of the base joint. For the angle of the base joint, see the description of the angle key in the "CMD_SINGLE_JOINT_ANGLE" command for the range of angular rotation.
s: the angle of the shoulder joint.
e: the angle of the elbow joint.
h: the angle of the clamp/wrist joint.
spd: The speed of rotation, the speed unit is °/s, the larger the value the faster the speed, when the speed value is 0, it rotates at the maximum speed.
acc: Acceleration at the beginning and end of the rotation, the smaller the value the smoother the start and stop, the value can be 0-254 in °/s^2. When the acceleration value is 0, the operation is in accordance with the maximum acceleration.
3D Cartesian Coordinate Control
CMD_SINGLE_AXIS_CRTL - Individual Axis Position Control of Robotic Arm EoAT (inverse kinematics)
{"T":103,"axis":2,"pos":0,"spd":0.25}
The definition of the axes of the robot arm is based on the right-hand rule, with the X-axis positively oriented directly in front of the robot arm, the Y-axis positively oriented to the left of the front of the robot arm, and the Z-axis positively oriented directly above the vertical of the robot arm.

103: Indicates that this command is CMD_SIGNLE_AXIS_CRTL to control the robotic arm motion by giving the coordinate position of a separate axis to the EoAT of the robotic arm.
axis: indicates the axis number. 1-X axis; 2-Y axis; 3-Z axis; 4-T axis, clamp/wrist angle (in radian).
pos: A specific position of an axis in mm. e.g. the example above is to move the EoAT of the robotic arm to position 0 of the Y-axis, which is directly in front of the robotic arm.
spd: The speed of the movement, the larger the value the faster the speed, this move command contains a curve speed control function at the bottom of the command, so the speed is not constant.
This command causes the process to block.

CMD_XYZT_GOAL_CTRL - EoAT Control (inverse kinematics)
{"T":104,"x":235,"y":0,"z":234,"t":3.14,"spd":0.25}
104: indicates this command is CMD_XYZT_GOAL_CTRL for controlling the movement of EoAT.
x, y, z, t: represents the specific position of four axes, the unit is mm. For more details, you can refer to the above introduction of CMD_SINGLE_AXIS_CTRL.
spd: indicates the movement speed. The bigger the value is, the faster the speed is. This movement command includes a curve speed control function at the bottom, so the speed is not constant.
This command may cause the movement to be blocked.

CMD_XYZT_DIRECT_CTRL - EoAT Position Control (inverse kinematics)
{"T":1041,"x":235,"y":0,"z":234,"t":3.14}
1041: Indicates that this instruction is CMD_XYZT_DIRECT_CTRL, which controls the movement of the end point position of the robot arm.
x, y, z, t: The specific position of each of the four axes in mm. For details, refer to the description in the CMD_SINGLE_AXIS_CTRL command above.
Note: the difference between this command and the above command is that this command will not cause blocking. As there is no interpolation calculation in the bottom layer, the robotic arm will move to the target point at the fastest speed after calling this command. It is suitable for the case that a new target point is given continuously by this command, and the difference in the target point position between each command should not be too big.

CMD_SERVO_RAD_FEEDBACK - Get Feedback from Robotic Arm
{"T":105}
105: indicates this command is CMD_SERVO_RAD_FEEDBACK for getting the feedback of the EoAT including coordinates, all joint angles, and the load.
After inputting this command, it feedbacks below:

{"T":1051,"x":309.0444117,"y":3.318604879,"z":238.2448043,"b":0.010737866,"s":-0.004601942,"e":1.570796327,"t":3.141592654,"torB":-56,"torS":-20,"torE":0,"torH":0}
x, y, z: respectively represents the EoAT coordinates of the X, Y, and Z axis.
b, s, e, t: respectively represents the base joint, shoulder joint, elbow joint, and EoAT joint angles (in radian).
torB, torS, torE, torH: respectively represent the load of the base joint, shoulder joint, elbow joint, and EoAT.
CMD_CONSTANT_CTRL - Continuous Movement Control (angle control + inverse kinematics control)
{"T":123,"m":0,"axis":0,"cmd":0,"spd":0}
123: this command is CMD_CONSTANT_CTRL for enabling each joint of the robotic arm or the EoAT of the robotic arm to move continuously after an instruction is input.
m: continuous movement control mode
0: angle control mode
1: coordinate control mode
axis: Control different joint rotations in different modes.
In angle control mode: when the value of m is 0, it controls the angle rotation of all joints for the robotic arm. 1-Base joint, 2-SHOULDER joint, 3-ELBOW joint, and 4-HAND clamp/wrist joint.
Coordinate control mode: when the value of m is 1, it controls the rotation of the EoAT coordinates. 1-X axis, 2-Y axis, 3-Z axis, and 4-HAND clamp/wrist joint.
cmd: movement status.
0-STOP movement.
1-INCREASE: The angle increases in angle control mode; the coordinates increase in inverse kinematics control mode.
2-DECREASE: The angle decreases in angle control mode; the coordinates decrease in inverse kinematics control mode.
spd: the speed coefficient, the bigger the value, the faster the speed. As the rotation speed of each joint is limited, the value is suggested in the range of 0-20.
This chapter introduces the JSON command meaning for the robotic arm, for more learning, you can click here to view.

JSON (JavaScript Object Notation) is a lightweight data exchange format, typically used for transmitting and storing data between different systems. JSON originally originated from JavaScript, but it has become an independent data format from programming languages and can therefore be used and parsed in various programming languages.

JSON commands are like a standardized "menu" that can tell the robotic arm the angles at which each joint needs to rotate, where the robotic arm needs to move to, and how fast to move, etc.

Basic format of JSON Command
The basic format of a JSON command is: key:value

The key must be a string enclosed in double quotation marks;
Values can be of various types: strings, numbers, objects, arrays, Boolean values, or null. Among them, strings must be enclosed in double quotes, while others do not require quotes;
Let's use a simple example to understand the JSON command. The following is the command for releasing the end point of the robotic arm:

{"T":106,"cmd":1.57,"spd":0,"acc":0}
Among them, T, cmd, spd, and acc in double quotation marks are keys, and values are after colons. Explanation of this command:

"T": 106 represents the command used to control the rotation of the end joint of the robotic arm (CMD_EOAT_HAND_CTRL). This is a fixed value, which cannot be changed, is a numerical value that the program recognizes the purpose of the command.
The value of T is defined in the header file jsonn_cmd. h of the product's slave computer program.
Note: Different control commands will use different T values.
"cmd": The angle at which the end joint needs to be rotated (displayed in radians). The default initial position of the end joint is 3.14. The value given here is 1.57, so the gripper rotate openly.
"spd": The speed of joint rotation. When the speed value is 0, rotate at maximum speed.
"acc": Acceleration of joint rotation. When the acceleration value is 0, rotate at maximum acceleration.
This command tells the robotic arm: "Please open the gripper with maximum speed and acceleration."

Each symbol in a JSON command is important, and missing commas or parentheses can cause the directive to fail to execute. It is recommended that you directly copy and paste the command of the corresponding function and change the corresponding value.
Why use JSON commands for communication?
The following are the advantages of using JSON formatted commands to control robots:

1. Good readability

JSON is a lightweight text data format that is easy for humans to read and write. It uses the form of key-value pairs, which makes the commands easy to understand and debug, especially during the development and testing phases.

2. Easy to parse

Many programming languages provide JSON parsers, making parsing JSON commands very easy. This makes it easy to convert commands into executable operations.

3. Cross platform compatibility

JSON is a universal format that can be used on almost any programming language and platform. This means that you can use different programming languages to send and receive JSON commands.

4. Structured data

JSON supports nested data structures and can contain objects and arrays. This allows you to organize commands in a clear manner, including parameters, options, and subcommands.

5. Scalability

You can easily add new fields and parameters to JSON commands to support more features and options without changing the overall structure of the command.

6. Easy to integrate

JSON is the standard input and output format for many APIs and Web services. This enables robots to seamlessly inherit from other systems and services, such as communicating through REST APIs.

7. Standardization

JSON is a standardized data format that is widely supported and adopted. This means that you can use various libraries and tools to process and manipulate JSON data.

8. Support for multiple languages

Due to the fact that JSON can be used in multiple programming languages, it is possible to implement robot control systems written in multiple languages without the need to rewrite command parsers.

Overall, JSON formatted commands provide a simple, flexible, readable, and easily parsed way to control robots, making robot control systems more powerful and maintainable.

TORQUE CTRL - Torque Lock Control
CMD_TORQUE_CTRL
{"T":210,"cmd":0}
210: This command is CMD_TORQUE_CTRL and controls the torque switch ON/OFF.
cmd: Torque lock switch mode.
0: This means "turn off the torque lock," allows you to manually move the joints of the robotic arm when the arm is powered on.
1: This means "turn on the torque lock" prevents manual movement of the joints when the robotic arm is powered on.
Note: after turning off the torque lock, the torque lock will automatically be on if any joints of the robotic arm receive other rotation commands.

DYNAMIC ADAPTATION - Dynamic Force Self-Adaption
CMD_DYNAMIC_ADAPTATION
{"T":112,"mode":1,"b":60,"s":110,"e":50,"h":50}

{"T":112,"mode":0,"b":1000,"s":1000,"e":1000,"h":1000}
112: This command is labeled as "CMD_DYNAMIC_ADAPTATION" and is used to control the status of the dynamic external force adaptive function. Here's an explanation of the parameters:
mode: The code for the dynamic external force adaptive mode.
0: Represents the function is turned off. When turned off, you cannot manually move the joints when the robotic arm is powered on.
1: Represents the function is turned on. When turned on, using an external force to move the robotic arm will result in the arm returning to its previous position.
b: Represents the maximum torque limit for the BASE joint.
s: Represents the maximum torque limit for the SHOULDER joint.
e: Represents the maximum torque limit for the ELBOW joint.
h: Represents the maximum torque limit for the GRIPPER/WRIST joint.
You can set the maximum torque limit values as per your requirements.

When this function is in the "on" state and the applied external force exceeds the set maximum torque limit value, the robotic arm will move in response to the external force and then return to its previous position. The larger the set maximum torque limit value, the more force is required to move the arm, and the arm will rebound to its original position more quickly. Conversely, a smaller set maximum torque limit value requires less force but results in a slower rebound speed.

When this function is in the "off" state, the default maximum torque limit for all joints is set to 1000.


TORQUE CTRL
CMD_TORQUE_CTRL
{"T":210,"cmd":0}
INPUT
DYNAMIC ADAPTATION
CMD_SET_NEW_X
{"T":112,"mode":1,"b":60,"s":110,"e":50,"t":50,"r":50,"h":50}
INPUT
MOVING CTRL
CMD_MOVE_INIT
{"T":100}
INPUT
CMD_SINGLE_JOINT_CTRL
{"T":101,"joint":0,"rad":0,"spd":0,"acc":10}
INPUT
CMD_JOINTS_RAD_CTRL
{"T":102,"base":0,"shoulder":0,"elbow":1.57,"wrist":0,"roll":0,"hand":1.57,"spd":0,"acc":10}
INPUT
CMD_XYZT_GOAL_CTRL
{"T":104,"x":235,"y":0,"z":234,"t":0,"r":0,"g":3.14,"spd":0.25}
INPUT
CMD_XYZT_DIRECT_CTRL
{"T":1041,"x":235,"y":0,"z":234,"t":0,"r":0,"g":3.14}
INPUT
CMD_SERVO_RAD_FEEDBACK
{"T":105}
INPUT
CMD_EOAT_HAND_CTRL
{"T":106,"cmd":3.14,"spd":0,"acc":0}
INPUT
CMD_SINGLE_JOINT_ANGLE
{"T":121,"joint":1,"angle":0,"spd":10,"acc":10}
INPUT
CMD_JOINTS_ANGLE_CTRL
{"T":122,"b":0,"s":0,"e":90,"t":0,"r":0,"h":180,"spd":10,"acc":10}
INPUT
CMD_CONSTANT_CTRL
{"T":123,"m":0,"axis":0,"cmd":0,"spd":3}
INPUT
CMD_DELAY_MILLIS
{"T":111,"cmd":3000}
INPUT
EOAT CTRL
CMD_EOAT_GRAB_TORQUE
{"T":107,"tor":200}
INPUT
JOINTS PID CTRL
CMD_SET_JOINT_PID
{"T":108,"joint":3,"p":16,"i":0}
INPUT
CMD_RESET_PID
{"T":109}
INPUT
SET X-AXIS
CMD_SET_NEW_X
{"T":110,"xAxisAngle":0}
INPUT
MISSION & STEPS EDIT
CMD_CREATE_MISSION
{"T":220,"name":"mission_a","intro":"test mission created in flash."}
INPUT
CMD_MISSION_CONTENT
{"T":221,"name":"mission_a"}
INPUT
CMD_APPEND_STEP_JSON
{"T":222,"name":"mission_a","step":"{\"T\":104,\"x\":235,\"y\":0,\"z\":234,\"t\":3.14,\"r\":0,\"g\":0,\"spd\":0.25}"}
INPUT
CMD_APPEND_STEP_FB
{"T":223,"name":"mission_a","spd":0.25}
INPUT
CMD_APPEND_DELAY
{"T":224,"name":"mission_a","delay":3000}
INPUT
CMD_INSERT_STEP_JSON
{"T":225,"name":"mission_a","stepNum":3,"step":"{\"T\":114,\"led\":255}"}
INPUT
CMD_INSERT_STEP_FB
{"T":226,"name":"mission_a","stepNum":3,"spd":0.25}
INPUT
CMD_INSERT_DELAY
{"T":227,"stepNum":3,"delay":3000}
INPUT
CMD_REPLACE_STEP_JSON
{"T":228,"name":"mission_a","stepNum":3,"step":"{\"T\":114,\"led\":255}"}
INPUT
CMD_REPLACE_STEP_FB
{"T":229,"name":"mission_a","stepNum":3}
INPUT
CMD_REPLACE_DELAY
{"T":230,"name":"mission_a","stepNum":3,"delay":3000}
INPUT
CMD_DELETE_STEP
{"T":231,"name":"mission_a","stepNum":3}
INPUT
CMD_MOVE_TO_STEP
{"T":241,"name":"mission_a","stepNum":3}
INPUT
CMD_MISSION_PLAY
{"T":242,"name":"mission_a","times":3}
INPUT
FILE SYSTEM CTRL
CMD_SCAN_FILES
{"T":200}
INPUT
CMD_CREATE_FILE
{"T":201,"name":"file.txt","content":"inputContentHere."}
INPUT
CMD_READ_FILE
{"T":202,"name":"file.txt"}
INPUT
CMD_DELETE_FILE
{"T":203,"name":"file.txt"}
INPUT
CMD_APPEND_LINE
{"T":204,"name":"file.txt","content":"inputContentHere."}
INPUT
CMD_INSERT_LINE
{"T":205,"name":"file.txt","lineNum":3,"content":"content"}
INPUT
CMD_REPLACE_LINE
{"T":206,"name":"file.txt","lineNum":3,"content":"Content"}
INPUT
CMD_READ_LINE
{"T":207,"name":"file.txt","lineNum":3}
INPUT
CMD_DELETE_LINE
{"T":208,"name":"file.txt","lineNum":3}
INPUT
SWITCH CTRL
CMD_SWITCH_CTRL
{"T":113,"pwm_a":-255,"pwm_b":-255}
INPUT
CMD_LIGHT_CTRL
{"T":114,"led":255}
INPUT
CMD_SWITCH_OFF
{"T":115}
INPUT
SERVO SETTINGS
CMD_SET_SERVO_ID
{"T":501,"raw":1,"new":11}
INPUT
CMD_SET_MIDDLE
{"T":502,"id":11}
INPUT
CMD_SET_SERVO_PID
{"T":503,"id":14,"p":16}
INPUT
ESP32 SETTINGS
CMD_REBOOT
{"T":600}
INPUT
CMD_FREE_FLASH_SPACE
{"T":601}
INPUT
CMD_BOOT_MISSION_INFO
{"T":602}
INPUT
CMD_RESET_BOOT_MISSION
{"T":603}
INPUT
CMD_NVS_CLEAR
{"T":604}
INPUT
CMD_INFO_PRINT
{"T":605,"cmd":1}

Can we remake direct_test with this API as our guideline