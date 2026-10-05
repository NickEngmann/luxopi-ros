"""Optional actual camera SDK graph construction; no device or model download."""
import pytest


def test_v2_sdk_constructs_used_camera_nodes_without_opening_hardware():
    dai = pytest.importorskip('depthai')
    assert dai.__version__.startswith('2.'), 'Production pipeline requires DepthAI v2 APIs'
    pipeline = dai.Pipeline()
    camera = pipeline.create(dai.node.ColorCamera)
    camera.setPreviewSize(300, 300)
    camera.setInterleaved(False)
    output = pipeline.create(dai.node.XLinkOut)
    output.setStreamName('rgb')
    camera.preview.link(output.input)
    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setResize(64, 64)
    manip.setMaxOutputFrameSize(64 * 64 * 3)
    camera.preview.link(manip.inputImage)
    network = pipeline.create(dai.node.NeuralNetwork)
    network.input.setBlocking(False)
    manip.out.link(network.input)
    assert len(pipeline.getAllNodes()) == 4
