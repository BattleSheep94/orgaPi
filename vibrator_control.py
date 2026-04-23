# coding: utf8
# Programm zur Steuerung eines Vibrators mit PWM auf einem Raspberry Pi mit PCB-Adapter
# Nutzt GPIO 21 (BCM, PCB-Adapter: primäre Steuerung) für alle Modi
# Unterstützt Welle-, Slow-Wave-, Schlagartig-, Standard-, Chaos-, Tease-, Random-, Edge-, Whip- und Plateau-Modi sowie Make-Cum und Extreme-Torture
# Whip-Modus: Levelabhängige Hiebe, 100% Intensität, Pausen 2–8 s, Impulsdauer 0.2–0.6 s
# Korrektur: SyntaxError in print-Anweisungen, f-Strings ohne deutsche Punkte

# Falls das Skript auf einem Nicht-Raspberry-System ausgeführt wird (z.B. Windows),
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

# GPIO-Setup (BCM-Modus für Pin-Nummerierung)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Pin für PWM auf dem PCB-Adapter
PRIMARY_PWM_PIN = 21  # GPIO 21 (BCM, PCB-Adapter: primäre Steuerung)
GPIO.setup(PRIMARY_PWM_PIN, GPIO.OUT)

# PWM mit 50 Hz initialisieren
pwm = GPIO.PWM(PRIMARY_PWM_PIN, 50)
pwm.start(0)

# Globale Variablen
LEVEL = 1  # Aktuelles Level, beeinflusst Intensität
SESSION_DURATION = 10800  # Wird bei Programmstart durch Benutzereingabe überschrieben
BASE_PROBABILITIES = {
    "make_cum": 0.10,
    "extreme_torture": 0.015,
    "level_reset": 0.05,
    "fake_phase": 0.05,
    "pieks": 0.10,
    "random_delay": 0.05,
    "tease_burst": 0.10,
}
EVENT_PROB = BASE_PROBABILITIES.copy()
MODE_COUNTS = {i: 0 for i in range(1, 11)}  # Jeder Modus soll mindestens 2x vorkommen
MODUS_STREAK = {}  # Verfolgt, wie oft ein Modus hintereinander ausgewählt wurde
MID_CLIMAX_DONE = False  # Make-Cum zur Halbzeit
FINAL_CLIMAX_DONE = False  # Abschluss-Sequenz am Ende

def clamp_prob(value, upper=0.7):
    """Beschränkt Wahrscheinlichkeiten auf einen sinnvollen Bereich."""
    return max(0.0, min(value, upper))


def rescale_probabilities():
    """Skaliert alle Wahrscheinlichkeiten passend zur tatsächlichen Sitzungsdauer."""
    # Keine Skalierung mehr nötig - BASE_SESSION wurde entfernt
    for key, base in BASE_PROBABILITIES.items():
        EVENT_PROB[key] = clamp_prob(base)

def test_vibrator():
    """Testet den Vibrator für 2 Sekunden auf 50% Intensität"""
    print("[Test] Vibrator-Test gestartet...")
    pwm.ChangeDutyCycle(80)
    time.sleep(2)
    pwm.ChangeDutyCycle(0)
    print("[Test] Vibrator-Test beendet.")

def fake_phase():
    """Täuscht den Start einer neuen Phase vor (2 Sekunden wechselnde Intensität)"""
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
    """Verzögert Modusstart ohne Meldungen (5–20 Sekunden)"""
    delay_time = random.uniform(5, 20)
    time.sleep(delay_time)

def wave_mode(max_speed, duration):
    """Modus: Welle - Langsames Auf- und Abschwellen der Intensität"""
    print(f"[Welle] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    for i in range(0, max_speed, 1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.02)
    time.sleep(duration)
    for i in range(max_speed, -1, -1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.02)
    pwm.ChangeDutyCycle(0)

def slow_wave_mode(max_speed, duration):
    """Modus: Slow Wave - Sehr langsames Auf- und Abschwellen der Intensität"""
    print(f"[Slow Wave] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    for i in range(0, max_speed, 1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.05)
    time.sleep(duration)
    for i in range(max_speed, -1, -1):
        pwm.ChangeDutyCycle(i)
        time.sleep(0.05)
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
    """Modus: Standard - Konstante Geschwindigkeit für die angegebene Dauer"""
    print(f"[Standard] Konstante Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    pwm.ChangeDutyCycle(max_speed)
    time.sleep(duration)
    pwm.ChangeDutyCycle(0)

def chaos_mode(max_speed, duration):
    """Modus: Chaos - Zufällige Intensitätsspitzen mit kurzen Pausen"""
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
        edge_max = int(max_speed * 0.95)
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
    """Modus: Whip - Simuliert Peitschenhiebe mit levelabhängigen Impulsen bei 100%"""
    print(f"[Whip] Dauer: {duration:.1f}s")
    num_whips = random.randint(3 + (LEVEL - 1) // 3, min(8 + (LEVEL - 1) // 2, 20))  # Levelabhängige Hiebe
    elapsed = 0
    for _ in range(num_whips):
        if elapsed >= duration:
            break
        intensity = 100  # Immer 100% Intensität
        whip_duration = random.uniform(0.2, 0.6)  # Kurzer Impuls (0.2–0.6 s)
        print("[Whip] Spür den Hieb!")
        pwm.ChangeDutyCycle(intensity)
        time.sleep(whip_duration)
        pwm.ChangeDutyCycle(0)
        pause_time = random.uniform(2, 8)  # Pause zwischen Hieben
        time.sleep(pause_time)
        elapsed += whip_duration + pause_time
    pwm.ChangeDutyCycle(0)

def plateau_mode(max_speed, duration, progress):
    """Modus: Plateau - Moderate Dauerstimulation, steigert sich mit Session-Fortschritt.
    Am Anfang schwach (20-40%), später intensiver (40-60%)."""
    low = int(20 + 20 * progress)   # 20% -> 40%
    high = int(40 + 20 * progress)  # 40% -> 60%
    plateau_intensity = random.randint(low, max(low, min(high, max_speed)))
    print(f"[Plateau] Intensität: {plateau_intensity}%, Dauer: {duration:.1f}s (Fortschritt: {progress:.0%})")
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

def random_mode(max_speed, duration):
    """Modus: Random - Zufällige Kombination von Elementen anderer Modi"""
    print(f"[Random] Max Geschwindigkeit: {max_speed}%, Dauer: {duration:.1f}s")
    elapsed = 0
    while elapsed < duration:
        sub_mode = random.choice([wave_mode, slow_wave_mode, pulse_mode, chaos_mode, whip_mode])
        sub_duration = random.uniform(1, 3)
        sub_mode(max_speed, sub_duration)
        elapsed += sub_duration
    pwm.ChangeDutyCycle(0)

def make_cum():
    """Make-Cum: Längere, variable Pulse mit Überraschungselementen"""
    print("[Make-Cum] Achtung: Intensive und unvorhersehbare Phase!")
    num_pulses = random.randint(10, 20)
    total_duration = 0
    speeds = list(range(80, 101))
    weights = [1 + (i / 20) * (LEVEL - 1) / 5 for i in range(len(speeds))]
    for i in range(num_pulses):
        max_intensity = random.choices(speeds, weights=weights, k=1)[0]
        sleep_time = random.uniform(0.005, 0.015)
        if random.random() < 0.1:
            print("[Überraschungspuls] Maximale Intensität!")
            max_intensity = 100
            sleep_time = 0.005
        for j in range(0, max_intensity, 10):
            pwm.ChangeDutyCycle(j)
            time.sleep(sleep_time)
        hold_time = random.uniform(0.5, 1.5)
        time.sleep(hold_time)
        for j in range(max_intensity, -1, -10):
            pwm.ChangeDutyCycle(j)
            time.sleep(sleep_time)
        if i < num_pulses - 1:
            pause_time = random.uniform(0.2, 0.8)
            time.sleep(pause_time)
            total_duration += (max_intensity // 10 + 1) * sleep_time + hold_time + (max_intensity // 10 + 1) * sleep_time + pause_time
        else:
            total_duration += (max_intensity // 10 + 1) * sleep_time + hold_time + (max_intensity // 10 + 1) * sleep_time
    print(f"[Make-Cum] Gesamtdauer: {total_duration:.1f}s")
    pwm.ChangeDutyCycle(0)

def extreme_torture():
    """Extreme-Torture: Motor läuft 60 Sekunden auf 100%"""
    print("[Extreme Torture] Motor auf 100% für 60 Sekunden!")
    pwm.ChangeDutyCycle(100)
    time.sleep(60)
    pwm.ChangeDutyCycle(0)

def random_pulse():
    """Zufälliger kurzer Impuls (0.2s oder 1s Pieks) bei 100%"""
    pulse_prob = 0.05 + LEVEL * 0.01
    if random.random() < pulse_prob:
        if random.random() < EVENT_PROB["pieks"]:
            print("[Pieks] 1-Sekunden-Impuls bei 100%!")
            pwm.ChangeDutyCycle(100)
            time.sleep(1)
            pwm.ChangeDutyCycle(0)
        else:
            print("[Random Pulse] Kurzer Impuls bei 100%!")
            pwm.ChangeDutyCycle(100)
            time.sleep(0.2)
            pwm.ChangeDutyCycle(0)

def recovery_with_pulses(recovery_time):
    """Erholungsphase mit 0 bis 2 zufälligen Impulsen und möglichem Tease Burst"""
    burst_time = random.uniform(0, recovery_time)
    if random.random() < EVENT_PROB["tease_burst"]:
        burst_time = random.uniform(0, recovery_time)
        pulse_times = sorted([random.uniform(0, recovery_time) for _ in range(random.randint(0, 2))] + [burst_time])
    else:
        pulse_times = sorted([random.uniform(0, recovery_time) for _ in range(random.randint(0, 2))])
    pulse_times.append(recovery_time)
    current_time = 0
    for pt in pulse_times:
        time_to_next = pt - current_time
        if time_to_next > 0:
            time.sleep(time_to_next)
        if pt < recovery_time:
            if burst_time is not None and pt == burst_time and random.random() < EVENT_PROB["tease_burst"]:
                print("[Tease Burst] Überraschung! Jetzt warten...")
                pwm.ChangeDutyCycle(100)
                time.sleep(0.5)
                pwm.ChangeDutyCycle(0)
                extra_pause = random.uniform(10, 30)
                print(f"[Tease Burst] Zusätzliche Pause: {extra_pause:.1f}s")
                time.sleep(extra_pause)
            else:
                random_pulse()
        current_time = pt

# Mindestpause, damit sich der Körper zuverlässig beruhigen kann,
# auch wenn nur sehr kurz gelaufen wurde oder die Sitzung fast vorbei ist.
MIN_CALM_RECOVERY = 45
# Verhältnis Pause : Laufzeit. Die Pause soll deutlich länger sein als die
# vorangegangene Motorphase, damit wirklich Erholung stattfindet.
RECOVERY_DURATION_RATIO_MIN = 15
RECOVERY_DURATION_RATIO_MAX = 30
RECOVERY_UPPER_CAP = 300


def _recovery_for_duration(duration, level):
    """Leitet eine Erholungspause aus der tatsächlichen Motor-Laufzeit ab.

    Plan: Die Pause muss immer ausreichen, um sich zu beruhigen. Daher wird sie
    an die zuletzt gelaufene Laufzeit gekoppelt (15-30x) und mit einem Level-
    abhängigen Mindestwert versehen, damit sie auch bei sehr kurzen Pulsen
    nicht zu knapp wird.
    """
    level_floor = min(MIN_CALM_RECOVERY + (level - 1) * 4, 120)
    min_recovery = max(level_floor, duration * RECOVERY_DURATION_RATIO_MIN)
    max_recovery = min(
        max(min_recovery + 30, duration * RECOVERY_DURATION_RATIO_MAX),
        RECOVERY_UPPER_CAP,
    )
    return random.uniform(min_recovery, max_recovery)


def calculate_parameters(level, streak_modus):
    """Berechnet Zufallsparameter basierend auf dem aktuellen Level und Streak.

    Plan: Die Motor-Laufzeit steigert sich LANGSAM mit dem Level (gedämpfter
    Anstieg via sqrt), während die Erholungspause immer lang genug bleibt, um
    sich wirklich zu beruhigen - auch nach Streak-/Variation-Verlängerungen.
    """
    speeds = list(range(80, 101))
    weights = [1 + (i / 20) * (level - 1) / 5 for i in range(len(speeds))]
    max_speed = random.choices(speeds, weights=weights, k=1)[0]

    # Gedämpfter Anstieg: am Anfang schnell spürbar, später nur noch langsam.
    # Level 1 -> 0, Level 5 -> ~3, Level 10 -> 4.5, Level 20 -> ~6.5
    level_boost = max(0.0, (level - 1)) ** 0.5 * 1.5
    min_duration = 1 + level_boost * 0.5
    max_duration = 5 + level_boost * 1.0
    duration = random.uniform(min_duration, max_duration)

    if random.random() < 0.05:
        duration *= 1.5
        max_speed = min(100, max_speed + 10)
        print(f"[Variation] Modusvariante: Dauer {duration:.1f}s, Intensität {max_speed}%")

    if MODUS_STREAK.get(streak_modus, 0) >= 3:
        if random.random() < 0.5:
            max_speed = min(100, max_speed + 10)
            print(f"[Streak] Intensität erhöht auf {max_speed}%")
        else:
            duration *= 1.5
            print(f"[Streak] Dauer erhöht auf {duration:.1f}s")

    # Erholung wird erst NACH allen Dauer-Modifikationen berechnet, damit eine
    # verlängerte Motorphase auch eine entsprechend längere Pause nach sich zieht.
    recovery = _recovery_for_duration(duration, level)

    return max_speed, duration, recovery


def calculate_parameters_with_time(level, streak_modus, time_left):
    """Wie calculate_parameters, aber begrenzt Dauer/Erholung an verbleibende Zeit.

    Wichtig: Die Erholung wird NIE unter MIN_CALM_RECOVERY gekürzt, damit die
    Pause auch am Sitzungsende noch zum Beruhigen ausreicht.
    """
    max_speed, duration, recovery = calculate_parameters(level, streak_modus)
    # Laufzeit an Restzeit anpassen (min. 3s, damit ein Modus überhaupt Sinn ergibt).
    duration = min(duration, max(3, time_left * 0.25))
    # Erholung an Restzeit anpassen, aber nie unter den Beruhigungs-Boden.
    recovery = min(recovery, max(MIN_CALM_RECOVERY, time_left * 0.4))
    return max_speed, duration, recovery


def mid_session_climax():
    """Make-Cum zur Halbzeit der Session."""
    global MID_CLIMAX_DONE
    if MID_CLIMAX_DONE:
        return
    MID_CLIMAX_DONE = True
    print("\n=== HALBZEIT - HÖHEPUNKT ===")
    make_cum()
    pause = random.uniform(60, 120)  # 1-2 Minuten Erholung nach Halbzeit-Climax
    print(f"[Halbzeit] Erholung für {pause:.0f}s.")
    pwm.ChangeDutyCycle(0)
    time.sleep(pause)


def select_mode(progress):
    """Wählt einen Modus basierend auf Session-Fortschritt (0.0 = Anfang, 1.0 = Ende).
    
    Am Anfang werden sanfte Modi bevorzugt, gegen Ende intensive Modi.
    Modi-Kategorien:
    - Sanft (Anfang): 1=Welle, 3=Slow Wave, 6=Tease, 9=Whip, 10=Plateau
    - Mittel: 4=Standard, 7=Random
    - Intensiv (Ende): 2=Schlagartig, 5=Chaos, 8=Edge
    """
    sanft = [1, 3, 6, 9, 10]  # Welle, Slow Wave, Tease, Whip, Plateau
    mittel = [4, 7]           # Standard, Random
    intensiv = [2, 5, 8]     # Schlagartig, Chaos, Edge
    
    # Gewichtung basierend auf Fortschritt
    # Anfang (progress=0): sanft=5, mittel=2, intensiv=0.5
    # Ende (progress=1): sanft=0.5, mittel=2, intensiv=5
    sanft_weight = max(0.5, 5 - 4.5 * progress)
    mittel_weight = 2
    intensiv_weight = max(0.5, 0.5 + 4.5 * progress)
    
    pool = list(MODE_COUNTS.keys())
    weights = []
    for m in pool:
        if m in sanft:
            base_weight = sanft_weight
        elif m in mittel:
            base_weight = mittel_weight
        else:
            base_weight = intensiv_weight
        
        # Bonus für Modi die noch nicht 2x vorkamen
        count = MODE_COUNTS.get(m, 0)
        if count < 2:
            base_weight *= 1.5
        weights.append(base_weight)
    
    return random.choices(pool, weights=weights, k=1)[0]


def final_climax_sequence():
    """Abschluss-Sequenz: Make-Cum gefolgt von Extreme-Torture."""
    global FINAL_CLIMAX_DONE
    if FINAL_CLIMAX_DONE:
        return
    FINAL_CLIMAX_DONE = True
    print("\n=== FINALE - HÖHEPUNKT ===")
    make_cum()
    pause = random.uniform(10, 30)
    print(f"[Finale] Kurze Pause vor dem Abschluss: {pause:.0f}s")
    time.sleep(pause)
    extreme_torture()

def prompt_session_duration_minutes():
    """Fragt die Sitzungsdauer ab und gibt Sekunden zurück."""
    while True:
        try:
            raw = input("Bitte Sitzungsdauer in Minuten eingeben (z.B. 90): ").strip().replace(",", ".")
            minutes = float(raw)
            if minutes <= 0:
                raise ValueError
            return minutes * 60
        except ValueError:
            print("Ungültige Eingabe. Bitte eine Zahl größer 0 angeben.")

def main():
    """Hauptprogramm"""
    global LEVEL, MODUS_STREAK, SESSION_DURATION, MID_CLIMAX_DONE, FINAL_CLIMAX_DONE
    test_vibrator()
    SESSION_DURATION = prompt_session_duration_minutes()
    rescale_probabilities()

    print("Anwendung starten? (Y/N)")
    start = input().strip().upper()
    if start not in ["Y", "J"]:
        print("Anwendung nicht gestartet.")
        sys.exit(0)

    start_time = time.time()
    last_modus = None
    try:
        while True:
            elapsed = time.time() - start_time
            time_left = SESSION_DURATION - elapsed
            
            # Finale Sequenz in den letzten 2 Minuten
            if time_left <= 120 and not FINAL_CLIMAX_DONE:
                final_climax_sequence()
                break
            
            # Make-Cum zur Halbzeit
            if not MID_CLIMAX_DONE and elapsed >= SESSION_DURATION / 2:
                mid_session_climax()
                elapsed = time.time() - start_time
                time_left = SESSION_DURATION - elapsed

            # Fortschritt berechnen (0.0 = Anfang, 1.0 = Ende)
            progress = min(1.0, elapsed / SESSION_DURATION)

            if progress >= 0.4 and random.random() < EVENT_PROB["extreme_torture"]:
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
                slow_wave_mode(max_speed, duration)
                current_modus = "Slow Wave"
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

            # Streak-System: Verfolge Wiederholungen
            if last_modus == current_modus:
                MODUS_STREAK[current_modus] = MODUS_STREAK.get(current_modus, 0) + 1
            else:
                MODUS_STREAK[current_modus] = 1
            last_modus = current_modus

            # Zufälliger Impuls nach dem Modus mit 10% Wahrscheinlichkeit
            if random.random() < 0.1:
                random_pulse()

            # Make-Cum nur ab 40% Session-Fortschritt
            if progress >= 0.4 and random.random() < EVENT_PROB["make_cum"]:
                make_cum()

            # Pflicht-Recovery nach intensiven Modi (Edge, Chaos, Schlagartig)
            if current_modus in ("Edge", "Chaos", "Schlagartig"):
                min_intense_recovery = max(recovery, 60)  # Mindestens 60s nach intensiven Modi
                print(f"[Intensive Erholung] {min_intense_recovery:.1f}s nach {current_modus}")
                recovery_with_pulses(min_intense_recovery)
            else:
                print(f"Erholung: {recovery:.1f}s")
                recovery_with_pulses(recovery)

            # Level erhöhen oder zurücksetzen
            if random.random() < 0.3:
                LEVEL += 1.3
                print(f"Level auf {LEVEL:.1f} gestiegen!")
            elif random.random() < EVENT_PROB["level_reset"]:
                LEVEL = 1
                print("[Überraschung] Level auf 1 zurückgesetzt!")
    finally:
        pwm.stop()
        GPIO.cleanup()
        minutes_total = SESSION_DURATION / 60
        print(f"Sitzungsdauer von {minutes_total:.1f} Minuten erreicht. Programm beendet.")

if __name__ == "__main__":
    main()