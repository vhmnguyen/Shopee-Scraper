import random


ACTION_WAIT_RANGE = (2.0, 5.0)


def action_wait(sb):
    """Choose a fresh delay for each browser action."""
    duration = random.uniform(*ACTION_WAIT_RANGE)
    sb.sleep(duration)
    return duration
