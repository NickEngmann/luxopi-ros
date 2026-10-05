"""Adapt the pinned vendor M3 model to modern Gazebo without invented inertias."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET


M3_NAMES = (
    'base_link_to_link1', 'link1_to_link2', 'link2_to_link3',
    'link3_to_link4', 'link4_to_link5', 'link5_to_gripper_link',
)


def build_vendor_description(asset_directory):
    """Resolve the authentic vendor geometry without requiring Gazebo or xacro."""
    assets = Path(asset_directory).resolve()
    root = ET.parse(assets / 'roarm_m3.xacro').getroot()
    for child in list(root):
        if child.tag.startswith('{http://www.ros.org/wiki/xacro}'):
            root.remove(child)
    for material in ET.parse(assets / 'materials.xacro').getroot():
        root.append(material)
    for mesh in root.iter('mesh'):
        basename = mesh.attrib['filename'].split('/')[-1]
        target = assets / basename
        if not target.is_file() or target.parent != assets:
            raise ValueError('Vendor mesh missing or outside the model directory')
        mesh.set('filename', target.as_uri())
    revolute = {joint.get('name'): joint for joint in root.findall('joint') if joint.get('type') == 'revolute'}
    if set(revolute) != set(M3_NAMES):
        raise ValueError('Vendor model must contain exactly the six expected M3 axes')
    return ET.tostring(root, encoding="unicode")


def build_gazebo_description(asset_directory, controller_parameters, *, max_velocity=.5, effort_limit=3.0):
    """Use vendor mesh/inertia/position bounds; explicit simulation actuator limits.

    Velocity/effort values are simulator configuration, not calibrated motor
    specifications. Vendor xacro has zero velocity/effort bounds and obsolete
    Classic plugins; neither is usable as a modern dynamic controller setup.
    """
    if any(not math.isfinite(value) or value <= 0 for value in (max_velocity, effort_limit)):
        raise ValueError('Simulator actuator limits must be finite and positive')
    root = ET.fromstring(build_vendor_description(asset_directory))
    revolute = {joint.get("name"): joint for joint in root.findall("joint") if joint.get("type") == "revolute"}
    control = ET.SubElement(root, 'ros2_control', {'name': 'GazeboSimSystem', 'type': 'system'})
    hardware = ET.SubElement(control, 'hardware')
    ET.SubElement(hardware, 'plugin').text = 'gz_ros2_control/GazeboSimSystem'
    for name in M3_NAMES:
        limit = revolute[name].find('limit')
        limit.set('velocity', str(max_velocity))
        limit.set('effort', str(effort_limit))
        joint = ET.SubElement(control, 'joint', {'name': name})
        interface = ET.SubElement(joint, 'command_interface', {'name': 'position'})
        ET.SubElement(interface, 'param', {'name': 'min'}).text = limit.get('lower')
        ET.SubElement(interface, 'param', {'name': 'max'}).text = limit.get('upper')
        position = ET.SubElement(joint, 'state_interface', {'name': 'position'})
        ET.SubElement(position, 'param', {'name': 'initial_value'}).text = '0.0'
        ET.SubElement(joint, 'state_interface', {'name': 'velocity'})
        ET.SubElement(joint, 'state_interface', {'name': 'effort'})
    gazebo = ET.SubElement(root, 'gazebo')
    plugin = ET.SubElement(gazebo, 'plugin', {
        'filename': 'libgz_ros2_control-system.so', 'name': 'gz_ros2_control::GazeboSimROS2ControlPlugin'})
    ET.SubElement(plugin, 'parameters').text = str(Path(controller_parameters).resolve())
    ET.SubElement(plugin, 'position_proportional_gain').text = '0.1'
    return ET.tostring(root, encoding='unicode')
