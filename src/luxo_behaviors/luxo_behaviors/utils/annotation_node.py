from typing import List
import time

import depthai as dai

from depthai_nodes import ImgDetectionsExtended, Classifications, SECONDARY_COLOR
from depthai_nodes.utils import AnnotationHelper


class AnnotationNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self.last_print_time = 0
        self.print_interval = 2.0  # Print every 2 seconds to avoid spam
        # Emotion labels for the 8 emotions
        self.emotion_labels = [
            'anger', 'contempt', 'disgust', 'fear',
            'happiness', 'neutral', 'sadness', 'surprise'
        ]
        # Store emotion data for external access
        self.latest_emotion = None
        self.latest_confidence = 0.0
        self.emotion_callback = None
        self.skip_output = False  # Flag to skip output when no visualizer

    def build(
        self,
        gather_data_msg: dai.Node.Output,
        emotion_callback=None,
        skip_output=False,
    ) -> "AnnotationNode":
        self.link_args(gather_data_msg)
        self.emotion_callback = emotion_callback
        self.skip_output = skip_output
        return self

    def process(self, gather_data_msg: dai.Buffer) -> None:
        dets_msg: ImgDetectionsExtended = gather_data_msg.reference_data
        assert isinstance(dets_msg, ImgDetectionsExtended)

        rec_msg_list: List[Classifications] = gather_data_msg.gathered
        assert isinstance(rec_msg_list, list)
        assert all(isinstance(rec_msg, Classifications) for rec_msg in rec_msg_list)
        assert len(dets_msg.detections) == len(rec_msg_list)

        annotations = AnnotationHelper()

        current_time = time.time()
        should_print = (current_time - self.last_print_time) > self.print_interval

        # Collect face data for single-line logging
        face_data = []

        for idx, (det_msg, rec_msg) in enumerate(zip(dets_msg.detections, rec_msg_list)):
            xmin, ymin, xmax, ymax = det_msg.rotated_rect.getOuterRect()

            annotations.draw_rectangle(
                (xmin, ymin),
                (xmax, ymax),
            )

            # Get all emotion scores
            emotion_scores = rec_msg.scores

            # Store latest emotion data and trigger callback
            if idx == 0:  # Use first face
                self.latest_emotion = rec_msg.top_class.lower()
                self.latest_confidence = rec_msg.top_score.item()

                # Call the emotion callback if provided
                if self.emotion_callback and self.latest_confidence > 0.3:
                    self.emotion_callback(self.latest_emotion, self.latest_confidence)

            # Collect face info for logging
            face_data.append(f"Face{idx + 1}:{rec_msg.top_class}({rec_msg.top_score.item():.2f})")

            annotations.draw_text(
                text=f"{rec_msg.top_class} ({rec_msg.top_score.item():.2f})",
                position=(xmin + 0.005, ymin + 0.025),
                size=20,
                color=SECONDARY_COLOR,
            )

        # Print all faces on a single line
        if should_print and face_data:
            print(f"Detected {len(face_data)} faces: {' | '.join(face_data)}", flush=True)
            self.last_print_time = current_time

        # Always send output since we ensure visualizer is connected
        annotations_msg = annotations.build(
            timestamp=dets_msg.getTimestamp(),
            sequence_num=dets_msg.getSequenceNum(),
        )
        self.out.send(annotations_msg)
