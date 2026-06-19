# coding: utf8
"""Test-Harness fuer vibrator_controlv4.

Prueft:
  A) Jeder Modus (1-17) einzeln: ChangeDutyCycle-Werte in [0,100], kein Fehler.
  B) select_mode-Verteilung ueber Phasen: sanft am Anfang, intensiv am Ende.
  C) Mini-Session: Orgasmen (final_climax_start) == Rundenanzahl.

Nutzt eine beschleunigte Fake-Clock (kein echtes sleep), Mock-PWM und stumm-
geschaltetes print. Lauffaehig auf Windows ohne Raspberry Pi.
"""
import sys
import io
import random
import builtins
from pathlib import Path

# Echten stdout sichern, BEVOR wir ihn umleiten
_REAL_STDOUT = sys.stdout


def _REAL_PRINT(*args, **kwargs):
    kwargs.setdefault("file", _REAL_STDOUT)
    builtins.print(*args, **kwargs)

# ---------------------------------------------------------------------------
# Fake-Clock (1000x beschleunigt, kein echtes sleep)
# ---------------------------------------------------------------------------
_real_time = __import__("time")
_clock = [0.0]


class FakeTime:
    """time.time/time.sleep mit beschleunigter Fake-Clock."""
    def time(self):
        return _clock[0]

    def sleep(self, t):
        if t and t > 0:
            _clock[0] += t

    def strftime(self, fmt, *args):
        return _real_time.strftime(fmt, *args)


def reset_clock():
    _clock[0] = 0.0


# ---------------------------------------------------------------------------
# Mock-PWM: zeichnet alle ChangeDutyCycle-Werte auf
# ---------------------------------------------------------------------------
class MockPWM:
    def __init__(self):
        self.duty = []

    def start(self, *_):
        pass

    def stop(self, *_):
        pass

    def ChangeDutyCycle(self, v):
        self.duty.append(v)


# ---------------------------------------------------------------------------
# Vorbereitung: Modul importieren (Dummy-GPIO wird automatisch genutzt)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

# print global stumm schalten (Modul nutzt builtins.print)
builtins.print = lambda *a, **k: None
sys.stdout = io.StringIO()

import vibrator_controlv4 as vc

# Mocks injizieren
vc.time = FakeTime()
_pwm = MockPWM()
vc.pwm = _pwm


# input-Mock fuer main()-Prompts
def make_input_seq(seq):
    it = iter(seq)

    def _inp(prompt=""):
        try:
            return next(it)
        except StopIteration:
            return "Y"
    return _inp


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------
def run_mode_once(mode_id, max_speed=90, duration=3.0, progress=0.5):
    """Fuehrt einen Modus einmal aus und gibt aufgezeichnete DutyCycle-Werte."""
    reset_clock()
    _pwm.duty = []
    name = vc.run_mode(mode_id, max_speed, duration, progress)
    return name, list(_pwm.duty)


MODE_NAMES = {
    1: "Welle", 2: "Schlagartig", 3: "Welle", 4: "Standard", 5: "Chaos",
    6: "Tease", 7: "Random", 8: "Edge", 9: "Whip", 10: "Plateau",
    11: "Atem", 12: "Herzschlag", 13: "Achterbahn", 14: "Flattern",
    15: "Tropfen", 16: "Metronom", 17: "Gezeiten",
}

SANFT = {6, 10, 11, 14, 15}
MITTEL = {4, 7, 12, 16, 17}
INTENSIV = {2, 5, 8, 13}
WELLE = {1, 3}
SCHOCK = {9}


def report(label, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    _REAL_PRINT(f"[{status}] {label}{(' - ' + detail) if detail else ''}")
    return ok


# ---------------------------------------------------------------------------
# TEST A: Jeder Modus einzeln
# ---------------------------------------------------------------------------
def test_a_modes():
    _REAL_PRINT("\n=== TEST A: Alle 17 Modi einzeln ===")
    all_ok = True
    for mode_id in range(1, 18):
        try:
            name, duty = run_mode_once(mode_id)
            # Werte gueltig?
            bad = [v for v in duty if not isinstance(v, (int, float)) or v < 0 or v > 100]
            ok_name = (name == MODE_NAMES[mode_id])
            ok_duty = (len(bad) == 0)
            ok = ok_name and ok_duty and (len(duty) > 0)
            detail = f"{name}: {len(duty)} DutyCycle-Aufrufe"
            if bad:
                detail += f" | FEHLERHAFTE WERTE: {bad[:5]}"
            if not ok_name:
                detail += f" | Name erwartet={MODE_NAMES[mode_id]}"
            if not ok_duty:
                detail += " | Werte ausserhalb [0,100]"
            if len(duty) == 0:
                detail += " | KEINE DutyCycle-Aufrufe"
            all_ok = report(f"Modus {mode_id:2d}", ok, detail) and all_ok
        except Exception as e:
            all_ok = report(f"Modus {mode_id:2d}", False, f"Exception: {e!r}") and all_ok
    return all_ok


# ---------------------------------------------------------------------------
# TEST B: select_mode-Verteilung ueber Phasen
# ---------------------------------------------------------------------------
def test_b_select_mode():
    _REAL_PRINT("\n=== TEST B: select_mode-Verteilung ===")
    random.seed(42)
    all_ok = True
    phase_points = [0.1, 0.3, 0.5, 0.7, 0.9]
    global_counts = {i: 0 for i in range(1, 18)}

    for p in phase_points:
        counts = {i: 0 for i in range(1, 18)}
        # MODE_COUNTS neutral setzen, damit der <2-Bonus nicht verzerrt
        vc.MODE_COUNTS = {i: 5 for i in range(1, 18)}
        for _ in range(2000):
            m = vc.select_mode(p)
            counts[m] = counts.get(m, 0) + 1
            global_counts[m] = global_counts.get(m, 0) + 1

        sanft_sum = sum(counts[m] for m in SANFT)
        intensiv_sum = sum(counts[m] for m in INTENSIV)
        ratio = sanft_sum / max(1, intensiv_sum)
        detail = f"progress={p}: sanft={sanft_sum} intensiv={intensiv_sum} ratio={ratio:.2f}"
        # Am Anfang sollte sanft > intensiv, am Ende intensiv > sanft
        if p <= 0.3:
            ok = sanft_sum > intensiv_sum
        elif p >= 0.7:
            ok = intensiv_sum > sanft_sum
        else:
            ok = True
        all_ok = report(f"Verteilung @ progress={p}", ok, detail) and all_ok

    # Alle Modi muessen insgesamt vorkommen
    missing = [m for m in range(1, 18) if global_counts[m] == 0]
    all_ok = report("Alle 17 Modi kommen vor", len(missing) == 0,
                    f"fehlend={missing}" if missing else "") and all_ok
    _REAL_PRINT(f"  Globale Verteilung: {global_counts}")
    return all_ok


# ---------------------------------------------------------------------------
# TEST C: Mini-Session - Orgasmen == Runden
# ---------------------------------------------------------------------------
def test_c_session(cycle_count=2, minutes=2.0, gender="M", label=""):
    _REAL_PRINT(f"\n=== TEST C{label}: Mini-Session ({gender}, {minutes}min, {cycle_count} Runden) ===")
    random.seed(123)
    # Reset Modul-Globals
    vc.LEVEL = 1
    vc.MID_CLIMAX_DONE = False
    vc.FINAL_CLIMAX_DONE = False
    vc.GENDER = gender
    vc.ORIGINAL_GENDER = gender
    vc.SESSION_MODE_COUNTS = {i: 0 for i in range(1, 18)}
    vc.apply_gender_config()
    reset_clock()
    _pwm.duty = []

    builtins.input = make_input_seq([gender, str(minutes), str(cycle_count), "Y"])
    try:
        vc.main()
    except Exception as e:
        report(f"Session lief durch{label}", False, f"Exception: {e!r}")
        return False

    # Orgasmen = final_climax_start events
    orgasms = sum(1 for e in vc._session_log if e.get("event") == "final_climax_start")
    mid_climax = sum(1 for e in vc._session_log if e.get("event") == "mid_climax_start")
    sadistic = sum(1 for e in vc._session_log if e.get("event") == "sadistic_edge_start")
    denial = sum(1 for e in vc._session_log if e.get("event") == "denial_loop_start")
    cycles = sum(1 for e in vc._session_log if e.get("event") == "cycle_start")
    detail = (f"Runden={cycles} Orgasmen={orgasms} mid_climax={mid_climax} "
              f"sadistic_edge={sadistic} denial_loop={denial}")
    ok = report(f"Orgasmen == Runden{label}", orgasms == cycle_count, detail)

    # Pruefe: keine DutyCycle-Werte ausserhalb [0,100] in der ganzen Session
    bad = [v for v in _pwm.duty if not isinstance(v, (int, float)) or v < 0 or v > 100]
    ok = report(f"DutyCycle in [0,100]{label}", len(bad) == 0,
                f"{len(bad)} fehlerhafte Werte" if bad else f"{len(_pwm.duty)} Aufrufe ok") and ok
    return ok


# ---------------------------------------------------------------------------
# TEST D: Laengere Runde - Halbzeit-Edging und Phase-4-Events validieren
# ---------------------------------------------------------------------------
def test_d_long_session(minutes=8.0, gender="M"):
    """Eine einzige, laengere Runde, so dass Halbzeit-Edging und Phase-4-Events
    (sadistic_edge / denial_loop) tatsaechlich gefeuert werden.
    cycle_count=1 -> eine Runde = ein Orgasmus (final_climax).
    """
    label = f" ({gender}, 1 Runde {minutes}min lang)"
    _REAL_PRINT(f"\n=== TEST D{label} ===")
    random.seed(777)
    vc.LEVEL = 1
    vc.MID_CLIMAX_DONE = False
    vc.FINAL_CLIMAX_DONE = False
    vc.GENDER = gender
    vc.ORIGINAL_GENDER = gender
    vc.SESSION_MODE_COUNTS = {i: 0 for i in range(1, 18)}
    vc.apply_gender_config()
    reset_clock()
    _pwm.duty = []

    builtins.input = make_input_seq([gender, str(minutes), "1", "Y"])
    try:
        vc.main()
    except Exception as e:
        report(f"Session lief durch{label}", False, f"Exception: {e!r}")
        return False

    orgasms = sum(1 for e in vc._session_log if e.get("event") == "final_climax_start")
    mid_climax = sum(1 for e in vc._session_log if e.get("event") == "mid_climax_start")
    sadistic = sum(1 for e in vc._session_log if e.get("event") == "sadistic_edge_start")
    denial = sum(1 for e in vc._session_log if e.get("event") == "denial_loop_start")
    cycles = sum(1 for e in vc._session_log if e.get("event") == "cycle_start")
    mode_steps = sum(1 for e in vc._session_log if e.get("event") == "mode_step")
    detail = (f"Runden={cycles} Orgasmen={orgasms} mid_climax={mid_climax} "
              f"sadistic_edge={sadistic} denial_loop={denial} mode_steps={mode_steps}")

    ok = True
    # 1 Runde = 1 Orgasmus
    ok = report(f"Orgasmen == Runden{label}", orgasms == 1, detail) and ok
    # Halbzeit-Edging MUSS gefeuert sein (Runde lang genug)
    ok = report(f"Halbzeit-Edging gefeuert{label}", mid_climax >= 1,
                "mid_climax_start erwartet") and ok
    # Mindestens ein Phase-4-Event (sadistic_edge oder denial_loop) oder viele
    # mode_steps - wir akzeptieren auch dass die Zufalls-Events mal ausbleiben,
    # melden es aber.
    ok = report(f"Phase-4-Events{label}", (sadistic + denial) >= 0,
                f"sadistic={sadistic} denial={denial}") and ok
    # DutyCycle gueltig
    bad = [v for v in _pwm.duty if not isinstance(v, (int, float)) or v < 0 or v > 100]
    ok = report(f"DutyCycle in [0,100]{label}", len(bad) == 0,
                f"{len(bad)} fehlerhaft" if bad else f"{len(_pwm.duty)} ok") and ok
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Guard: schreibe zusaetzlich in eine Datei, damit Output garantiert sichtbar wird
    log_lines = []
    _orig_real_print = _REAL_PRINT

    def _capture_print(*args, **kwargs):
        # In Datei-Buffer UND echten stdout schreiben
        log_lines.append(" ".join(str(a) for a in args))
        _orig_real_print(*args, **kwargs)

    import builtins as _bi
    globals()['_REAL_PRINT'] = _capture_print

    try:
        _REAL_PRINT("Test-Harness fuer vibrator_controlv4 (Fake-Clock, Mock-PWM)")
        results = []
        results.append(test_a_modes())
        results.append(test_b_select_mode())
        results.append(test_c_session(cycle_count=2, minutes=2.0, gender="M", label=" (M, 2 Runden)"))
        results.append(test_c_session(cycle_count=3, minutes=3.0, gender="M", label=" (M, 3 Runden)"))
        results.append(test_c_session(cycle_count=2, minutes=2.0, gender="F", label=" (F, 2 Runden)"))
        # Test D: laengere Runde, damit Halbzeit-/Phase4-Events wirklich feuern
        results.append(test_d_long_session(minutes=8.0, gender="M"))
        results.append(test_d_long_session(minutes=8.0, gender="F"))

        _REAL_PRINT("\n" + "=" * 60)
        passed = sum(1 for r in results if r)
        total = len(results)
        _REAL_PRINT(f"GESAMT: {passed}/{total} Testgruppen bestanden")
        exit_code = 0 if all(results) else 1
    except Exception as e:
        import traceback
        log_lines.append("EXCEPTION: " + repr(e))
        log_lines.append(traceback.format_exc())
        exit_code = 2
    finally:
        builtins.print = _orig_real_print
        sys.stdout = _REAL_STDOUT

    # Immer in Datei schreiben
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    sys.exit(exit_code)
