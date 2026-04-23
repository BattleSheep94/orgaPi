# coding: utf8
"""Tests fuer die Berechnungs-Logik in vibrator_control.py.

Geprueft wird der Plan:
- Die Motor-Laufzeit (duration) steigert sich langsam mit dem Level.
- Die Pause (recovery) reicht IMMER aus, um sich zu beruhigen.
- Die Zeit-begrenzte Variante kuerzt die Pause nie unter den Beruhigungs-Boden.

Laufbar per Python-Standardbibliothek (unittest), damit keine externen
Abhaengigkeiten (pytest etc.) noetig sind.
"""
from __future__ import annotations

import random
import statistics
import unittest

import vibrator_control as vc


SAMPLES = 2000


def _sample(fn, *args, n=SAMPLES):
    durs, recs = [], []
    for _ in range(n):
        _, d, r = fn(*args)
        durs.append(d)
        recs.append(r)
    return durs, recs


class DurationGrowsSlowlyWithLevelTests(unittest.TestCase):
    """Die Motor-Laufzeit soll mit dem Level monoton wachsen, aber gedaempft."""

    def setUp(self):
        random.seed(1234)
        vc.MODUS_STREAK.clear()

    def test_average_duration_monotonically_increases(self):
        levels = [1, 2, 5, 10, 20]
        averages = []
        for lvl in levels:
            durs, _ = _sample(vc.calculate_parameters, lvl, None)
            averages.append(statistics.mean(durs))
        for earlier, later in zip(averages, averages[1:]):
            self.assertLess(earlier, later,
                            f"Duration did not increase: {averages}")

    def test_growth_is_slow_not_explosive(self):
        """Level 20 soll nicht mehr als 5x so lang laufen wie Level 1."""
        d1, _ = _sample(vc.calculate_parameters, 1, None)
        d20, _ = _sample(vc.calculate_parameters, 20, None)
        ratio = statistics.mean(d20) / statistics.mean(d1)
        self.assertLess(ratio, 5.0, f"Growth too aggressive (ratio={ratio:.2f})")
        self.assertGreater(ratio, 1.5, f"No meaningful growth (ratio={ratio:.2f})")


class RecoveryIsAlwaysEnoughTests(unittest.TestCase):
    """Die Pause muss IMMER ausreichen, um sich zu beruhigen."""

    def setUp(self):
        random.seed(1234)
        vc.MODUS_STREAK.clear()

    def test_recovery_never_below_min_calm_recovery(self):
        for lvl in [1, 2, 5, 10, 20, 50]:
            _, recs = _sample(vc.calculate_parameters, lvl, None)
            self.assertGreaterEqual(
                min(recs), vc.MIN_CALM_RECOVERY,
                f"Recovery dropped below floor at level {lvl}: min={min(recs):.1f}",
            )

    def test_recovery_significantly_longer_than_duration(self):
        """Im Mittel soll die Pause mindestens 10x so lang sein wie die Laufzeit."""
        for lvl in [1, 5, 10, 20]:
            durs, recs = _sample(vc.calculate_parameters, lvl, None)
            ratio = statistics.mean(recs) / statistics.mean(durs)
            self.assertGreater(
                ratio, 10.0,
                f"Pause-Verhaeltnis zu gering auf Level {lvl}: {ratio:.1f}x",
            )

    def test_per_sample_recovery_scales_with_duration(self):
        """Fuer jede einzelne Probe muss die Pause mindestens so lang sein wie
        das Minimum aus (MIN_CALM_RECOVERY, RATIO_MIN * duration)."""
        random.seed(99)
        for _ in range(SAMPLES):
            _, d, r = vc.calculate_parameters(5, None)
            expected_min = max(vc.MIN_CALM_RECOVERY, d * vc.RECOVERY_DURATION_RATIO_MIN)
            # Upper recovery cap may shorten the floor on very long durations,
            # allow RECOVERY_UPPER_CAP as the hard ceiling below which we don't
            # require more.
            allowed_min = min(expected_min, vc.RECOVERY_UPPER_CAP)
            self.assertGreaterEqual(
                r + 1e-6, allowed_min,
                f"recovery {r:.1f}s zu kurz fuer Laufzeit {d:.1f}s",
            )


class TimeLimitedCalculationTests(unittest.TestCase):
    """calculate_parameters_with_time darf den Beruhigungs-Boden nicht unterschreiten."""

    def setUp(self):
        random.seed(42)
        vc.MODUS_STREAK.clear()

    def test_recovery_floor_holds_near_end_of_session(self):
        for tl in [600, 300, 180, 120]:
            _, recs = _sample(vc.calculate_parameters_with_time, 5, None, tl)
            self.assertGreaterEqual(
                min(recs), vc.MIN_CALM_RECOVERY,
                f"Recovery fiel unter {vc.MIN_CALM_RECOVERY}s bei time_left={tl}: min={min(recs):.1f}",
            )

    def test_duration_capped_to_time_left(self):
        """Die Laufzeit darf 25% der Restzeit nicht nennenswert uebersteigen."""
        for tl in [60, 120, 300]:
            durs, _ = _sample(vc.calculate_parameters_with_time, 10, None, tl)
            cap = max(3, tl * 0.25)
            self.assertLessEqual(max(durs), cap + 1e-6,
                                 f"Laufzeit ueberschritt Cap bei time_left={tl}")


class StreakBonusKeepsRecoverySafeTests(unittest.TestCase):
    """Streak-Bonus verlaengert die Laufzeit - die Pause muss mitwachsen."""

    def setUp(self):
        random.seed(7)
        vc.MODUS_STREAK.clear()

    def test_recovery_scales_with_extended_duration(self):
        # Streak erzwingen
        vc.MODUS_STREAK["Welle"] = 5
        try:
            violations = 0
            for _ in range(SAMPLES):
                _, d, r = vc.calculate_parameters(5, "Welle")
                floor = min(
                    max(vc.MIN_CALM_RECOVERY, d * vc.RECOVERY_DURATION_RATIO_MIN),
                    vc.RECOVERY_UPPER_CAP,
                )
                if r + 1e-6 < floor:
                    violations += 1
            self.assertEqual(
                violations, 0,
                f"{violations} Proben mit zu kurzer Pause trotz Streak-Bonus",
            )
        finally:
            vc.MODUS_STREAK.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
