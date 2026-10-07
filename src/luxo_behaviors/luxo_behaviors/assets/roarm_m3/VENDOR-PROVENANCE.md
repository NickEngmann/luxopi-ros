# RoArm-M3 model provenance

The optional RoArm-M3 dashboard model is sourced from the official Waveshare
ROS 2 workspace, branch `ros2-humble`, commit
`40dbd84b553695212fab713e8465f817ba95454` (2025-07-25):

<https://github.com/waveshareteam/roarm_ws/tree/40dbd84b553695212fab713e8465f817ba95454/src/roarm_main/roarm_description>

The pinned `roarm_description/package.xml` declares the package license as
MIT. That upstream checkout contains no standalone license file or explicit
copyright notice. This provenance note records the upstream declaration
without inventing a copyright holder or year. The original model files are
retained here with their source filenames.

The model uses the vendor M3 xacro and seven visual meshes: base, links 1–5,
and gripper. Its STL geometry is millimetres and the xacro scales each mesh by
`0.001`. The xacro defines six revolute joints and a fixed `hand_tcp`; links
have inertial masses and inertias, and collision meshes currently reuse the
visual meshes. Its `.gazebo` file references the Gazebo Classic
`libgazebo_ros_control.so` plugin, which is not the Gazebo Harmonic/Jazzy
integration used by newer ROS installations.

The vendor driver maps the M3 `JointState` names in this order: base,
shoulder, elbow, wrist, roll, gripper. The existing Luxo animation and
simulated-motion contract publishes four arm joints. In the optional M3
preview those four map to the vendor base, shoulder, elbow, and wrist joints;
roll and gripper stay at zero. The view clamps only its displayed values to
vendor M3 position limits and marks that limitation in the UI. It does not
change published motion targets or imply that the app now controls the last
two actuators.
