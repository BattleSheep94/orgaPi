# coding: utf8
# Programm zur Steuerung eines Vibrators mit PWM auf einem Raspberry Pi mit PCB-Adapter
# Nutzt GPIO 21 (BCM, PCB-Adapter: primÃ¤re Steuerung) fÃ¼r alle Modi
# UnterstÃ¼tzt Welle (generisch)-, Schlagartig-, Standard-, Chaos-, Tease-, Random-, Edge-, Whip- und Plateau-Modi sowie Make-Cum und Extreme-Torture
# Whip-Modus: LevelabhÃ¤ngige Hiebe, 100% IntensitÃ¤t, Pausen 2â€“8 s, Impulsdauer 0.2â€“0.6 s
# Korrektur: SyntaxError in print-Anweisungen, f-Strings ohne deutsche Punkte

# Falls das Skript auf einem Nicht-Raspberry-System ausgefÃ¼hrt wird (z.B. Windows),
# wird ein Dummy-GPIO verwendet, damit die Logik testbar bleibt.
try:
    import RPi.GPIO as GPIO
    IS_SIMULATED = False
except (ImportError, RuntimeError):
    class _DummyPWM:
        def __init__(self, *_, **__):
            pass

        def start(self, *_):
            pass

        def ChangeDutyCycle(self, *_):
            pass

        def stop(self):
            pass

    class _DummyGPIO:
        BCM = "BCM"
        OUT = "OUT"

        def setmode(self, *_, **__):
            pass

        def setwarnings(self, *_, **__):
            pass

        def setup(self, *_, **__):
            pass

        def cleanup(self):
            pass

        def PWM(self, *_, **__):
            return _DummyPWM()

    GPIO = _DummyGPIO()
    IS_SIMULATED = True
import time
import random
import sys

# GPIO-Setup (BCM-Modus fÃ¼r Pin-Nummerierung)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Pin fÃ¼r PWM auf dem PCB-Adapter
PRIMARY_PWM_PIN = 21  # GPIO 21 (BCM, PCB-Adapter: primÃ¤re Steuerung)
GPIO.setup(PRIMARY_PWM_PIN, GPIO.OUT)

# PWM mit 50 Hz initialisieren
pwm = GPIO.PWM(PRIMARY_PWM_PIN, 50)
pwm.start(0)

# Globale Variablen
LEVEL = 1  # Aktuelles Level, beeinflusst IntensitÃ¤t
SESSION_DURATION = 10800  # Wird bei Programmstart durch Benutzereingabe Ã¼berschrieben
BASE_PROBABILITIES = {
    "make_cum": 0.10,
    "extreme_torture": 0.015,
    "level_reset": 0.05,
    "fake_phase": 0.05,
    "random_delay": 0.05,
}
EVENT_PROB = BASE_PROBABILITIES.copy()
MODE_COUNTS = {i: 0 for i in range(1, 11)}  # Jeder Modus soll mindestens 2x vorkommen
MODUS_STREAK = {}  # Verfolgt, wie oft ein Modus hintereinander ausgewÃ¤hlt wurde
MID_CLIMAX_DONE = False  # Make-Cum zur Halbzeit
FINAL_CLIMAX_DONE = False  # Abschluss-Sequenz am Ende
GENDER = "M"  # "M" = Mann, "F" = Frau, wird bei Programmstart gesetzt
DURATION_MULTIPLIER = 1.0  # Wird durch apply_gender_config angepasst

def clamp_prob(value, upper=0.7):
    """BeschrÃ¤nkt Wahrscheinlichkeiten auf einen sinnvollen Bereich."""
    return max(0.0, min(value, upper))


def rescale_probabilities():
    """Skaliert alle Wahrscheinlichkeiten passend zur tatsÃ¤chlichen Sitzungsdauer."""
    # Keine Skalierung mehr nÃ¶tig - BASE_SESSION wurde entfernt
    for key, base in BASE_PROBABILITIES.items():
        EVENT_PROB[key] = clamp_prob(base)

def test_vibrator():
    """Testet den Vibrator fÃ¼r 2 Sekunden auf 50% IntensitÃ¤t"""
    print("[Test] Vibrator-Test gestartet...")
    pwm.ChangeDutyCycle(80)
    time.sleep(2)
    pwm.ChangeDutyCycle(0)
    print("[Test] Vibrator-Test beendet.")

def fake_phase():
    """TÃ¤uscht den Start einer neuen Phase vor (2 Sekunden wechselnde IntensitÃ¤t)"""
    print("[Fake Phase] Achtung, neue Phase beginnt... oder doch nicht?")
    for i in range(0, 80, 5):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.05)
    for i in range(80, 0, -5):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.05)
    pwm.ChangeDutyCycle(0)
    time.sleep(0.5)

def random_delay():
    """VerzÃ¶gert Modusstart ohne Meldungen (5â€“20 Sekunden)"""
    delay_time = random.uniform(5, 20)
    time.sleep(delay_time)

def wave_mode(max_speed, duration):
    """Modus: Welle - Generische Wellen mit zufÃ¤lligen LÃ¤ngen und Geschwindigkeiten.

    Jeder Aufruf wÃ¤hlt zufÃ¤llig Anstiegsgeschwindigkeit und Peak-Variationen.
    Innerhalb der Dauer werden eine oder mehrere Wellen erzeugt.
    """
    step_time = random.uniform(0.01, 0.06)
    variant = "Schnell" if step_time < 0.025 else ("Mittel" if step_time < 0.04 else "Langsam")
    print(f"[Welle/{variant}] Max: {max_speed}%, Dauer: {duration:.1f}s, Step: {step_time:.3f}s")
    start = time.time()
    while (time.time() - start) < duration:
        peak = random.randint(int(max_speed * 0.6), max_speed)
        for i in range(0, peak, 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(step_time)
            if (time.time() - start) >= duration:
                break
        hold = random.uniform(0.2, 1.5)
        remaining = duration - (time.time() - start)
        if remaining > 0:
            pwm.ChangeDutyCycle(peak)
            time.sleep(min(hold, remaining))
        for i in range(peak, -1, -1):
            pwm.ChangeDutyCycle(i)
            time.sleep(step_time)
            if (time.time() - start) >= duration:
                break
    pwm.ChangeDutyCycle(0)

def pulse_mode(max_speed, duration):
    """Modus: Schlagartig - Schnelle Pulse mit kurzen Pausen"""
    print(f"[Schlagartig] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    while elapsed < duration:
        for i in range(0, max_speed, 5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.0035)
        for i in range(max_speed, -1, -5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.0035)
        elapsed += 0.5
        time.sleep(0.1)
    pwm.ChangeDutyCycle(0)

def standard_mode(max_speed, duration):
    """Modus: Standard - Konstante Geschwindigkeit fÃ¼r die angegebene Dauer"""
    print(f"[Standard] Konstante Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    pwm.ChangeDutyCycle(max_speed)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)

def chaos_mode(max_speed, duration):
    """Modus: Chaos - ZufÃ¤llige IntensitÃ¤tsspitzen mit kurzen Pausen"""
    print(f"[Chaos] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    while elapsed < duration:
        intensity = random.randint(50, max_speed)
        pwm.ChangeDutyCycle(intensity)
        step_time = random.uniform(0.1, 0.5)
        time.sleep(step_time)
        elapsed += step_time
        if random.random() < 0.2:
            pwm.ChangeDutyCycle(0)
            pause_time = random.uniform(0.05, 0.2)
            time.sleep(pause_time)
            elapsed += pause_time
    pwm.ChangeDutyCycle(0)

def tease_mode(max_speed, duration):
    """Modus: Tease - Langsames Ansteigen mit Abbruch vor variablem Maximum"""
    print(f"[Tease] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    while elapsed < duration - 0.5:
        tease_max = random.randint(int(max_speed * 0.5), int(max_speed * 0.9))
        for i in range(0, tease_max, 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.05)
            elapsed += 0.05
            if elapsed >= duration - 0.5:
                break
        pwm.ChangeDutyCycle(0)
        time.sleep(0.2)
        elapsed += 0.2
    pwm.ChangeDutyCycle(max_speed)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)

def edge_mode(max_speed, duration):
    """Modus: Edge - Schnelles Ansteigen bis knapp unter Maximum, Abbruch, Wiederholung"""
    print(f"[Edge] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    num_cycles = random.randint(3, 5)
    cycle_time = duration / num_cycles
    while elapsed < duration - 1:
        edge_max = 100
        for i in range(0, edge_max, 5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.025)
        time.sleep(0.3)
        for i in range(edge_max, 0, -5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.025)
        time.sleep(0.2)
        elapsed += (0.5 + 0.3 + 0.5 + 0.2)
    print("[Edge] So nah... und doch so fern!")
    pwm.ChangeDutyCycle(0)
    time.sleep(1)
    pwm.ChangeDutyCycle(0)

def whip_mode(max_speed, duration):
    """Modus: Whip - Simuliert Peitschenhiebe mit levelabhÃ¤ngigen Impulsen bei 100%"""
    print(f"[Whip] Dauer: {duration:.1f}s")
    num_whips = random.randint(3 + (LEVEL - 1) // 3, min(8 + (LEVEL - 1) // 2, 20))  # LevelabhÃ¤ngige Hiebe
    elapsed = 0
    for _ in range(num_whips):
        if elapsed >= duration:
            break
        intensity = 100  # Immer 100% IntensitÃ¤t
        whip_duration = random.uniform(0.2, 0.6)  # Kurzer Impuls (0.2â€“0.6 s)
        print("[Whip] SpÃ¼r den Hieb!")
        pwm.ChangeDutyCycle(intensity)
        time.sleep(whip_duration)
        pwm.ChangeDutyCycle(0)
        pause_time = random.uniform(2, 8)  # Pause zwischen Hieben
        time.sleep(pause_time)
        elapsed += whip_duration + pause_time
    pwm.ChangeDutyCycle(0)

def plateau_mode(max_speed, duration, progress):
    """Modus: Plateau - Moderate Dauerstimulation, steigert sich mit Session-Fortschritt.
    Am Anfang schwach (20-40%), spÃ¤ter intensiver (40-60%)."""
    low = int(20 + 20 * progress)   # 20% -> 40%
    high = int(40 + 20 * progress)  # 40% -> 60%
    plateau_intensity = random.randint(low, max(low, min(high, max_speed)))
    print(f"[Plateau] IntensitÃ¤t: {plateau_intensity}%, Dauer: {duration:.1f}s (Fortschritt: {progress:.0%})")
    # Sanft hochfahren
    for i in range(0, plateau_intensity, 1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.03)
    # Plateau halten mit leichten Schwankungen
    elapsed = 0
    while elapsed < duration:
        variation = random.randint(-3, 3)
        current = max(0, min(100, plateau_intensity + variation))
        pwm.ChangeDutyCycle(current)
        step = random.uniform(0.5, 2.0)
        time.sleep(step)
        elapsed += step
    # Sanft runterfahren
    for i in range(plateau_intensity, -1, -1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.03)
    pwm.ChangeDutyCycle(0)
    
def denial_loop_mode(rounds=None, start_peak=85):
    """Denial Loop: Je höher der Peak, desto kürzer das Plateau.
    Unberechenbar durch zufälligen Peak pro Runde — auch 100% möglich, aber sehr kurz.
    """
    if rounds is None:
        rounds = random.randint(2, 4) if GENDER == "F" else random.randint(3, 5)

    pause_min = 15 if GENDER == "F" else 30
    pause_max = 30 if GENDER == "F" else 60

    print(f"[Denial Loop] {rounds} Runden, Start-Peak {start_peak}%")

    for i in range(rounds):
        # Peak: steigt pro Runde, kann auch 100% erreichen
        peak = min(100, start_peak + i * random.randint(2, 5))

        # Je höher der Peak, desto kürzer das Plateau — inverses Verhältnis
        # 85% -> ~7s, 90% -> ~5.5s, 95% -> ~4s, 100% -> ~2.5s
        plateau_base = max(1.0, 7.0 - (peak - 85) * 0.3)
        plateau_variation = random.uniform(-0.5, 1.5)
        plateau_time = max(1.0, plateau_base + plateau_variation)

        print(f"[Denial Loop] Runde {i + 1}/{rounds} — Peak {peak}%, Plateau {plateau_time:.1f}s")

        # Hochfahren — bei höherem Peak schneller, damit die Gesamtzeit nicht zu lang wird
        step_time = max(0.008, 0.04 - (peak - 85) * 0.001)
        for val in range(0, peak, 1):
            pwm.ChangeDutyCycle(val)
            time.sleep(step_time)

        # Am Limit halten
        pwm.ChangeDutyCycle(peak)
        time.sleep(plateau_time)

        # Abrupter Abbruch
        for val in range(peak, -1, -5):
            pwm.ChangeDutyCycle(val)
            time.sleep(0.01)
        pwm.ChangeDutyCycle(0)

        # Pause wird mit jeder Runde etwas kürzer — Anspannung steigt
        shrink = i * (1.5 if GENDER == "F" else 3)
        pause = random.uniform(
            max(pause_min - shrink, pause_min * 0.5),
            max(pause_max - shrink, pause_min)
        )
        print(f"[Denial Loop] Abbruch! Erholung {pause:.0f}s...")
        time.sleep(pause)

    pwm.ChangeDutyCycle(0)
    print("[Denial Loop] Verweigerung abgeschlossen.")

def random_mode(max_speed, duration):
    """Modus: Random - ZufÃ¤llige Kombination von Elementen anderer Modi"""
    print(f"[Random] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    while elapsed < duration:
        sub_mode = random.choice([wave_mode, pulse_mode, chaos_mode, whip_mode])
        sub_duration = random.uniform(1, 3)
        sub_mode(max_speed, sub_duration)
        elapsed += sub_duration
    pwm.ChangeDutyCycle(0)

def make_cum(duration_override=None, reason=None):
    """Make-Cum: Dynamische intensive Phase bei 100% mit Wellen, Chaos und Fake-Enden."""
    if duration_override is not None:
        target = duration_override
    elif GENDER == "F":
        target = random.uniform(180, 800)
    else:
        target = random.uniform(60, 300)

    label = f" [{reason}]" if reason else ""
    print(f"[Make-Cum{label}] Intensive Phase: {target:.0f}s!")
    log_event("make_cum_start", duration_seconds=round(target, 2),
              reason=reason or "random", gender=GENDER)

    start = time.time()
    pwm.ChangeDutyCycle(100)
    while (time.time() - start) < target:
        pattern = random.random()
        if pattern < 0.25:
            step_time = random.uniform(0.01, 0.03)
            low = random.randint(90, 100)
            for i in range(100, low - 1, -1):
                pwm.ChangeDutyCycle(i)
                time.sleep(step_time)
            time.sleep(random.uniform(0.3, 1.0))
            for i in range(low, 101):
                pwm.ChangeDutyCycle(i)
                time.sleep(step_time)
        elif pattern < 0.45:
            for _ in range(random.randint(4, 10)):
                intensity = random.randint(90, 100)
                pwm.ChangeDutyCycle(intensity)
                time.sleep(random.uniform(0.1, 0.5))
            pwm.ChangeDutyCycle(100)
        elif pattern < 0.55:
            print(f"[Make-Cum{label}] Ende... oder doch nicht!")
            for i in range(100, -1, -5):
                pwm.ChangeDutyCycle(i)
                time.sleep(0.02)
            time.sleep(random.uniform(5.0, 30.0))
            pwm.ChangeDutyCycle(100)
        else:
            pwm.ChangeDutyCycle(100)
            time.sleep(random.uniform(10, 60))

    print(f"[Make-Cum{label}] Beendet nach {(time.time()-start):.0f}s.")
    pwm.ChangeDutyCycle(0)
    log_event("make_cum_end", duration_seconds=round(time.time() - start, 2), gender=GENDER)

def extreme_torture(duration_override=None, reason=None):
    """Extreme-Torture: Motor auf 100%. Dauer geschlechtsabhängig mit Variation."""
    if duration_override is not None:
        duration = duration_override
    elif GENDER == "F":
        duration = random.uniform(180, 800)
    else:
        duration = random.uniform(45, 180)

    label = f" [{reason}]" if reason else ""
    if duration >= 60:
        print(f"[Extreme Torture{label}] Motor auf 100% für {duration/60:.1f} Minuten!")
    else:
        print(f"[Extreme Torture{label}] Motor auf 100% für {duration:.0f} Sekunden!")

    log_event("extreme_torture_start", duration_seconds=round(duration, 2),
              reason=reason or "random", gender=GENDER)
    pwm.ChangeDutyCycle(100)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)
    log_event("extreme_torture_end", duration_seconds=round(duration, 2), gender=GENDER)

def _recovery_massage(recovery_time):
    """Sanfte Massage-Erholung: langsame Wellen bei 20-50% statt Stille."""
    print(f"[Massage] Sanfte Erholung fÃ¼r {recovery_time:.0f}s")
    start = time.time()
    while (time.time() - start) < recovery_time:
        low = random.randint(20, 30)
        high = random.randint(35, 50)
        step_time = random.uniform(0.03, 0.06)
        for i in range(low, high + 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(step_time)
            if (time.time() - start) >= recovery_time:
                break
        hold = random.uniform(1.0, 4.0)
        remaining = recovery_time - (time.time() - start)
        if remaining > 0:
            time.sleep(min(hold, remaining))
        for i in range(high, low - 1, -1):
            pwm.ChangeDutyCycle(i)
            time.sleep(step_time)
            if (time.time() - start) >= recovery_time:
                break
        # Gelegentlicher Ãœberraschungsimpuls (8%)
        if random.random() < 0.08:
            pwm.ChangeDutyCycle(100)
            time.sleep(random.uniform(0.2, 0.5))
            pwm.ChangeDutyCycle(high)
    pwm.ChangeDutyCycle(0)

def recovery_with_pulses(recovery_time):
    """Erholungsphase mit verteilten Burst-Impulsen bei 100%."""
    blocks = 3 if GENDER == "F" else 2
    bursts_per_block = [random.randint(1, 4) for _ in range(blocks)]
    total_bursts = sum(bursts_per_block)
    base_interval = recovery_time / (total_bursts + 1)
    long_burst_prob = 0.10

    for block_bursts in bursts_per_block:
        for _ in range(block_bursts):
            wait_time = max(2.0, base_interval + random.uniform(-10.0, 10.0))
            time.sleep(wait_time)
            pwm.ChangeDutyCycle(100)
            if random.random() < long_burst_prob:
                time.sleep(2.5)
            else:
                time.sleep(1.0)
            pwm.ChangeDutyCycle(0)

        time.sleep(max(2.0, base_interval + random.uniform(-10.0, 10.0)))


def do_recovery(recovery_time):
    """Wählt Erholungsart: Massage oder Impuls-basiert."""
    massage_chance = 0.6 if GENDER == "F" else 0.4
    if random.random() < massage_chance:
        log_event("recovery_start", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        _recovery_massage(recovery_time)
        log_event("recovery_end", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
    else:
        log_event("recovery_start", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        recovery_with_pulses(recovery_time)
        log_event("recovery_end", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)


MIN_CALM_RECOVERY = 30
RECOVERY_DURATION_RATIO_MIN = 10
RECOVERY_DURATION_RATIO_MAX = 20
RECOVERY_UPPER_CAP = 200


def apply_gender_config():
    """Setzt geschlechtsabhängige Parameter basierend auf GENDER."""
    global MIN_CALM_RECOVERY, RECOVERY_DURATION_RATIO_MIN, RECOVERY_DURATION_RATIO_MAX
    global RECOVERY_UPPER_CAP, DURATION_MULTIPLIER

    if GENDER == "F":
        MIN_CALM_RECOVERY = 15
        RECOVERY_DURATION_RATIO_MIN = 3
        RECOVERY_DURATION_RATIO_MAX = 8
        RECOVERY_UPPER_CAP = 120
        DURATION_MULTIPLIER = 4.5
    else:  # "M"
        MIN_CALM_RECOVERY = 30
        RECOVERY_DURATION_RATIO_MIN = 10
        RECOVERY_DURATION_RATIO_MAX = 20
        RECOVERY_UPPER_CAP = 200
        DURATION_MULTIPLIER = 1.0
def do_recovery(recovery_time):
    """WÃ¤hlt Erholungsart: Massage oder Impuls-basiert."""
    massage_chance = 0.6 if GENDER == "F" else 0.4
    if random.random() < massage_chance:
        log_event("recovery_start", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        _recovery_massage(recovery_time)
        log_event("recovery_end", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
    else:
        log_event("recovery_start", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        recovery_with_pulses(recovery_time)
        log_event("recovery_end", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)

# Mindestpause, damit sich der KÃ¶rper zuverlÃ¤ssig beruhigen kann,
# auch wenn nur sehr kurz gelaufen wurde oder die Sitzung fast vorbei ist.
# Standardwerte fÃ¼r Mann â€“ werden durch apply_gender_config() ggf. Ã¼berschrieben.
MIN_CALM_RECOVERY = 30
# VerhÃ¤ltnis Pause : Laufzeit.
RECOVERY_DURATION_RATIO_MIN = 10
RECOVERY_DURATION_RATIO_MAX = 20
RECOVERY_UPPER_CAP = 200


def apply_gender_config():
    """Setzt geschlechtsabhÃ¤ngige Parameter basierend auf GENDER."""
    global MIN_CALM_RECOVERY, RECOVERY_DURATION_RATIO_MIN, RECOVERY_DURATION_RATIO_MAX
    global RECOVERY_UPPER_CAP, DURATION_MULTIPLIER
    if GENDER == "F":
        MIN_CALM_RECOVERY = 15
        RECOVERY_DURATION_RATIO_MIN = 3
        RECOVERY_DURATION_RATIO_MAX = 8
        RECOVERY_UPPER_CAP = 120
        DURATION_MULTIPLIER = 4.5
    else:  # "M"
        MIN_CALM_RECOVERY = 30
        RECOVERY_DURATION_RATIO_MIN = 10
        RECOVERY_DURATION_RATIO_MAX = 20
        RECOVERY_UPPER_CAP = 200
        DURATION_MULTIPLIER = 1.0


def level_recovery_factor(level):
    """Level-Faktor fÃ¼r Recovery: hÃ¶heres Level -> kÃ¼rzere Erholung.

    Level 1 -> 1.0, Level 10 -> 0.775, Level 20 -> 0.525, min 0.5.
    """
    return max(0.5, 1.0 - (level - 1) * 0.025)


def _recovery_for_duration(duration, level):
    """Leitet eine Erholungspause aus der tatsÃ¤chlichen Motor-Laufzeit ab.

    Recovery sinkt mit steigendem Level (level_recovery_factor). Gewichtete
    Verteilung bevorzugt kurze Pausen â€“ lange Pausen sind mÃ¶glich aber
    unwahrscheinlicher.
    """
    lf = level_recovery_factor(level)

    floor = MIN_CALM_RECOVERY * lf
    ratio_min = RECOVERY_DURATION_RATIO_MIN * lf
    ratio_max = RECOVERY_DURATION_RATIO_MAX * lf
    cap = RECOVERY_UPPER_CAP * lf

    min_recovery = max(floor, duration * ratio_min)
    max_recovery = min(max(min_recovery + 20, duration * ratio_max), cap)
    max_recovery = max(max_recovery, min_recovery + 5)  # Mindest-Range

    # Gewichtete Verteilung: kurze Pausen wahrscheinlicher als lange
    raw = random.random() ** 1.5
    return min_recovery + raw * (max_recovery - min_recovery)


def calculate_parameters(level, streak_modus):
    """Berechnet Zufallsparameter basierend auf dem aktuellen Level und Streak.

    Plan: Die Motor-Laufzeit steigert sich LANGSAM mit dem Level (gedÃ¤mpfter
    Anstieg via sqrt), wÃ¤hrend die Erholungspause immer lang genug bleibt, um
    sich wirklich zu beruhigen - auch nach Streak-/Variation-VerlÃ¤ngerungen.
    """
    speeds = list(range(88, 101))
    weights = [1 + (i / 20) * (level - 1) / 5 for i in range(len(speeds))]
    max_speed = random.choices(speeds, weights=weights, k=1)[0]

    # GedÃ¤mpfter Anstieg: am Anfang schnell spÃ¼rbar, spÃ¤ter nur noch langsam.
    # Level 1 -> 0, Level 5 -> ~3, Level 10 -> 4.5, Level 20 -> ~6.5
    level_boost = max(0.0, (level - 1)) ** 0.5 * 1.5
    min_duration = 1 + level_boost * 0.5
    max_duration = 10 + level_boost * 1.2
    duration = random.uniform(min_duration, max_duration) * DURATION_MULTIPLIER

    if random.random() < 0.05:
        duration *= 1.5
        max_speed = min(100, max_speed + 10)
        print(f"[Variation] Modusvariante: Dauer {duration:.1f}s, IntensitÃ¤t {max_speed}%")

    if MODUS_STREAK.get(streak_modus, 0) >= 3:
        if random.random() < 0.5:
            max_speed = min(100, max_speed + 10)
            print(f"[Streak] IntensitÃ¤t erhÃ¶ht auf {max_speed}%")
        else:
            duration *= 1.5
            print(f"[Streak] Dauer erhÃ¶ht auf {duration:.1f}s")

    # Erholung wird erst NACH allen Dauer-Modifikationen berechnet, damit eine
    # verlÃ¤ngerte Motorphase auch eine entsprechend lÃ¤ngere Pause nach sich zieht.
    recovery = _recovery_for_duration(duration, level)

    return max_speed, duration, recovery


def calculate_parameters_with_time(level, streak_modus, time_left):
    """Wie calculate_parameters, aber begrenzt Dauer/Erholung an verbleibende Zeit.

    Wichtig: Die Erholung wird NIE unter MIN_CALM_RECOVERY gekÃ¼rzt, damit die
    Pause auch am Sitzungsende noch zum Beruhigen ausreicht.
    """
    max_speed, duration, recovery = calculate_parameters(level, streak_modus)
    # Laufzeit an Restzeit anpassen (min. 3s, damit ein Modus Ã¼berhaupt Sinn ergibt).
    duration = min(duration, max(3, time_left * 0.25))
    # Erholung an Restzeit anpassen, aber nie unter den level-skalierten Boden.
    lf = level_recovery_factor(level)
    recovery = min(recovery, max(MIN_CALM_RECOVERY * lf, time_left * 0.4))
    return max_speed, duration, recovery


def mid_session_climax():
    """Make-Cum zur Halbzeit der Session."""
    global MID_CLIMAX_DONE
    if MID_CLIMAX_DONE:
        return
    MID_CLIMAX_DONE = True
    print("\n=== HALBZEIT - HÃ–HEPUNKT ===")
    log_event("mid_climax_start", gender=GENDER)
    make_cum(reason="mid_session")
    if GENDER == "F":
        pause = random.uniform(20, 45)  # KÃ¼rzere Erholung fÃ¼r Frau
    else:
        pause = random.uniform(60, 120)  # 1-2 Minuten Erholung fÃ¼r Mann
    print(f"[Halbzeit] Erholung fÃ¼r {pause:.0f}s.")
    log_event("mid_climax_pause", pause_seconds=round(pause, 2), gender=GENDER)
    pwm.ChangeDutyCycle(0)
    time.sleep(pause)
    log_event("mid_climax_end", pause_seconds=round(pause, 2), gender=GENDER)


def select_mode(progress):
    """WÃ¤hlt einen Modus basierend auf Session-Fortschritt (0.0 = Anfang, 1.0 = Ende).
    
    Am Anfang werden sanfte Modi bevorzugt, gegen Ende intensive Modi.
    Welle (1, 3) hat in allen Phasen konstantes Gewicht.
    Modi-Kategorien:
    - Welle (alle Phasen): 1=Welle, 3=Welle
    - Sanft (Anfang): 6=Tease, 9=Whip, 10=Plateau
    - Mittel: 4=Standard, 7=Random
    - Intensiv (Ende): 2=Schlagartig, 5=Chaos, 8=Edge
    """
    welle = [1, 3]           # Welle (generisch, alle Phasen)
    sanft = [6, 9, 10]       # Tease, Whip, Plateau
    mittel = [4, 7]          # Standard, Random
    intensiv = [2, 5, 8]     # Schlagartig, Chaos, Edge
    
    # Welle hat konstantes Gewicht Ã¼ber alle Phasen
    welle_weight = 2.5
    sanft_weight = max(0.5, 5 - 4.5 * progress)
    mittel_weight = 2
    intensiv_weight = max(0.5, 0.5 + 4.5 * progress)
    
    pool = list(MODE_COUNTS.keys())
    weights = []
    for m in pool:
        if m in welle:
            base_weight = welle_weight
        elif m in sanft:
            base_weight = sanft_weight
        elif m in mittel:
            base_weight = mittel_weight
        else:
            base_weight = intensiv_weight
        
        # Bonus fÃ¼r Modi die noch nicht 2x vorkamen
        count = MODE_COUNTS.get(m, 0)
        if count < 2:
            base_weight *= 1.5
        weights.append(base_weight)
    
    return random.choices(pool, weights=weights, k=1)[0]

def should_trigger_final_climax(time_left, cycle_duration):
    """Chance auf Final Climax steigt gegen Rundenende.
    In den letzten 15 Sekunden ist er garantiert.
    Ohne FINAL_CLIMAX_DONE-Sperre: kann mehrfach feuern.
    """
    if time_left > 180:
        return False

    if time_left <= 15:
        return True

    window = 180.0
    progress_to_end = max(0.0, min(1.0, (window - time_left) / window))
    chance = 0.05 + progress_to_end * 0.90
    return random.random() < chance

def final_climax_sequence():
    """Abschluss-Sequenz: Make-Cum oder Extreme-Torture.
    Kein FINAL_CLIMAX_DONE-Guard -> kann in einer Runde mehrfach ausgeführt werden.
    Läuft immer vollständig durch, auch wenn sie überzieht.
    """
    global FINAL_CLIMAX_DONE
    FINAL_CLIMAX_DONE = True  # nur für Logging/reset_run_state relevant

    print("\n=== FINALE - HÖHEPUNKT ===")

    switch_prob = 0.4 if SESSION_CYCLE_COUNT >= 2 else 0.2
    climax_gender = "F" if random.random() < switch_prob else GENDER

    if climax_gender == "F" and GENDER != "F":
        print(f"[Finale] {switch_prob:.0%}-Switch aktiv: Frauen-Profil.")

    log_event("final_climax_start", session_gender=GENDER, climax_gender=climax_gender)

    roll = random.random()
    if roll < 0.3:
        if climax_gender == "F":
            make_cum(random.uniform(400, 800), reason="final_combined")
            extreme_torture(random.uniform(400, 1000), reason="final_combined")
        else:
            make_cum(random.uniform(150, 500), reason="final_combined")
            extreme_torture(random.uniform(150, 400), reason="final_combined")
    elif roll < 0.75:
        if climax_gender == "F":
            make_cum(random.uniform(400, 1000), reason="final_make_cum")
        else:
            make_cum(random.uniform(150, 500), reason="final_make_cum")
    else:
        if climax_gender == "F":
            extreme_torture(random.uniform(400, 1200), reason="final_extreme_torture")
        else:
            extreme_torture(random.uniform(150, 400), reason="final_extreme_torture")

    log_event("final_climax_end", session_gender=GENDER, climax_gender=climax_gender)

def prompt_gender():
    """Fragt das Geschlecht ab und gibt 'M' oder 'F' zurÃ¼ck."""
    while True:
        raw = input("Geschlecht wÃ¤hlen \u2013 Mann (M) oder Frau (F): ").strip().upper()
        if raw in ("M", "F"):
            return raw
        print("UngÃ¼ltige Eingabe. Bitte M oder F eingeben.")

def prompt_session_duration_minutes():
    """Fragt die Sitzungsdauer ab und gibt Sekunden zurÃ¼ck."""
    while True:
        try:
            raw = input("Bitte Sitzungsdauer in Minuten eingeben (z.B. 90): ").strip().replace(",", ".")
            minutes = float(raw)
            if minutes <= 0:
                raise ValueError
            return minutes * 60
        except ValueError:
            print("UngÃ¼ltige Eingabe. Bitte eine Zahl grÃ¶ÃŸer 0 angeben.")

def prompt_cycle_count():
    """Fragt die Anzahl kompletter DurchlÃ¤ufe (1 bis 5) ab."""
    while True:
        raw = input("Wie viele DurchlÃ¤ufe in der Zeit? (1-5): ").strip()
        if raw in ("1", "2", "3", "4", "5"):
            return int(raw)
        print("UngÃ¼ltige Eingabe. Bitte 1 bis 5 eingeben.")

def reset_run_state():
    """Setzt den Zustandsautomaten fÃ¼r einen neuen Durchlauf zurÃ¼ck."""
    global LEVEL, MODE_COUNTS, MODUS_STREAK, MID_CLIMAX_DONE, FINAL_CLIMAX_DONE
    LEVEL = 1
    MODE_COUNTS = {i: 0 for i in range(1, 11)}
    MODUS_STREAK = {}
    MID_CLIMAX_DONE = False
    FINAL_CLIMAX_DONE = False

def main():
    """Hauptprogramm"""
    global LEVEL, MODUS_STREAK, SESSION_DURATION, MID_CLIMAX_DONE, FINAL_CLIMAX_DONE, GENDER, SESSION_CYCLE_COUNT
    test_vibrator()
    GENDER = prompt_gender()
    apply_gender_config()
    print(f"[Konfiguration] Geschlecht: {'Frau' if GENDER == 'F' else 'Mann'}")
    SESSION_DURATION = prompt_session_duration_minutes()
    cycle_count = prompt_cycle_count()
    SESSION_CYCLE_COUNT = cycle_count
    rescale_probabilities()

    print("Anwendung starten? (Y/N)")
    start = input().strip().upper()
    if start not in ["Y", "J"]:
        print("Anwendung nicht gestartet.")
        sys.exit(0)

    init_session_log()
    log_event(
        "session_start",
        gender=GENDER,
        session_duration_seconds=SESSION_DURATION,
        cycle_count=cycle_count,
        cycle_duration_seconds=round(SESSION_DURATION / cycle_count, 2),
        duration_multiplier=DURATION_MULTIPLIER,
        event_probabilities=dict(EVENT_PROB),
    )

    try:
        cycle_duration = SESSION_DURATION / cycle_count
        for cycle_idx in range(1, cycle_count + 1):
            reset_run_state()
            print(f"\n=== Durchlauf {cycle_idx}/{cycle_count} gestartet ===")
            start_time = time.time()
            last_modus = None
            cycle_peak_level = LEVEL
            log_event(
                "cycle_start",
                cycle=cycle_idx,
                total_cycles=cycle_count,
                cycle_duration_seconds=round(cycle_duration, 2),
                level=LEVEL,
            )

            while True:
                elapsed = time.time() - start_time
                time_left = cycle_duration - elapsed
                level_before = LEVEL

                # Finale Sequenz in den letzten 2 Minuten
                # NEU — kein break, kein DONE-Guard, Mehrfachstart möglich
                if should_trigger_final_climax(time_left, cycle_duration):
                final_climax_sequence()
                # kein break -> Loop läuft weiter, weitere Trigger möglich

                # Make-Cum zur Halbzeit
                if not MID_CLIMAX_DONE and elapsed >= cycle_duration / 2:
                    mid_session_climax()
                    elapsed = time.time() - start_time
                    time_left = cycle_duration - elapsed

                # Fortschritt berechnen (0.0 = Anfang, 1.0 = Ende)
                progress = min(1.0, elapsed / cycle_duration)

                if progress >= 0.6 and random.random() < EVENT_PROB["extreme_torture"]:
                    extreme_torture()
                    continue

                print(f"\n=== Level {LEVEL:.1f} | Rest: {time_left/60:.1f} min ===")
                if random.random() < EVENT_PROB["fake_phase"]:
                    fake_phase()
                if random.random() < EVENT_PROB["random_delay"]:
                    random_delay()

                max_speed, duration, recovery = calculate_parameters_with_time(LEVEL, last_modus, time_left)

                mode = select_mode(progress)
                if mode == 1:
                    wave_mode(max_speed, duration)
                    current_modus = "Welle"
                elif mode == 2:
                    pulse_mode(max_speed, duration)
                    current_modus = "Schlagartig"
                elif mode == 3:
                    wave_mode(max_speed, duration)
                    current_modus = "Welle"
                elif mode == 4:
                    standard_mode(max_speed, duration)
                    current_modus = "Standard"
                elif mode == 5:
                    chaos_mode(max_speed, duration)
                    current_modus = "Chaos"
                elif mode == 6:
                    tease_mode(max_speed, duration)
                    current_modus = "Tease"
                elif mode == 7:
                    random_mode(max_speed, duration)
                    current_modus = "Random"
                elif mode == 8:
                    edge_mode(max_speed, duration)
                    current_modus = "Edge"
                elif mode == 9:
                    whip_mode(max_speed, duration)
                    current_modus = "Whip"
                else:
                    plateau_mode(max_speed, duration, progress)
                    current_modus = "Plateau"

                MODE_COUNTS[mode] = MODE_COUNTS.get(mode, 0) + 1
                SESSION_MODE_COUNTS[mode] = SESSION_MODE_COUNTS.get(mode, 0) + 1

                # Streak-System: Verfolge Wiederholungen
                if last_modus == current_modus:
                    MODUS_STREAK[current_modus] = MODUS_STREAK.get(current_modus, 0) + 1
                else:
                    MODUS_STREAK[current_modus] = 1
                last_modus = current_modus

                # Make-Cum nur ab 40% Session-Fortschritt
                if progress >= 0.5 and random.random() < EVENT_PROB["make_cum"]:
                    make_cum()

                # Pflicht-Recovery nach intensiven Modi (Edge, Chaos, Schlagartig)
                if current_modus in ("Edge", "Chaos", "Schlagartig"):
                    intense_floor = 30 if GENDER == "F" else 60
                    min_intense_recovery = max(recovery, intense_floor)
                    print(f"[Intensive Erholung] {min_intense_recovery:.1f}s nach {current_modus}")
                    do_recovery(min_intense_recovery)
                else:
                    print(f"Erholung: {recovery:.1f}s")
                    do_recovery(recovery)

                cycle_peak_level = max(cycle_peak_level, LEVEL)
                LEVEL += 1.0
                # Level erhÃ¶hen oder zurÃ¼cksetzen
                if random.random() < 0.85:
                    LEVEL += 1.3
                    print(f"Level auf {LEVEL:.1f} gestiegen!")
                elif random.random() < EVENT_PROB["level_reset"]:
                    LEVEL = 1
                    print("[Ãœberraschung] Level auf 1 zurÃ¼ckgesetzt!")
                cycle_peak_level = max(cycle_peak_level, LEVEL)

                log_event(
                    "mode_step",
                    cycle=cycle_idx,
                    mode_id=mode,
                    mode_name=current_modus,
                    level_before=round(level_before, 2),
                    level_after=round(LEVEL, 2),
                    progress=round(progress, 4),
                    max_speed=max_speed,
                    duration_seconds=round(duration, 2),
                    recovery_seconds=round(recovery, 2),
                    time_left_seconds=round(time_left, 2),
                    streak=dict(MODUS_STREAK),
                )

            log_event(
                "cycle_end",
                cycle=cycle_idx,
                total_cycles=cycle_count,
                peak_level=round(cycle_peak_level, 2),
                final_level=round(LEVEL, 2),
                mode_counts=dict(MODE_COUNTS),
                streaks=dict(MODUS_STREAK),
                elapsed_seconds=round(time.time() - start_time, 2),
            )
            if cycle_idx < cycle_count:
                reset_pause = random.uniform(30, 90)
                pwm.ChangeDutyCycle(0)
                print(f"[Reset] Pause vor neuem Durchlauf: {reset_pause:.0f}s")
                log_event("cycle_reset_pause", cycle=cycle_idx, total_cycles=cycle_count, pause_seconds=round(reset_pause, 2))
                time.sleep(reset_pause)
    finally:
        pwm.stop()
        GPIO.cleanup()
        minutes_total = SESSION_DURATION / 60
        print(f"Sitzungsdauer von {minutes_total:.1f} Minuten pro Durchlauf erreicht. Programm beendet.")
        log_event(
            "session_end",
            session_duration_seconds=SESSION_DURATION,
            cycle_count=cycle_count,
            cycle_duration_seconds=round(cycle_duration, 2),
            gender=GENDER,
            log_path=str(SESSION_LOG_PATH) if SESSION_LOG_PATH is not None else None,
            final_level=round(LEVEL, 2),
            mode_counts=dict(SESSION_MODE_COUNTS),
        )

if __name__ == "__main__":
    main()
