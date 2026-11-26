"""Quality-bounded logarithmic warmth with exponential reversion to manual anchors."""

import math
import time
from collections import OrderedDict
from datetime import datetime
from zoneinfo import ZoneInfo


class Affinity:
    def __init__(self):
        self.rows = OrderedDict()
        self.seen = OrderedDict()

    def offset(self, key, config, now=None):
        now = time.time() if now is None else now
        row = self.rows.get(key)
        return (
            (row["offset"] * math.exp2(-max(0, now - row["at"]) / (config.half_life_days * 86400)))
            if row
            else 0
        )

    def observe(self, key, message_id, quality, config, now=None):
        if not message_id or message_id in self.seen:
            return
        now = time.time() if now is None else now
        day = datetime.fromtimestamp(now, ZoneInfo(config.timezone)).date().isoformat()
        row = self.rows.get(key, {"day": day, "quality": 0, "offset": 0, "at": now})
        previous = row["quality"] if row["day"] == day else 0
        current = min(config.quality_saturation, previous + int(quality))
        gain = config.day_gain * (math.log1p(current) - math.log1p(previous))
        self.rows[key] = {
            "offset": min(1, self.offset(key, config, now) + gain),
            "at": now,
            "day": day,
            "quality": current,
        }
        self.rows.move_to_end(key)
        self.seen[message_id] = True
        while len(self.rows) > config.max_entries:
            self.rows.popitem(last=False)
        while len(self.seen) > config.seen_messages:
            self.seen.popitem(last=False)
