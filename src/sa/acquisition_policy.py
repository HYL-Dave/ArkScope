"""Pure rolling-window admission for managed SA page-navigation attempts."""

from collections import defaultdict
import math


def validate_policy(policy):
    keys = {"hour_limit", "day_limit", "hour_reserve", "day_reserve"}
    if type(policy) is not dict or set(policy) != keys:
        raise ValueError("invalid navigation policy")
    for window in ("hour", "day"):
        limit, reserve = policy[window + "_limit"], policy[window + "_reserve"]
        if type(limit) is not int or type(reserve) is not int or not 0 <= reserve <= limit or limit < 1:
            raise ValueError("invalid navigation policy")
    return dict(policy)


def navigation_eligibility(attempts, policy, priority, now):
    policy = validate_policy(policy)
    if type(now) not in (int, float) or not math.isfinite(now) or now < 0 or priority not in {"routine", "background"}:
        raise ValueError("invalid navigation clock or priority")
    counts = [[0, 0], [0, 0]]
    expirations = defaultdict(list)
    for at, lane in attempts:
        if type(at) not in (int, float) or not math.isfinite(at) or not 0 <= at <= now or lane not in {"routine", "background"}:
            raise ValueError("invalid navigation history")
        for index, seconds in enumerate((3600, 86400)):
            if at > now - seconds:
                routine = int(lane == "routine")
                counts[index][0] += 1
                counts[index][1] += routine
                expirations[at + seconds].append((index, routine))

    def allowed():
        for index, window in enumerate(("hour", "day")):
            used, routine = counts[index]
            reserve = max(0, policy[window + "_reserve"] - routine) if priority == "background" else 0
            if used >= policy[window + "_limit"] - reserve:
                return False
        return True

    if allowed():
        return {"allowed": True, "retry_at": None}
    # Expiring routine traffic also restores its reserve, so the oldest attempt
    # alone is not necessarily the next usable background slot.
    for at in sorted(expirations):
        for index, routine in expirations[at]:
            counts[index][0] -= 1
            counts[index][1] -= routine
        if allowed():
            return {"allowed": False, "retry_at": at}
    return {"allowed": False, "retry_at": None}
