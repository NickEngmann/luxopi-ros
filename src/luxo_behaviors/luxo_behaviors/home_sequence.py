"""Deterministic simulation of the existing two-stage physical home recipe."""
import math
from luxo_behaviors.joint_profiles import animation_pose_for_profile, joint_profile


HOME_STAGE_POSES = ((0.5, 0.5, 1.3, 1.4, -1.5),
                    (0.5, -0.85, 1.3, 1.4, -1.5))


class HomeSequence:
    def __init__(self, profile, current, now, timeout=30.0):
        names, limits = joint_profile(profile)
        if len(current) != len(names) or any(not math.isfinite(x) for x in current):
            raise ValueError('Home sequence needs complete finite measured feedback')
        base = current[0]
        lo, hi = limits[names[0]]
        if min(base - lo, hi - base) < 0.5:
            base = 0.0
        gripper = current[-1] if len(names) == 6 else 0.0
        self.targets = [animation_pose_for_profile(
            [base, *pose[1:]], profile,
            gripper_position=gripper)[1] for pose in HOME_STAGE_POSES]
        self.started = now
        self.timeout = timeout
        self.stage = (1 if max(abs(a-b) for a,b in zip(current, self.targets[1])) <= 0.03
                      else 0)
        self.settled_since = None
        self.status = 'running'
        self.reason = ''

    @property
    def target(self):
        return list(self.targets[self.stage])

    def interrupt(self, reason):
        if self.status == 'running':
            self.status, self.reason = 'interrupted', reason

    def advance(self, measured, velocities, now, *, fresh=True):
        if self.status != 'running':
            return self.status
        if now - self.started > self.timeout:
            self.status, self.reason = 'timed_out', 'Home feedback did not settle before deadline'
            return self.status
        settled = (fresh and len(measured) == len(self.target)
                   and len(velocities) == len(self.target)
                   and all(math.isfinite(x) for x in measured + velocities)
                   and max(abs(a-b) for a, b in zip(measured, self.target)) <= 0.03
                   and max(abs(v) for v in velocities) <= 0.03)
        if not settled:
            self.settled_since = None
            return self.status
        if self.settled_since is None:
            self.settled_since = now
        dwell = 0.5 if self.stage == 0 else 0.1
        if now - self.settled_since >= dwell:
            if self.stage == 0:
                self.stage, self.settled_since = 1, None
            else:
                self.status = 'completed'
        return self.status
