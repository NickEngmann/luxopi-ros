from luxo_behaviors.sim_motion_controller import motion_is_frozen


def test_motion_holds_for_active_collision_even_before_state_update():
    assert motion_is_frozen("IDLE", (False, True, False))


def test_motion_holds_for_safety_states_after_sensor_clears():
    for state in ("COLLISION_AVOIDING", "ESCAPE_MODE", "ERROR", "SHUTDOWN"):
        assert motion_is_frozen(state, (False, False, False))


def test_motion_remains_available_in_ordinary_states_without_collision():
    for state in ("IDLE", "VOICE_FOLLOWING", "ANIMATING", "PETTING"):
        assert not motion_is_frozen(state, (False, False, False))
