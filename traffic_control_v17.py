
import Adafruit_BBIO.GPIO as GPIO
import time

light_pins = {
    '120E_R': 'P8_14', '120E_Y': 'P8_16', '120E_G': 'P8_18',
    '120W_R': 'P8_15', '120W_Y': 'P8_17', '120W_G': 'P8_19',
    'Martin_R': 'P8_8', 'Martin_Y': 'P8_10', 'Martin_G': 'P8_12',
    'TechPkwy_R': 'P8_7', 'TechPkwy_Y': 'P8_9', 'TechPkwy_G': 'P8_11',
    'Turn_Tech': 'P8_26', 'Turn_Martin': 'P8_27', 'Turn_120W': 'P8_28'
}

sensor_pins = {
    'Martin_Short': 'P9_12', 'Martin_Long': 'P9_15',
    'TechPkwy_Short': 'P9_41', 'TechPkwy_Long': 'P9_42',
    '120E_Short': 'P9_23', '120E_Long': 'P9_27',
    '120W_Short': 'P9_25', '120W_Long': 'P9_30',
    'Turn_Tech': 'P8_29', 'Turn_Martin': 'P8_30', 'Turn_120W': 'P8_31'
}

def setup_gpio():
    for pin in light_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    for pin in sensor_pins.values():
        GPIO.setup(pin, GPIO.IN)

def set_light_group(group, r, y, g):
    GPIO.output(light_pins[f'{group}_R'], r)
    GPIO.output(light_pins[f'{group}_Y'], y)
    GPIO.output(light_pins[f'{group}_G'], g)

def all_red():
    for group in ['120E', '120W', 'Martin', 'TechPkwy']:
        set_light_group(group, GPIO.HIGH, GPIO.LOW, GPIO.LOW)

def run_transition(from_groups, to_groups, delay=2, yellow=3):
    for g in from_groups:
        set_light_group(g, GPIO.LOW, GPIO.HIGH, GPIO.LOW)
    time.sleep(yellow)
    for g in from_groups + to_groups:
        set_light_group(g, GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    time.sleep(delay)
    for g in to_groups:
        set_light_group(g, GPIO.LOW, GPIO.LOW, GPIO.HIGH)

def display_status(direction):
    print(f"💡 CURRENT GREEN: {direction}")

def wait_with_possible_long_cut(start_wait, long_sensors):
    start = time.time()
    while time.time() - start < start_wait:
        for sensor in long_sensors:
            if GPIO.input(sensor_pins[sensor]) == 0:
                print(f"Long sensor {sensor} detected — cutting delay.")
                return max(5, (time.time() - start) + (start_wait * 0.25))
        time.sleep(0.2)
    return start_wait

def run_turn_phase(name, light_key, sensor_key):
    if GPIO.input(sensor_pins[sensor_key]) == 0:
        print(f"{name} triggered. Turning on turn signal.")
        GPIO.output(light_pins[light_key], GPIO.HIGH)
        time.sleep(15)
        GPIO.output(light_pins[light_key], GPIO.LOW)
        return True
    return False

def monitor_y_green(max_duration=45, active_turns=[]):
    start = time.time()
    triggered_time = None
    while True:
        elapsed = time.time() - start
        if elapsed >= max_duration:
            break
        print(f"[Y GREEN] {max_duration - elapsed:.1f}s remaining")
        if GPIO.input(sensor_pins['120E_Long']) == 0 or GPIO.input(sensor_pins['120W_Long']) == 0:
            if not triggered_time:
                triggered_time = time.time()
                print("120 long sensor pressure started")
            elif time.time() - triggered_time >= 5:
                print("120 pressure sustained. Ending early.")
                return elapsed + max(3, max_duration * 0.25)
        else:
            triggered_time = None
        for key in active_turns:
            GPIO.output(light_pins[key], GPIO.HIGH)
        time.sleep(0.25)
        for key in active_turns:
            GPIO.output(light_pins[key], GPIO.LOW)
        time.sleep(0.25)
    return max_duration

def run_y_cycle():
    run_transition(['120E', '120W'], [], delay=2, yellow=3)
    display_status("Martin & Tech")
    turn_tech = run_turn_phase("Tech turn", 'Turn_Tech', 'Turn_Tech')
    turn_martin = run_turn_phase("Martin turn", 'Turn_Martin', 'Turn_Martin')
    turn_blinks = []
    if turn_tech:
        turn_blinks.append('Turn_Tech')
    if turn_martin:
        turn_blinks.append('Turn_Martin')
    set_light_group('Martin', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    set_light_group('TechPkwy', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    monitor_y_green(max_duration=45, active_turns=turn_blinks)
    run_transition(['Martin', 'TechPkwy'], [], delay=5, yellow=4)
    run_turn_phase("120W turn", 'Turn_120W', 'Turn_120W')
    run_transition([], ['120E', '120W'], delay=1, yellow=0)
    display_status("120E & 120W")

def control_traffic():
    setup_gpio()
    set_light_group('120E', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    set_light_group('120W', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    set_light_group('Martin', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    set_light_group('TechPkwy', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    display_status("120E & 120W")
    while True:
        print("Watching Martin/Tech short sensors...")
        while True:
            if GPIO.input(sensor_pins['Martin_Short']) == 0 or GPIO.input(sensor_pins['TechPkwy_Short']) == 0:
                delay = wait_with_possible_long_cut(45, ['Martin_Long', 'TechPkwy_Long'])
                print(f"Delaying {delay:.1f}s before Martin/Tech green")
                time.sleep(delay)
                break
            time.sleep(0.2)
        run_y_cycle()

if __name__ == "__main__":
    try:
        control_traffic()
    except KeyboardInterrupt:
        print("Shutting down.")
        all_red()
