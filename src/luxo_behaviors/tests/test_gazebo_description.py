from pathlib import Path
import xml.etree.ElementTree as ET
import pytest
from luxo_behaviors.gazebo_description import build_gazebo_description, build_vendor_description, M3_NAMES

ASSETS = Path(__file__).resolve().parents[1] / 'luxo_behaviors/assets/roarm_m3'


def test_vendor_inertias_and_meshes_survive_modern_controller_adaptation(tmp_path):
    root = ET.fromstring(build_gazebo_description(ASSETS, tmp_path / 'controllers.yaml'))
    assert not any('xacro' in element.tag for element in root.iter())
    assert [joint.get('name') for joint in root.find('ros2_control').findall('joint')] == list(M3_NAMES)
    for link in root.findall('link'):
        if link.get('name') not in ('world', 'hand_tcp'):
            assert float(link.find('inertial/mass').get('value')) > 0
            for axis in ('ixx', 'iyy', 'izz'):
                assert float(link.find('inertial/inertia').get(axis)) > 0
    for joint in root.findall('joint'):
        if joint.get('type') == 'revolute':
            assert float(joint.find('limit').get('velocity')) == .5
    assert root.find('gazebo/plugin').get('filename') == 'libgz_ros2_control-system.so'
    for mesh in root.iter('mesh'):
        assert Path(mesh.get('filename').removeprefix('file://')).is_file()


@pytest.mark.parametrize('limit', [0, -1, float('nan'), float('inf')])
def test_invalid_simulator_actuator_limit_rejected(limit, tmp_path):
    with pytest.raises(ValueError):
        build_gazebo_description(ASSETS, tmp_path / 'controller.yaml', max_velocity=limit)


def test_kinematic_vendor_model_has_all_axes_without_physics_plugins():
    root = ET.fromstring(build_vendor_description(ASSETS))
    assert {j.get('name') for j in root.findall('joint') if j.get('type') == 'revolute'} == set(M3_NAMES)
    assert root.find('ros2_control') is None
    assert root.find('gazebo') is None
    assert not any('xacro' in element.tag for element in root.iter())
