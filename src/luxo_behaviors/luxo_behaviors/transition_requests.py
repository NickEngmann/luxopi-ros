"""Helpers for observing asynchronous ROS state-transition requests."""


def watch_transition_result(future, requested_state, logger, on_result=None):
    """Log the actual service result and return the still-asynchronous future.

    ``call_async`` only means the request was queued locally. Returning a
    successful-looking boolean at that point hides state-manager denials.
    This helper preserves nonblocking ROS executor behavior while making the
    eventual acceptance/rejection observable to callers and logs.
    """

    def report_result(completed_future):
        accepted = False
        try:
            response = completed_future.result()
            accepted = bool(response.success)
            if accepted:
                logger.debug(
                    f"State transition to {requested_state} accepted; "
                    f"current state is {response.current_state}"
                )
            else:
                logger.warning(
                    f"State transition to {requested_state} denied: {response.message}"
                )
        except Exception as exc:
            logger.error(
                f"State transition request to {requested_state} failed: {exc}"
            )
        if on_result is not None:
            try:
                on_result(accepted)
            except Exception as exc:
                logger.error(
                    f"State transition callback for {requested_state} failed: {exc}"
                )

    future.add_done_callback(report_result)
    return future
