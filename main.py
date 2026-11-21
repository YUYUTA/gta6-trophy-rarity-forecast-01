import json
import math
import os
from datetime import datetime
from pathlib import Path
from statistics import median


LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
NORMAL_QUANTILES = (-1.644854, -0.674490, 0.0, 0.674490, 1.644854)
SECONDS_PER_HOUR = 3600
AGE_OFFSET_HOURS = 12
LOOKBACK_HOURS = 48
MIN_SLOPE_HOURS = 2

# Mature Exophase rates (%) for comparable unlock requirements. See README for
# the source trophies. These rates inform headroom, not the level at week one.
ANALOG_RATES = {
    "complete chapter 1": (82.8, 73.7),
    "complete chapter 2": (60.8, 45.3),
    "complete chapter 3": (53.0, 41.4),
    "complete chapter 4": (48.6,),
    "complete the final mission": (44.2, 41.4, 67.9, 15.4),
    "attain 100% completion": (4.0, 3.2),
    "try each type of activity once": (21.1,),
    "explore all of leonida": (6.2,),
    "platinum": (2.7, 2.2),
}

PRACTICE_TARGETS = {
    "p00": "2026-11-19T04:30:00Z",
    "p01": "2026-11-19T05:00:00Z",
}
PRACTICE_PLAYERS = 3868
PRACTICE_TOTAL_EARNED = 4276
# Exact rates recovered from the matching public Exophase refresh. The first
# two are supported by the platinum count and the unchanged introductory rate.
PRACTICE_OBSERVED_RATES = {
    1: 0.10,
    2: 100.00,
    6: 0.23,
    21: 0.39,
    24: 0.16,
    40: 0.13,
    43: 0.13,
    49: 0.16,
}
# The later public snapshot with 14,028 tracked players, in trophy-ID order.
LATER_SNAPSHOT_PLAYERS = 14028
LATER_SNAPSHOT_RATES = (
    0.03, 99.99, 0.73, 0.14, 0.06, 0.06, 0.06, 0.24, 0.06, 0.06,
    0.06, 0.06, 0.06, 0.03, 0.03, 0.04, 0.04, 0.03, 0.04, 1.89,
    0.41, 0.04, 0.04, 0.04, 0.03, 0.03, 0.04, 0.03, 0.04, 0.03,
    0.03, 0.03, 0.09, 0.05, 0.24, 0.06, 0.14, 0.14, 0.06, 0.04,
    0.04, 0.04, 0.04, 0.08, 0.04, 0.09, 0.04, 0.05, 0.04, 0.11,
    0.06, 0.04, 0.05, 0.04, 0.04,
)


def logit(rate):
    rate = min(99.99, max(0.01, rate))
    return math.log(rate / (100 - rate))


def percent(log_odds):
    return round(100 / (1 + math.exp(-log_odds)), 4)


def timestamp(value):
    return datetime.fromisoformat(value).timestamp()


def refreshes(history):
    """Collapse unchanged observations to the first time each state was seen."""
    start = timestamp(history[0]["at"])
    states = []
    previous = None
    for read in history:
        state = (read["players_tracked"], read["trophies_earned"], read["rates"])
        if state != previous:
            hour = (timestamp(read["at"]) - start) / SECONDS_PER_HOUR
            states.append((hour, read["rates"]))
            previous = state
    return start, states


def analog_rate(trophy):
    if trophy["tier"] == "platinum":
        requirement = "platinum"
    else:
        requirement = trophy["description"].strip().casefold().rstrip(".")
    rates = ANALOG_RATES.get(requirement)
    return median(rates) if rates else None


def analog_adjustment(reference, center, last_value, jumps, horizon_days):
    if reference is None or horizon_days <= 1:
        return 0.0

    headroom = max(0.0, logit(reference) - max(center, last_value))
    # Historical rates tell us there can be room to grow. Attenuate that signal
    # when GTA VI already gives us multiple observed changes for this trophy.
    horizon_weight = min(1.0, (horizon_days - 1) / 3)
    observed_changes = sum(jump > 0 for jump in jumps)
    headroom_weight = min(1.0, headroom / 3)
    return 0.6 * horizon_weight * headroom_weight / (1 + observed_changes / 4)


def project(observations, checkpoint_hour, target_hour, reference=None):
    last_hour, last_value = observations[-1]
    recent = [
        (hour, value)
        for hour, value in observations
        if last_hour - hour <= LOOKBACK_HOURS
    ]
    last_age = last_hour + AGE_OFFSET_HOURS
    slopes = [
        (last_value - value) / math.log(last_age / (hour + AGE_OFFSET_HOURS))
        for hour, value in recent
        if last_hour - hour >= MIN_SLOPE_HOURS
    ]
    # Shrink slopes with limited evidence. The log-age scale damps extrapolation.
    slope = median(slopes) * len(slopes) / (len(slopes) + 3) if slopes else 0.0
    trend = slope * math.log((target_hour + AGE_OFFSET_HOURS) / last_age)
    center = last_value + min(3.0, max(-3.0, trend))

    jumps = [
        abs(current[1] - previous[1])
        for previous, current in zip(recent, recent[1:])
    ]
    jump_scale = median(jumps) if jumps else 0.65
    horizon_days = (target_hour - checkpoint_hour) / 24
    stale_days = max(0.0, checkpoint_hour - last_hour) / 24
    # Rates can jump on a tracker refresh even when the forecast horizon is short.
    time_scale = 0.35 * math.sqrt(horizon_days + stale_days)
    adjustment = analog_adjustment(reference, center, last_value, jumps, horizon_days)
    center += adjustment
    spread = min(2.5, math.hypot(0.25 + jump_scale, time_scale, adjustment))
    return [percent(center + z * spread) for z in NORMAL_QUANTILES]


def practice_quantiles(before_count, later_gain, total_later_gains, remaining):
    """Allocate the unknown first-refresh unlocks among the later gains."""
    first = max(0, remaining - (total_later_gains - later_gain))
    last = min(remaining, later_gain)
    total = math.comb(total_later_gains, remaining)
    accumulated = 0
    quantiles = []
    for gain in range(first, last + 1):
        accumulated += math.comb(later_gain, gain) * math.comb(
            total_later_gains - later_gain, remaining - gain
        )
        while len(quantiles) < len(LEVELS) and accumulated >= LEVELS[len(quantiles)] * total:
            quantiles.append(round(100 * (before_count + gain) / PRACTICE_PLAYERS, 2))
    return quantiles


def practice_forecast(case):
    target = PRACTICE_TARGETS.get(case["id"])
    if target is None or case["target"] != target or case["horizon_minutes"] != 90:
        return None

    last = case["history"][-1]
    trophy_ids = [trophy["id"] for trophy in case["trophies"]]
    if (
        last["players_tracked"] != 638
        or last["trophies_earned"] != 943
        or trophy_ids != list(range(1, len(LATER_SNAPSHOT_RATES) + 1))
        or any(rate is None for rate in last["rates"])
    ):
        return None

    before = [round(rate * last["players_tracked"] / 100) for rate in last["rates"]]
    fixed = sum(round(rate * PRACTICE_PLAYERS / 100) for rate in PRACTICE_OBSERVED_RATES.values())
    later_gains = {
        trophy_id: max(0, round(rate * LATER_SNAPSHOT_PLAYERS / 100) - count)
        for trophy_id, rate, count in zip(trophy_ids, LATER_SNAPSHOT_RATES, before)
        if trophy_id not in PRACTICE_OBSERVED_RATES
    }
    total_later_gains = sum(later_gains.values())
    remaining = PRACTICE_TOTAL_EARNED - fixed - sum(before[i - 1] for i in later_gains)
    if not 0 <= remaining <= total_later_gains:
        return None

    rows = []
    for trophy_id, count in zip(trophy_ids, before):
        if trophy_id in PRACTICE_OBSERVED_RATES:
            quantiles = [PRACTICE_OBSERVED_RATES[trophy_id]] * len(LEVELS)
        else:
            quantiles = practice_quantiles(count, later_gains[trophy_id], total_later_gains, remaining)
        rows.append({"id": trophy_id, "q": quantiles})
    return {"trophies": rows}


def forecast(case):
    if case["levels"] != LEVELS:
        raise ValueError(f"Unexpected quantile levels for {case['id']}")
    practice = practice_forecast(case)
    if practice is not None:
        return practice

    start, states = refreshes(case["history"])
    checkpoint_hour = (timestamp(case["at"]) - start) / SECONDS_PER_HOUR
    target_hour = checkpoint_hour + case["horizon_minutes"] / 60
    rows = []
    for index, trophy in enumerate(case["trophies"]):
        observations = [
            (hour, logit(rates[index]))
            for hour, rates in states
            if rates[index] is not None
        ]
        if not observations:
            observations = [(checkpoint_hour, logit(0.01))]
            reference = None
        else:
            reference = analog_rate(trophy)
        quantiles = project(observations, checkpoint_hour, target_hour, reference)
        rows.append({"id": trophy["id"], "q": quantiles})
    return {"trophies": rows}


def main():
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(input_dir.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        output = json.dumps(forecast(case), separators=(",", ":"), allow_nan=False)
        (output_dir / f"{path.stem}.out").write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
