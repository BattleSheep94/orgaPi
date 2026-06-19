# coding: utf8
# Programm zur Steuerung eines Vibrators mit PWM auf einem Raspberry Pi mit PCB-Adapter
# Nutzt GPIO 21 (BCM, PCB-Adapter: primaere Steuerung) fuer alle Modi
# 13 Modi: Welle, Schlagartig, Standard, Chaos, Tease, Random, Edge, Whip,
#          Plateau, Denial Loop, Atem, Herzschlag, Achterbahn
# Spannungskurve: Warm-Up -> Aufbau -> Halbzeit-Edging -> Tortur -> Finale
# Orgasmuskontrolle: Sanfter Start, steigende Intensitaet, Denial, Ueberziehendes Finale

# Falls das Skript auf einem Nicht-Raspberry-System ausgefuehrt wird (z.B. Windows),
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
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# GPIO-Setup (BCM-Modus fuer Pin-Nummerierung)
# ---------------------------------------------------------------------------
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Pin fuer PWM auf dem PCB-Adapter
PRIMARY_PWM_PIN = 21  # GPIO 21 (BCM, PCB-Adapter: primaere Steuerung)
GPIO.setup(PRIMARY_PWM_PIN, GPIO.OUT)

# PWM mit 50 Hz initialisieren
pwm = GPIO.PWM(PRIMARY_PWM_PIN, 50)
pwm.start(0)

# ---------------------------------------------------------------------------
# Globale Variablen
# ---------------------------------------------------------------------------
LEVEL = 1                    # Aktuelles Level, beeinflusst Intensitaet
SESSION_DURATION = 10800     # Wird bei Programmstart durch Benutzereingabe ueberschrieben
BASE_PROBABILITIES = {
    "make_cum": 0.10,
    "sadistic_edge": 0.05,   # Quael-Edge statt zufaelliger extreme_torture (kein Orgasmus)
    "level_reset": 0.05,
    "fake_phase": 0.05,
    "random_delay": 0.05,
}
EVENT_PROB = BASE_PROBABILITIES.copy()
MODE_COUNTS = {i: 0 for i in range(1, 18)}   # 17 Modi (1-17)
MODUS_STREAK = {}
MID_CLIMAX_DONE = False
FINAL_CLIMAX_DONE = False
GENDER = "M"                 # "M" = Mann, "F" = Frau, wird bei Programmstart gesetzt
ORIGINAL_GENDER = "M"        # Original-Geschlecht; bleibt auch bei temp. F-Switch
DURATION_MULTIPLIER = 1.0
SESSION_CYCLE_COUNT = 1
SESSION_MODE_COUNTS = {}
SESSION_LOG_PATH = None

# Geschlechtsabhaengige Recovery-Parameter (Standard: Mann)
MIN_CALM_RECOVERY = 30
RECOVERY_DURATION_RATIO_MIN = 10
RECOVERY_DURATION_RATIO_MAX = 20
RECOVERY_UPPER_CAP = 200

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_session_log = []

def init_session_log():
    """Initialisiert das Session-Log."""
    global SESSION_LOG_PATH, _session_log
    _session_log = []
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    SESSION_LOG_PATH = Path(f"session_log_{timestamp}.json")

def log_event(event_type, **kwargs):
    """Protokolliert ein Event mit Typ und beliebigen Zusatzfeldern."""
    entry = {"event": event_type, "ts": time.time()}
    entry.update(kwargs)
    _session_log.append(entry)

def save_session_log():
    """Schreibt das Session-Log als JSON-Datei."""
    if SESSION_LOG_PATH is not None and _session_log:
        with open(SESSION_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(_session_log, f, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def clamp_prob(value, upper=0.7):
    """Begrenzt Wahrscheinlichkeiten auf einen sinnvollen Bereich."""
    return max(0.0, min(value, upper))

def rescale_probabilities():
    """Skaliert alle Wahrscheinlichkeiten passend zur tatsaechlichen Sitzungsdauer."""
    for key, base in BASE_PROBABILITIES.items():
        EVENT_PROB[key] = clamp_prob(base)

# ---------------------------------------------------------------------------
# Basis-Modi (1-10)
# ---------------------------------------------------------------------------
def test_vibrator():
    """Testet den Vibrator fuer 2 Sekunden auf 80% Intensitaet."""
    print("[Test] Vibrator-Test gestartet...")
    pwm.ChangeDutyCycle(80)
    time.sleep(2)
    pwm.ChangeDutyCycle(0)
    print("[Test] Vibrator-Test beendet.")

def fake_phase():
    """Taeuscht den Start einer neuen Phase vor (2 Sekunden wechselnde Intensitaet)."""
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
    """Verzoegert Modusstart ohne Meldungen (5-20 Sekunden)."""
    delay_time = random.uniform(5, 20)
    time.sleep(delay_time)

def wave_mode(max_speed, duration):
    """Modus 1+3: Welle - Generische Wellen mit zufaelligen Laengen und Geschwindigkeiten."""
    step_time = random.uniform(0.01, 0.06)
    variant = "Schnell" if step_time < 0.025 else ("Mittel" if step_time < 0.04 else "Langsam")
    print(f"[Welle/{variant}] Max: {max_speed}%, Dauer: {duration:.1f}s, Step: {step_time:.3f}s")
    log_event("mode_start", mode="Welle", variant=variant, max_speed=max_speed, duration_seconds=round(duration, 2))
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
    log_event("mode_end", mode="Welle", elapsed_seconds=round(time.time() - start, 2))

def pulse_mode(max_speed, duration):
    """Modus 2: Schlagartig - Schnelle Pulse mit kurzen Pausen."""
    print(f"[Schlagartig] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Schlagartig", max_speed=max_speed, duration_seconds=round(duration, 2))
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
    log_event("mode_end", mode="Schlagartig", elapsed_seconds=round(elapsed, 2))

def standard_mode(max_speed, duration):
    """Modus 4: Standard - Konstante Geschwindigkeit fuer die angegebene Dauer."""
    print(f"[Standard] Konstante Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Standard", max_speed=max_speed, duration_seconds=round(duration, 2))
    # Sanft hochfahren
    for i in range(0, max_speed, 1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.02)
    time.sleep(max(0, duration - 0.04 * max_speed))
    # Sanft runterfahren
    for i in range(max_speed, -1, -1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.02)
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Standard")

def chaos_mode(max_speed, duration):
    """Modus 5: Chaos - Zufaellige Intensitaetsspitzen mit kurzen Pausen."""
    print(f"[Chaos] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Chaos", max_speed=max_speed, duration_seconds=round(duration, 2))
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
    log_event("mode_end", mode="Chaos", elapsed_seconds=round(elapsed, 2))

def tease_mode(max_speed, duration):
    """Modus 6: Tease - Langsames Ansteigen mit Abbruch vor variablem Maximum."""
    print(f"[Tease] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Tease", max_speed=max_speed, duration_seconds=round(duration, 2))
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
    # Kurzer Hoehepunkt am Ende
    pwm.ChangeDutyCycle(max_speed)
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Tease")

def edge_mode(max_speed, duration):
    """Modus 8: Edge - Schnelles Ansteigen bis knapp unter Maximum, Abbruch, Wiederholung."""
    print(f"[Edge] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Edge", max_speed=max_speed, duration_seconds=round(duration, 2))
    elapsed = 0
    while elapsed < duration - 1:
        for i in range(0, 100, 5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.025)
        time.sleep(0.3)
        for i in range(100, 0, -5):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.025)
        time.sleep(0.2)
        elapsed += (0.5 + 0.3 + 0.5 + 0.2)
    print("[Edge] So nah... und doch so fern!")
    pwm.ChangeDutyCycle(0)
    time.sleep(1)
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Edge")

def whip_mode(max_speed, duration):
    """Modus 9: Whip - Kurze 100%-Bursts mit langen Pausen. Schock/UEberraschung."""
    print(f"[Whip] Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Whip", duration_seconds=round(duration, 2))
    # LEVEL ist float (wird mit += 1.3 erhoeht); randint braucht int.
    _lvl = int(LEVEL)
    num_whips = random.randint(3 + (_lvl - 1) // 3, min(8 + (_lvl - 1) // 2, 20))
    elapsed = 0
    for _ in range(num_whips):
        if elapsed >= duration:
            break
        whip_duration = random.uniform(0.2, 0.6)
        print("[Whip] Spuer den Hieb!")
        pwm.ChangeDutyCycle(100)
        time.sleep(whip_duration)
        pwm.ChangeDutyCycle(0)
        pause_time = random.uniform(2, 8)
        time.sleep(pause_time)
        elapsed += whip_duration + pause_time
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Whip")

def plateau_mode(max_speed, duration, progress):
    """Modus 10: Plateau - Moderate Dauerstimulation, steigert sich mit Session-Fortschritt."""
    low = int(20 + 20 * progress)
    high = int(40 + 20 * progress)
    plateau_intensity = random.randint(low, max(low, min(high, max_speed)))
    print(f"[Plateau] Intensitaet: {plateau_intensity}%, Dauer: {duration:.1f}s (Fortschritt: {progress:.0%})")
    log_event("mode_start", mode="Plateau", intensity=plateau_intensity, duration_seconds=round(duration, 2))
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
    log_event("mode_end", mode="Plateau")

# ---------------------------------------------------------------------------
# Neue Modi (11-13)
# ---------------------------------------------------------------------------
def breath_mode(max_speed, duration):
    """Modus 11: Atem - Rhythmische Wellen die an Atemzuege erinnern.
    Einatmen (schneller Anstieg), Ausatmen (langsamer Abfall).
    Unregelmuessige Atempause dazwischen. Sehr meditativ, gut als Warm-Up.
    """
    print(f"[Atem] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Atem", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    while (time.time() - start) < duration:
        # Einatmen - schneller Anstieg
        inhale_peak = random.randint(int(max_speed * 0.4), int(max_speed * 0.7))
        inhale_speed = random.uniform(0.015, 0.035)
        for i in range(0, inhale_peak, 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(inhale_speed)
            if (time.time() - start) >= duration:
                break
        # Kurz halten
        hold = random.uniform(0.5, 1.5)
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(hold, remaining))
        # Ausatmen - langsamer Abfall
        exhale_speed = inhale_speed * random.uniform(1.5, 3.0)
        for i in range(inhale_peak, -1, -1):
            pwm.ChangeDutyCycle(i)
            time.sleep(exhale_speed)
            if (time.time() - start) >= duration:
                break
        # Atempause (unregelmuessig, wie echtes Atmen)
        breath_pause = random.uniform(1.0, 4.0)
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(breath_pause, remaining))
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Atem", elapsed_seconds=round(time.time() - start, 2))

def heartbeat_mode(max_speed, duration):
    """Modus 12: Herzschlag - Doppel-Impulse wie ein schlagendes Herz.
    Lub-Dub-Rhythmus mit beschleunigender Frequenz.
    Gut in Phase 2-4 fuer unbewusste Spannungssteigerung.
    """
    print(f"[Herzschlag] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Herzschlag", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    # BPM steigt ueber die Dauer: 60 -> 110 (gedeckelt). Der Rhythmus allein
    # fuehrt nicht zum Orgasmus - entscheidend ist die Intensitaet (Duty Cycle).
    base_bpm = 60
    while (time.time() - start) < duration:
        elapsed_frac = min(1.0, (time.time() - start) / duration)
        bpm = base_bpm + elapsed_frac * 50  # 60 -> 110
        beat_interval = 60.0 / bpm
        # Intensitaet gedeckelt auf max ~70% von max_speed: Herzschlag ist ein
        # subtiler "Mittel"-Modus und soll allein keinen Orgasmus ausloesen.
        intensity = int(max_speed * (0.35 + 0.35 * elapsed_frac))
        # Erster Schlag (Lub)
        for i in range(0, intensity, 3):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.005)
        time.sleep(0.06)
        for i in range(intensity, 0, -3):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.005)
        # Kurze Pause
        time.sleep(beat_interval * 0.15)
        # Zweiter Schlag (Dub, etwas leiser)
        dub_intensity = int(intensity * 0.7)
        for i in range(0, dub_intensity, 3):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.005)
        time.sleep(0.04)
        for i in range(dub_intensity, 0, -3):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.005)
        # Pause bis naechster Herzschlag
        remaining_beat = beat_interval - 0.15 * beat_interval - 0.06 - 0.04
        if remaining_beat > 0:
            time.sleep(remaining_beat)
        if (time.time() - start) >= duration:
            break
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Herzschlag", elapsed_seconds=round(time.time() - start, 2))

def rollercoaster_mode(max_speed, duration):
    """Modus 13: Achterbahn - Extreme Kontraste: tiefe Taeler, hohe Gipfel.
    Lange Aufstiege, steile Abstuerze, gelegentlich Surprise-100%-Burst am Boden.
    Spaet in der Session fuer maximale Desorientierung.
    """
    print(f"[Achterbahn] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Achterbahn", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    while (time.time() - start) < duration:
        # Tal (tiefe Ruhe)
        valley = random.randint(5, 20)
        pwm.ChangeDutyCycle(valley)
        valley_time = random.uniform(1.0, 4.0)
        time.sleep(valley_time)
        # Lange Kletterfahrt nach oben
        peak = random.randint(int(max_speed * 0.7), max_speed)
        climb_steps = random.uniform(0.01, 0.04)
        for i in range(valley, peak, 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(climb_steps)
            if (time.time() - start) >= duration:
                break
        # Gipfel kurz halten
        hold = random.uniform(0.3, 2.0)
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(hold, remaining))
        # STEILER Absturz
        for i in range(peak, -1, -3):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.008)
        # Surprise-Burst am Boden (20% Chance)
        if random.random() < 0.2:
            pwm.ChangeDutyCycle(100)
            time.sleep(random.uniform(0.1, 0.4))
            pwm.ChangeDutyCycle(0)
        time.sleep(random.uniform(0.5, 2.0))
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Achterbahn", elapsed_seconds=round(time.time() - start, 2))

# ---------------------------------------------------------------------------
# Weitere sanfte und mittlere Modi (14-17)
# ---------------------------------------------------------------------------
def flutter_mode(max_speed, duration):
    """Modus 14: Flattern - Sehr schnelle winzige Impulse bei niedriger Intensitaet.

    Wie ein Insekt auf der Haut - kaum spuerbar aber staendig. Tickle-Effekt,
    der nie ausreicht um zu befriedigen. Sanfte psychologische Quaelerei,
    ideal als Warm-Up und fuer die Hilflosigkeit im Bondage.
    """
    print(f"[Flattern] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Flattern", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    while (time.time() - start) < duration:
        # Sehr niedrige Intensitaet (5-25% von max_speed)
        intensity = random.randint(5, max(5, int(max_speed * 0.25)))
        # Sehr schnelle winzige Impulse
        for _ in range(random.randint(3, 12)):
            pwm.ChangeDutyCycle(intensity)
            time.sleep(random.uniform(0.02, 0.06))
            pwm.ChangeDutyCycle(0)
            time.sleep(random.uniform(0.01, 0.04))
            if (time.time() - start) >= duration:
                break
        # Kurze Pause zwischen Impuls-Buendeln
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(random.uniform(0.5, 2.0), remaining))
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Flattern", elapsed_seconds=round(time.time() - start, 2))

def drip_mode(max_speed, duration):
    """Modus 15: Tropfen - Einzelne isolierte sanfte Pulse mit langen Pausen.

    Wie Wassertropfen - jeder Tropfen ist ein kurzer sanfter Impuls (15-30%),
    gefolgt von 5-15s Stille. Erzeugt starke Erwartungspannung, weil man auf
    den naechsten Tropfen wartet. Sehr psychologisch - perfekt fuer Bondage.
    """
    print(f"[Tropfen] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Tropfen", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    while (time.time() - start) < duration:
        # Sanfter Tropfen aufbauen und abfallen
        intensity = random.randint(15, max(15, int(max_speed * 0.3)))
        for i in range(0, intensity, 2):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.03)
            if (time.time() - start) >= duration:
                break
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(random.uniform(0.5, 1.5), remaining))
        for i in range(intensity, -1, -2):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.03)
        pwm.ChangeDutyCycle(0)
        # Lange Stille - Erwartung auf den naechsten Tropfen
        pause = random.uniform(5.0, 15.0)
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(pause, remaining))
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Tropfen", elapsed_seconds=round(time.time() - start, 2))

def metronome_mode(max_speed, duration):
    """Modus 16: Metronom - Strenge regelmassige Pulse bei mittlerer Intensitaet.

    Konstanter Takt der sich langsam verschiebt (40 -> 60 BPM). Hypnotisch und
    erzeugt Erwartung, weil das Nervensystem sich auf den Rhythmus einstellt.
    Distinkt vom Herzschlag (Lub-Dub) - hier gleichmaessige einzelne Pulse.
    """
    print(f"[Metronom] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Metronom", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    base_bpm = random.randint(40, 60)
    while (time.time() - start) < duration:
        elapsed_frac = min(1.0, (time.time() - start) / duration)
        bpm = base_bpm + elapsed_frac * 20
        beat_interval = 60.0 / bpm
        # Mittlere Intensitaet (40-70% von max_speed)
        intensity = int(max_speed * random.uniform(0.4, 0.7))
        # Einzelner Pulse - schneller Anstieg und Abfall
        for i in range(0, intensity, 2):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.008)
        time.sleep(random.uniform(0.15, 0.3))
        for i in range(intensity, 0, -2):
            pwm.ChangeDutyCycle(i)
            time.sleep(0.008)
        pwm.ChangeDutyCycle(0)
        # Stille bis zum naechsten Schlag
        remaining_beat = beat_interval - 0.3
        if remaining_beat > 0:
            time.sleep(remaining_beat)
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Metronom", elapsed_seconds=round(time.time() - start, 2))

def tide_mode(max_speed, duration):
    """Modus 17: Gezeiten - Sehr lange langsame Zyklen zwischen niedrig und mittel.

    Pendelt ueber 30-60s zwischen 20% und 60% von max_speed, wie Gezeiten.
    Fast unauffaellig im Wechsel aber stetig. Gibt dem Koerper Zeit zu
    reagieren und baut eine tiefe wellenfoermige Spannung auf.
    """
    print(f"[Gezeiten] Max: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Gezeiten", max_speed=max_speed, duration_seconds=round(duration, 2))
    start = time.time()
    while (time.time() - start) < duration:
        # Ein kompletter Gezeitenzyklus (30-60s)
        cycle_time = random.uniform(30.0, 60.0)
        low = random.randint(10, max(10, int(max_speed * 0.2)))
        high = random.randint(int(max_speed * 0.4), int(max_speed * 0.6))
        # Langsam ansteigen (Flut)
        rise_step = (cycle_time * 0.4) / max(1, (high - low))
        for i in range(low, high, 1):
            pwm.ChangeDutyCycle(i)
            time.sleep(rise_step)
            if (time.time() - start) >= duration:
                break
        # Hochwasser halten
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(cycle_time * 0.2, remaining))
        # Langsam abfallen (Ebbe)
        fall_step = (cycle_time * 0.4) / max(1, (high - low))
        for i in range(high, low - 1, -1):
            pwm.ChangeDutyCycle(i)
            time.sleep(fall_step)
            if (time.time() - start) >= duration:
                break
        # Kurze Ebbe-Pause
        remaining = duration - (time.time() - start)
        if remaining > 0:
            time.sleep(min(random.uniform(2.0, 5.0), remaining))
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Gezeiten", elapsed_seconds=round(time.time() - start, 2))

# ---------------------------------------------------------------------------
# Denial Loop (Modus 11 interne Nummer, separate Funktion)
# ---------------------------------------------------------------------------
def denial_loop_mode(rounds=None, start_peak=85):
    """Denial Loop: Je hoeher der Peak, desto kuerzer das Plateau.
    Unberechenbar durch zufaelligen Peak pro Runde - auch 100% moeglich, aber sehr kurz.
    """
    if rounds is None:
        rounds = random.randint(2, 4) if GENDER == "F" else random.randint(3, 5)

    pause_min = 15 if GENDER == "F" else 30
    pause_max = 30 if GENDER == "F" else 60

    print(f"[Denial Loop] {rounds} Runden, Start-Peak {start_peak}%")
    log_event("denial_loop_start", rounds=rounds, start_peak=start_peak, gender=GENDER)

    for i in range(rounds):
        # Peak: steigt pro Runde, kann auch 100% erreichen
        peak = min(100, start_peak + i * random.randint(2, 5))

        # Je hoeher der Peak, desto kuerzer das Plateau - inverses Verhaeltnis
        plateau_base = max(1.0, 7.0 - (peak - 85) * 0.3)
        plateau_variation = random.uniform(-0.5, 1.5)
        plateau_time = max(1.0, plateau_base + plateau_variation)

        print(f"[Denial Loop] Runde {i + 1}/{rounds} - Peak {peak}%, Plateau {plateau_time:.1f}s")

        # Hochfahren - bei hoeherem Peak schneller
        step_time = max(0.008, 0.04 - (peak - 85) * 0.001)
        for val in range(0, peak, 1):
            pwm.ChangeDutyCycle(val)
            time.sleep(step_time)

        # Am Limit halten
        pwm.ChangeDutyCycle(peak)
        time.sleep(plateau_time)

        # Abrupter Abbruch (schnell runter in -5er Schritten)
        for val in range(peak, -1, -5):
            pwm.ChangeDutyCycle(val)
            time.sleep(0.01)
        pwm.ChangeDutyCycle(0)

        # Pause schrumpft pro Runde (Nervensystem-Erholung)
        shrink = i * (1.5 if GENDER == "F" else 3)
        pause = random.uniform(
            max(pause_min - shrink, pause_min * 0.5),
            max(pause_max - shrink, pause_min)
        )
        print(f"[Denial Loop] Abbruch! Erholung {pause:.0f}s...")
        log_event("denial_loop_round", round=i + 1, peak=peak, plateau_time=round(plateau_time, 2), pause_seconds=round(pause, 2))
        time.sleep(pause)

    pwm.ChangeDutyCycle(0)
    print("[Denial Loop] Verweigerung abgeschlossen.")
    log_event("denial_loop_end", rounds=rounds, gender=GENDER)

def random_mode(max_speed, duration):
    """Modus 7: Random - Zufaellige Kombination von Elementen anderer Modi."""
    print(f"[Random] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    log_event("mode_start", mode="Random", max_speed=max_speed, duration_seconds=round(duration, 2))
    elapsed = 0
    while elapsed < duration:
        sub_mode = random.choice([wave_mode, pulse_mode, chaos_mode, whip_mode, breath_mode, heartbeat_mode, flutter_mode, drip_mode, metronome_mode, tide_mode])
        sub_duration = random.uniform(1, 3)
        sub_mode(max_speed, sub_duration)
        elapsed += sub_duration
    pwm.ChangeDutyCycle(0)
    log_event("mode_end", mode="Random")

# ---------------------------------------------------------------------------
# Make-Cum und Extreme-Torture (BUG 1+2 FIX: reason-Parameter vorhanden)
# ---------------------------------------------------------------------------
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
            # Welle zwischen 80-100%
            step_time = random.uniform(0.01, 0.03)
            low = random.randint(80, 95)
            for i in range(100, low - 1, -1):
                pwm.ChangeDutyCycle(i)
                time.sleep(step_time)
            time.sleep(random.uniform(0.3, 1.0))
            for i in range(low, 101):
                pwm.ChangeDutyCycle(i)
                time.sleep(step_time)
        elif pattern < 0.45:
            # Chaos-Bursts
            for _ in range(random.randint(4, 10)):
                intensity = random.randint(85, 100)
                pwm.ChangeDutyCycle(intensity)
                time.sleep(random.uniform(0.1, 0.5))
            pwm.ChangeDutyCycle(100)
        elif pattern < 0.55:
            # Fake-Ende
            print(f"[Make-Cum{label}] Ende... oder doch nicht!")
            for i in range(100, -1, -5):
                pwm.ChangeDutyCycle(i)
                time.sleep(0.02)
            time.sleep(random.uniform(5.0, 30.0))
            pwm.ChangeDutyCycle(100)
        else:
            # Konstant 100%
            pwm.ChangeDutyCycle(100)
            time.sleep(random.uniform(10, 60))

    print(f"[Make-Cum{label}] Beendet nach {(time.time()-start):.0f}s.")
    pwm.ChangeDutyCycle(0)
    log_event("make_cum_end", duration_seconds=round(time.time() - start, 2), reason=reason or "random", gender=GENDER)

def extreme_torture(duration_override=None, reason=None):
    """Extreme-Torture: Motor auf 100%. Dauer geschlechtsabhaengig mit Variation.
    BUG 1 FIX: Mann ohne Override ist jetzt random.uniform(45, 180) statt hardcoded 60s.
    BUG 1 FIX: reason-Parameter hinzugefuegt.
    """
    if duration_override is not None:
        duration = duration_override
    elif GENDER == "F":
        duration = random.uniform(180, 800)
    else:
        duration = random.uniform(45, 180)

    label = f" [{reason}]" if reason else ""
    if duration >= 60:
        print(f"[Extreme Torture{label}] Motor auf 100% fuer {duration/60:.1f} Minuten!")
    else:
        print(f"[Extreme Torture{label}] Motor auf 100% fuer {duration:.0f} Sekunden!")

    log_event("extreme_torture_start", duration_seconds=round(duration, 2),
              reason=reason or "random", gender=GENDER)
    pwm.ChangeDutyCycle(100)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)
    log_event("extreme_torture_end", duration_seconds=round(duration, 2), reason=reason or "random", gender=GENDER)

# ---------------------------------------------------------------------------
# Sadistischer Edge (Quael-Event, kein Orgasmus)
# ---------------------------------------------------------------------------
def sadistic_edge_mode(duration):
    """Sadistischer Edge-Modus: Mehrere Edges knapp unter 100%, kaum Erholung.

    Qualvoller als Extreme-Torture, aber ohne Orgasmus (keine echte 100%-Phase).
    Peak steigt pro Edge und rueckt immer naeher ans Limit, wird dann abrupt
    abgebrochen - reines Denial. Ersetzt die frueheren zufaelligen
    extreme_torture-Events als 'Quael-Aktion' ohne Orgasmus.
    """
    rounds = random.randint(4, 8)
    print(f"[Sadistic Edge] {rounds} Edges geplant, Dauer bis ~{duration:.0f}s")
    log_event("sadistic_edge_start", rounds=rounds, gender=GENDER)
    start = time.time()
    for i in range(rounds):
        if (time.time() - start) >= duration:
            break
        # Peak rueckt pro Edge ans Limit und kann spaeter 100% erreichen.
        # 100% ist intensiv, aber nicht per se gefaehrlich - das Nervensystem
        # braucht ein paar Sekunden, um zum Orgasmus zu reizen. Die Sicherung
        # liegt daher in der kurzen Hold-Zeit (unter der 5-10s-Vollintensitaets-
        # Grenze) plus ausreichender Pause zwischen den Edges.
        peak = min(100, 90 + i * random.randint(2, 3))
        # Schnell hochfahren
        climb_step = random.uniform(0.015, 0.03)
        for val in range(0, peak, 1):
            pwm.ChangeDutyCycle(val)
            time.sleep(climb_step)
        # Am Limit halten - kurz und qualvoll, aber unter der 5-10s-Vollintensitaets-
        # Grenze, damit es nicht zum Orgasmus kommt. Letzter Edge minimal laenger.
        hold = random.uniform(1.5, 3.0) if i == rounds - 1 else random.uniform(0.5, 1.8)
        pwm.ChangeDutyCycle(peak)
        time.sleep(hold)
        # Abrupter Abbruch - Denial!
        for val in range(peak, -1, -5):
            pwm.ChangeDutyCycle(val)
            time.sleep(0.008)
        pwm.ChangeDutyCycle(0)
        log_event("sadistic_edge_round", round=i + 1, peak=peak, hold_seconds=round(hold, 2))
        # Laengere Pause (5-12s): Erregung sinkt unter die Point-of-no-Return-
        # Schwelle, damit der naechste Edge kein Orgasmus wird. Kurz genug, um
        # qualvoll zu bleiben, lang genug fuer Nervensystem-Erholung.
        # Das ist die eigentliche Sicherung gegen versehentlichen Orgasmus -
        # nicht die Peak-Hoehe, sondern Hold-Zeit + Pause.
        time.sleep(random.uniform(5.0, 12.0))
    pwm.ChangeDutyCycle(0)
    print("[Sadistic Edge] Verweigert - kein Orgasmus.")
    log_event("sadistic_edge_end", rounds=rounds, gender=GENDER)

# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------
def _recovery_massage(recovery_time):
    """Sanfte Massage-Erholung: langsame Wellen bei 20-50% statt Stille."""
    print(f"[Massage] Sanfte Erholung fuer {recovery_time:.0f}s")
    log_event("recovery_massage_start", recovery_seconds=round(recovery_time, 2))
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
        # Gelegentlicher UEberraschungsimpuls (8%)
        if random.random() < 0.08:
            pwm.ChangeDutyCycle(100)
            time.sleep(random.uniform(0.2, 0.5))
            pwm.ChangeDutyCycle(high)
    pwm.ChangeDutyCycle(0)
    log_event("recovery_massage_end", recovery_seconds=round(recovery_time, 2))

def recovery_with_pulses(recovery_time):
    """Erholungsphase mit verteilten Burst-Impulsen bei 100%."""
    log_event("recovery_pulses_start", recovery_seconds=round(recovery_time, 2))
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
    log_event("recovery_pulses_end", recovery_seconds=round(recovery_time, 2))

def do_recovery(recovery_time):
    """Waehlt Erholungsart: Massage oder Impuls-basiert. (BUG 3 FIX: nur eine Definition)"""
    massage_chance = 0.6 if GENDER == "F" else 0.4
    if random.random() < massage_chance:
        log_event("recovery_start", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        _recovery_massage(recovery_time)
        log_event("recovery_end", method="massage", recovery_seconds=round(recovery_time, 2), gender=GENDER)
    else:
        log_event("recovery_start", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)
        recovery_with_pulses(recovery_time)
        log_event("recovery_end", method="pulses", recovery_seconds=round(recovery_time, 2), gender=GENDER)

# ---------------------------------------------------------------------------
# Geschlechts-Konfiguration (BUG 3 FIX: nur eine Definition)
# ---------------------------------------------------------------------------
def apply_gender_config():
    """Setzt geschlechtsabhaengige Parameter basierend auf GENDER."""
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

# ---------------------------------------------------------------------------
# Level- und Parameter-Berechnung
# ---------------------------------------------------------------------------
def level_recovery_factor(level):
    """Level-Faktor fuer Recovery: hoeheres Level -> kuerzere Erholung.
    Level 1 -> 1.0, Level 10 -> 0.775, Level 20 -> 0.525, min 0.5.
    """
    return max(0.5, 1.0 - (level - 1) * 0.025)

def _recovery_for_duration(duration, level):
    """Leitet eine Erholungspause aus der tatsaechlichen Motor-Laufzeit ab."""
    lf = level_recovery_factor(level)
    floor = MIN_CALM_RECOVERY * lf
    ratio_min = RECOVERY_DURATION_RATIO_MIN * lf
    ratio_max = RECOVERY_DURATION_RATIO_MAX * lf
    cap = RECOVERY_UPPER_CAP * lf

    min_recovery = max(floor, duration * ratio_min)
    max_recovery = min(max(min_recovery + 20, duration * ratio_max), cap)
    max_recovery = max(max_recovery, min_recovery + 5)

    # Gewichtete Verteilung: kurze Pausen wahrscheinlicher als lange
    raw = random.random() ** 1.5
    return min_recovery + raw * (max_recovery - min_recovery)

def calculate_parameters(level, streak_modus):
    """Berechnet Zufallsparameter basierend auf dem aktuellen Level und Streak."""
    speeds = list(range(88, 101))
    weights = [1 + (i / 20) * (level - 1) / 5 for i in range(len(speeds))]
    max_speed = random.choices(speeds, weights=weights, k=1)[0]

    level_boost = max(0.0, (level - 1)) ** 0.5 * 1.5
    min_duration = 1 + level_boost * 0.5
    max_duration = 10 + level_boost * 1.2
    duration = random.uniform(min_duration, max_duration) * DURATION_MULTIPLIER

    if random.random() < 0.05:
        duration *= 1.5
        max_speed = min(100, max_speed + 10)
        print(f"[Variation] Modusvariante: Dauer {duration:.1f}s, Intensitaet {max_speed}%")

    if MODUS_STREAK.get(streak_modus, 0) >= 3:
        if random.random() < 0.5:
            max_speed = min(100, max_speed + 10)
            print(f"[Streak] Intensitaet erhoeht auf {max_speed}%")
        else:
            duration *= 1.5
            print(f"[Streak] Dauer erhoeht auf {duration:.1f}s")

    recovery = _recovery_for_duration(duration, level)
    return max_speed, duration, recovery

def calculate_parameters_with_time(level, streak_modus, time_left):
    """Wie calculate_parameters, aber begrenzt Dauer/Erholung an verbleibende Zeit."""
    max_speed, duration, recovery = calculate_parameters(level, streak_modus)
    duration = min(duration, max(3, time_left * 0.25))
    lf = level_recovery_factor(level)
    recovery = min(recovery, max(MIN_CALM_RECOVERY * lf, time_left * 0.4))
    return max_speed, duration, recovery

# ---------------------------------------------------------------------------
# Halbzeit-Climax (FEATURE 2: Edging statt Make-Cum)
# ---------------------------------------------------------------------------
def mid_session_climax():
    """Halbzeit-Edging: Denial Loop + Chaos-Burst, kein Orgasmus.
    FEATURE 2: Komplett neue Version - kein make_cum() Aufruf.
    """
    global MID_CLIMAX_DONE
    if MID_CLIMAX_DONE:
        return
    MID_CLIMAX_DONE = True
    print("\n=== HALBZEIT - EDGING ===")
    log_event("mid_climax_start", gender=GENDER)

    # Denial Loop statt Make-Cum
    denial_loop_mode(rounds=random.randint(2, 3), start_peak=82)
    log_event("mid_climax_pause", gender=GENDER, note="denial_complete")

    # Chaos-Burst danach
    chaos_mode(100, random.uniform(5.0, 12.0))
    log_event("mid_climax_chaos_burst", gender=GENDER)

    # Harter Abbruch, kein Orgasmus
    pwm.ChangeDutyCycle(0)

    # Abschluss-Recovery (time.sleep, kein do_recovery)
    if GENDER == "F":
        pause = random.uniform(20, 45)
    else:
        pause = random.uniform(40, 90)
    print(f"[Halbzeit] Erholung fuer {pause:.0f}s. Kein Orgasmus.")
    log_event("mid_climax_pause", pause_seconds=round(pause, 2), gender=GENDER)
    time.sleep(pause)
    log_event("mid_climax_end", pause_seconds=round(pause, 2), gender=GENDER)

# ---------------------------------------------------------------------------
# Modus-Auswahl (FEATURE: Whip als eigene Schock-Kategorie)
# ---------------------------------------------------------------------------
def select_mode(progress):
    """Waehlt einen Modus basierend auf Session-Fortschritt (0.0 = Anfang, 1.0 = Ende).

    Spannungskurve-Phasen:
    - Phase 1 (0-30%):  Warm-Up - Tease, Plateau, Welle, Atem. Kein Maximum.
    - Phase 2 (30-50%): Aufbau - erste Edge-Einschuebe, Fake Phase, Random Delay.
    - Phase 3 (50%):    Halbzeit - mid_session_climax() mit Edging.
    - Phase 4 (60-85%): Tortur - Denial Loop Events, Chaos, Edge hochgewichtet.
    - Phase 5 (85-100%): Finale - should_trigger_final_climax() steigende Chance.

    Kategorien mit Whip als Schock:
    - welle:    [1, 3]            konstant 2.5 ueber alle Phasen
    - schock:   [9]               Whip: 1.0 + progress * 1.5 (leicht steigend 1.0 -> 2.5)
    - sanft:    [6, 10, 11, 14, 15]  Tease, Plateau, Atem, Flattern, Tropfen: 5.0 -> 0.3
    - mittel:   [4, 7, 12, 16, 17]   Standard, Random, Herzschlag, Metronom, Gezeiten: konstant 2.0
    - intensiv: [2, 5, 8, 13]     Schlagartig, Chaos, Edge, Achterbahn: 0.3 -> 4.8 (stark am Ende)
    """
    welle = [1, 3]
    schock = [9]
    sanft = [6, 10, 11, 14, 15]       # Tease, Plateau, Atem, Flattern, Tropfen
    mittel = [4, 7, 12, 16, 17]       # Standard, Random, Herzschlag, Metronom, Gezeiten
    intensiv = [2, 5, 8, 13]

    # Gewicht je nach Kategorie und Fortschritt
    welle_weight = 2.5
    schock_weight = 1.0 + progress * 1.5     # 1.0 -> 2.5
    sanft_weight = max(0.3, 5.0 - 4.7 * progress)  # 5.0 -> 0.3
    mittel_weight = 2.0
    intensiv_weight = max(0.3, 0.3 + 4.5 * progress)  # 0.3 -> 4.8

    pool = list(MODE_COUNTS.keys())
    weights = []
    for m in pool:
        if m in welle:
            base_weight = welle_weight
        elif m in schock:
            base_weight = schock_weight
        elif m in sanft:
            base_weight = sanft_weight
        elif m in mittel:
            base_weight = mittel_weight
        else:
            base_weight = intensiv_weight

        # Bonus *1.5 wenn Modus noch keine 2x gespielt wurde
        count = MODE_COUNTS.get(m, 0)
        if count < 2:
            base_weight *= 1.5
        weights.append(base_weight)

    return random.choices(pool, weights=weights, k=1)[0]

# ---------------------------------------------------------------------------
# Final-Climax-Trigger
# ---------------------------------------------------------------------------
def should_trigger_final_climax(time_left, cycle_duration):
    """Chance auf Final Climax steigt gegen Rundenende.
    In den letzten 15 Sekunden ist er garantiert.
    Wird pro Runde nur einmal ausgewertet (Guard im main-Loop),
    danach beendet die Runde. Anzahl Runden = Anzahl Orgasmen.
    """
    if time_left > 180:
        return False
    if time_left <= 15:
        return True
    window = 180.0
    progress_to_end = max(0.0, min(1.0, (window - time_left) / window))
    chance = 0.05 + progress_to_end * 0.90
    return random.random() < chance

# ---------------------------------------------------------------------------
# Final-Climax-Sequenz (einmal pro Runde, darf ueberziehen)
# ---------------------------------------------------------------------------
def final_climax_sequence():
    """Abschluss-Sequenz: Ein Orgasmus pro Runde (Make-Cum und/oder Extreme-Torture).

    Wird im main-Loop genau einmal pro Runde aufgerufen (Guard: not FINAL_CLIMAX_DONE)
    und setzt FINAL_CLIMAX_DONE=True, damit reset_run_state() beim Start der naechsten
    Runde wieder zurueckgesetzt wird. Laeuft immer vollstaendig durch - die Runde darf
    ueberziehen. Anzahl Runden = Anzahl Orgasmen in der Session.
    """
    global FINAL_CLIMAX_DONE
    FINAL_CLIMAX_DONE = True

    print("\n=== FINALE - HOEHEPUNKT ===")

    # Geschlechts-Switch-Logik
    switch_prob = 0.4 if SESSION_CYCLE_COUNT >= 2 else 0.2
    climax_gender = "F" if random.random() < switch_prob else GENDER

    if climax_gender == "F" and GENDER != "F":
        print(f"[Finale] {switch_prob:.0%}-Switch aktiv: Frauen-Profil.")

    log_event("final_climax_start", session_gender=GENDER, climax_gender=climax_gender)

    roll = random.random()
    if roll < 0.3:
        # Kombination: Make-Cum + Extreme-Torture
        if climax_gender == "F":
            make_cum(random.uniform(400, 800), reason="final_combined")
            extreme_torture(random.uniform(400, 1000), reason="final_combined")
        else:
            make_cum(random.uniform(150, 500), reason="final_combined")
            extreme_torture(random.uniform(150, 400), reason="final_combined")
    elif roll < 0.75:
        # Nur Make-Cum
        if climax_gender == "F":
            make_cum(random.uniform(400, 1000), reason="final_make_cum")
        else:
            make_cum(random.uniform(150, 500), reason="final_make_cum")
    else:
        # Nur Extreme-Torture
        if climax_gender == "F":
            extreme_torture(random.uniform(400, 1200), reason="final_extreme_torture")
        else:
            extreme_torture(random.uniform(150, 400), reason="final_extreme_torture")

    log_event("final_climax_end", session_gender=GENDER, climax_gender=climax_gender)

# ---------------------------------------------------------------------------
# Benutzereingaben
# ---------------------------------------------------------------------------
def prompt_gender():
    """Fragt das Geschlecht ab und gibt 'M' oder 'F' zurueck."""
    while True:
        raw = input("Geschlecht waehlen - Mann (M) oder Frau (F): ").strip().upper()
        if raw in ("M", "F"):
            return raw
        print("Ungueltige Eingabe. Bitte M oder F eingeben.")

def prompt_session_duration_minutes():
    """Fragt die Sitzungsdauer ab und gibt Sekunden zurueck."""
    while True:
        try:
            raw = input("Bitte Sitzungsdauer in Minuten eingeben (z.B. 90): ").strip().replace(",", ".")
            minutes = float(raw)
            if minutes <= 0:
                raise ValueError
            return minutes * 60
        except ValueError:
            print("Ungueltige Eingabe. Bitte eine Zahl groesser 0 angeben.")

def prompt_cycle_count():
    """Fragt die Anzahl kompletter Durchlaeufe (1 bis 6) ab.
    Bei 20-40 min pro Runde und bis zu 2 h Session: typisch 3-6 Runden.
    """
    while True:
        raw = input("Wie viele Durchlaeufe in der Zeit? (1-6): ").strip()
        if raw in ("1", "2", "3", "4", "5", "6"):
            return int(raw)
        print("Ungueltige Eingabe. Bitte 1 bis 6 eingeben.")

def reset_run_state():
    """Setzt den Zustandsautomaten fuer einen neuen Durchlauf zurueck."""
    global LEVEL, MODE_COUNTS, MODUS_STREAK, MID_CLIMAX_DONE, FINAL_CLIMAX_DONE
    LEVEL = 1
    MODE_COUNTS = {i: 0 for i in range(1, 18)}
    MODUS_STREAK = {}
    MID_CLIMAX_DONE = False
    FINAL_CLIMAX_DONE = False

# ---------------------------------------------------------------------------
# Modus-Dispatcher
# ---------------------------------------------------------------------------
def run_mode(mode, max_speed, duration, progress):
    """Fuehrt den ausgewaehlten Modus aus und gibt den Modusnamen zurueck."""
    if mode == 1:
        wave_mode(max_speed, duration)
        return "Welle"
    elif mode == 2:
        pulse_mode(max_speed, duration)
        return "Schlagartig"
    elif mode == 3:
        wave_mode(max_speed, duration)
        return "Welle"
    elif mode == 4:
        standard_mode(max_speed, duration)
        return "Standard"
    elif mode == 5:
        chaos_mode(max_speed, duration)
        return "Chaos"
    elif mode == 6:
        tease_mode(max_speed, duration)
        return "Tease"
    elif mode == 7:
        random_mode(max_speed, duration)
        return "Random"
    elif mode == 8:
        edge_mode(max_speed, duration)
        return "Edge"
    elif mode == 9:
        whip_mode(max_speed, duration)
        return "Whip"
    elif mode == 10:
        plateau_mode(max_speed, duration, progress)
        return "Plateau"
    elif mode == 11:
        breath_mode(max_speed, duration)
        return "Atem"
    elif mode == 12:
        heartbeat_mode(max_speed, duration)
        return "Herzschlag"
    elif mode == 13:
        rollercoaster_mode(max_speed, duration)
        return "Achterbahn"
    elif mode == 14:
        flutter_mode(max_speed, duration)
        return "Flattern"
    elif mode == 15:
        drip_mode(max_speed, duration)
        return "Tropfen"
    elif mode == 16:
        metronome_mode(max_speed, duration)
        return "Metronom"
    elif mode == 17:
        tide_mode(max_speed, duration)
        return "Gezeiten"
    else:
        # Fallback
        wave_mode(max_speed, duration)
        return "Welle"

# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------
def main():
    """Hauptprogramm"""
    global LEVEL, MODUS_STREAK, SESSION_DURATION, MID_CLIMAX_DONE, FINAL_CLIMAX_DONE
    global GENDER, ORIGINAL_GENDER, SESSION_CYCLE_COUNT, SESSION_MODE_COUNTS

    test_vibrator()
    GENDER = prompt_gender()
    ORIGINAL_GENDER = GENDER
    apply_gender_config()
    print(f"[Konfiguration] Geschlecht: {'Frau' if GENDER == 'F' else 'Mann'}")
    SESSION_DURATION = prompt_session_duration_minutes()
    cycle_count = prompt_cycle_count()
    SESSION_CYCLE_COUNT = cycle_count
    SESSION_MODE_COUNTS = {i: 0 for i in range(1, 18)}
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
        next_round_female = False  # Straf-Runde (M->F) fuer die naechste Runde
        for cycle_idx in range(1, cycle_count + 1):
            reset_run_state()
            # Temporaerer Gender-Switch: Maenner in der naechsten Runde ins
            # intensivere Frauen-Profil zwingen (laengere Dauer, kuerzere
            # Erholung, laengerer Make-Cum) - reine Quaelerei.
            if next_round_female and ORIGINAL_GENDER == "M":
                GENDER = "F"
                apply_gender_config()
                print("[Straf-Runde] Frauen-Profil aktiv - wird laenger und intensiver.")
                log_event("gender_switch_round", cycle=cycle_idx,
                          original_gender=ORIGINAL_GENDER, active_gender="F")
            else:
                GENDER = ORIGINAL_GENDER
                apply_gender_config()
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

                # --- Final Climax: genau einmal pro Runde, dann Runde beenden ---
                # Eine Runde = ein garantierter Orgasmus (final_climax).
                # Die Runde darf ueberziehen, wenn final_climax laenger laeuft;
                # danach wird die Runde beendet und resetet (naechste Runde).
                # Anzahl Runden = Anzahl Orgasmen in der Session.
                if not FINAL_CLIMAX_DONE and should_trigger_final_climax(time_left, cycle_duration):
                    final_climax_sequence()
                    break  # Runde beenden -> reset_run_state() -> naechste Runde

                # Halbzeit-Edging (FEATURE 2)
                if not MID_CLIMAX_DONE and elapsed >= cycle_duration / 2:
                    mid_session_climax()
                    elapsed = time.time() - start_time
                    time_left = cycle_duration - elapsed

                # Fortschritt berechnen (0.0 = Anfang, 1.0 = Ende)
                progress = min(1.0, elapsed / cycle_duration)

                # Sadistischer Edge als Quael-Event ab 60% (kein Orgasmus).
                # Ersetzt die frueheren zufaelligen extreme_torture-Events.
                if progress >= 0.6 and random.random() < EVENT_PROB["sadistic_edge"]:
                    sadistic_edge_mode(duration=random.uniform(40, 90))
                    continue

                # --- FEATURE 6: Denial Loop Zufalls-Event in Phase 4 ---
                if 0.6 <= progress <= 0.85 and random.random() < 0.08:
                    denial_loop_mode()
                    continue

                # Zufaellige Events
                if random.random() < EVENT_PROB["fake_phase"]:
                    fake_phase()
                if random.random() < EVENT_PROB["random_delay"]:
                    random_delay()

                # Zeitlimit-Check nach Events
                elapsed = time.time() - start_time
                time_left = cycle_duration - elapsed
                if time_left <= 5:
                    # Sehr wenig Zeit - nur noch kurze Modis
                    break

                max_speed, duration, recovery = calculate_parameters_with_time(LEVEL, last_modus, time_left)

                mode = select_mode(progress)
                current_modus = run_mode(mode, max_speed, duration, progress)

                MODE_COUNTS[mode] = MODE_COUNTS.get(mode, 0) + 1
                SESSION_MODE_COUNTS[mode] = SESSION_MODE_COUNTS.get(mode, 0) + 1

                # Streak-System
                if last_modus == current_modus:
                    MODUS_STREAK[current_modus] = MODUS_STREAK.get(current_modus, 0) + 1
                else:
                    MODUS_STREAK[current_modus] = 1
                last_modus = current_modus

                # Surprise-Edging statt zufaelligem Orgasmus.
                # Orgasmen gibt es nur einmal pro Runde ueber final_climax,
                # daher wird das fruehere zufaellige make_cum durch Denial ersetzt.
                if progress >= 0.5 and random.random() < EVENT_PROB["make_cum"]:
                    denial_loop_mode(rounds=random.randint(2, 3), start_peak=85)

                # Pflicht-Recovery nach intensiven Modi
                if current_modus in ("Edge", "Chaos", "Schlagartig", "Achterbahn"):
                    intense_floor = 30 if GENDER == "F" else 60
                    min_intense_recovery = max(recovery, intense_floor)
                    print(f"[Intensive Erholung] {min_intense_recovery:.1f}s nach {current_modus}")
                    do_recovery(min_intense_recovery)
                else:
                    print(f"Erholung: {recovery:.1f}s")
                    do_recovery(recovery)

                cycle_peak_level = max(cycle_peak_level, LEVEL)

                # BUG 4 FIX: Doppeltes LEVEL += entfernt, nur LEVEL += 1.3 in if-Logik
                # Level erhoehen oder zuruecksetzen
                if random.random() < 0.85:
                    LEVEL += 1.3
                    print(f"Level auf {LEVEL:.1f} gestiegen!")
                elif random.random() < EVENT_PROB["level_reset"]:
                    LEVEL = 1
                    print("[UEberraschung] Level auf 1 zurueckgesetzt!")
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
            # Gender-Switch fuer die naechste Runde (nur Maenner quaelen):
            # 25% Chance, dass die naechste Runde im intensiveren Frauen-Profil
            # laeuft. Der Orgasmus kommt weiterhin durch final_climax - die
            # Straf-Runde verlaengert/intensiviert nur den Weg dorthin.
            if ORIGINAL_GENDER == "M" and cycle_idx < cycle_count:
                if random.random() < 0.25:
                    next_round_female = True
                    print("[Quaelerei] Naechste Runde im Frauen-Profil!")
                    log_event("gender_switch_announce", next_cycle=cycle_idx + 1, active_gender="F")
                else:
                    next_round_female = False
            if cycle_idx < cycle_count:
                reset_pause = random.uniform(30, 90)
                pwm.ChangeDutyCycle(0)
                print(f"[Reset] Pause vor neuem Durchlauf: {reset_pause:.0f}s")
                log_event("cycle_reset_pause", cycle=cycle_idx, total_cycles=cycle_count, pause_seconds=round(reset_pause, 2))
                time.sleep(reset_pause)
    finally:
        # GENDER auf Original zuruecksetzen (falls eine Straf-Runde aktiv war)
        GENDER = ORIGINAL_GENDER
        apply_gender_config()
        pwm.stop()
        GPIO.cleanup()
        minutes_total = SESSION_DURATION / 60
        print(f"Sitzungsdauer von {minutes_total:.1f} Minuten pro Durchlauf erreicht. Programm beendet.")
        save_session_log()
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
