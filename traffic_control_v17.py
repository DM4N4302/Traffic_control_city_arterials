import Adafruit_BBIO.GPIO as GPIO
import time
import _thread

light_pins = {
    '120_R': 'P8_14', '120_Y': 'P8_16', '120_G': 'P8_18',
    'MT_R': 'P8_8', 'MT_Y': 'P8_10', 'MT_G': 'P8_12',
    'Turn_Tech_R': 'P8_7', 'Turn_Tech_Y': 'P8_9', 'Turn_Tech_G': 'P8_11',
    'Turn_120W_R': 'P8_13', 'Turn_120W_Y': 'P8_17', 'Turn_120W_G': 'P8_19',
    'Turn_120E_R': 'P9_11', 'Turn_120E_Y': 'P9_13', 'Turn_120E_G': 'P9_15'
}

sensor_pins = {
    'Martin_Short': 'P9_12',
    'TechPkwy_Short': 'P9_23',
    'TechPkwy_Long': 'P9_18',
    '120E_Short': 'P9_27',
    '120E_Long': 'P9_30',
    '120W_Short': 'P9_41',
    '120W_Long': 'P9_42',
    'Turn_Tech': 'P9_14',
    'Turn_120W': 'P9_26',
    'Turn_120E': 'P9_23'
}

flashing_turns = {
    'Turn_Tech': False,
    'Turn_120W': False,
    'Turn_120E': False
}

turn_in_progress = False  # Flag to pause straight cycle timers during turn green

def setup_gpio():
    for pin in light_pins.values():
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
    for pin in sensor_pins.values():
        GPIO.setup(pin, GPIO.IN)

def set_group_lights(group, r, y, g):
    GPIO.output(light_pins[f"{group}_R"], r)
    GPIO.output(light_pins[f"{group}_Y"], y)
    GPIO.output(light_pins[f"{group}_G"], g)

def flash_turn(turn_group, straight_group):
    flashing_turns[turn_group] = True
    GPIO.output(light_pins[f"{turn_group}_R"], GPIO.LOW)
    GPIO.output(light_pins[f"{turn_group}_G"], GPIO.LOW)
    while flashing_turns[turn_group] and GPIO.input(light_pins[f"{straight_group}_G"]) == 1:
        GPIO.output(light_pins[f"{turn_group}_Y"], GPIO.HIGH)
        time.sleep(0.4)
        GPIO.output(light_pins[f"{turn_group}_Y"], GPIO.LOW)
        time.sleep(0.4)
    GPIO.output(light_pins[f"{turn_group}_Y"], GPIO.LOW)
    GPIO.output(light_pins[f"{turn_group}_R"], GPIO.HIGH)
    flashing_turns[turn_group] = False

def sustained_low(pin, seconds=5):
    start = time.time()
    while time.time() - start < seconds:
        if GPIO.input(pin) == 1:
            return False
        time.sleep(0.1)
    return True

def handle_turn_request(turn_group, straight_group, opposing_group):
    global turn_in_progress
    if GPIO.input(light_pins[f"{straight_group}_R"]) != 1:
        return
    turn_in_progress = True
    flashing_turns[turn_group] = False
    time.sleep(0.3)
    set_group_lights(turn_group, GPIO.HIGH, GPIO.LOW, GPIO.LOW)

    if GPIO.input(light_pins[f"{opposing_group}_G"]) == 1:
        set_group_lights(opposing_group, GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        time.sleep(3)
        set_group_lights(opposing_group, GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        time.sleep(2)

    time.sleep(2)
    set_group_lights(turn_group, GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    print(f"[TURN GREEN] {turn_group} green for 15s")
    time.sleep(15)

    set_group_lights(turn_group, GPIO.LOW, GPIO.HIGH, GPIO.LOW)
    time.sleep(3)
    set_group_lights(turn_group, GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    time.sleep(2)
    set_group_lights(straight_group, GPIO.LOW, GPIO.LOW, GPIO.HIGH)

    print(f"[TURN END] {turn_group} resumes flashing")
    _thread.start_new_thread(flash_turn, (turn_group, straight_group))
    turn_in_progress = False

def monitor_turn_requests():
    while True:
        if GPIO.input(light_pins['120_R']) == GPIO.HIGH:
            if sustained_low(sensor_pins['Turn_120W'], 5):
                handle_turn_request('Turn_120W', '120', 'MT')
            elif sustained_low(sensor_pins['Turn_120E'], 5):
                handle_turn_request('Turn_120E', '120', 'MT')
        if GPIO.input(light_pins['MT_R']) == GPIO.HIGH:
            if sustained_low(sensor_pins['Turn_Tech'], 5):
                handle_turn_request('Turn_Tech', 'MT', '120')
        time.sleep(0.5)

def wait_for_MT_request():
    start = time.time()
    while time.time() - start < 45:
        if turn_in_progress:
            start = time.time()  # reset timer after turn
        if sustained_low(sensor_pins['Martin_Short'], 5):
            return True
        if sustained_low(sensor_pins['TechPkwy_Short'], 5) or sustained_low(sensor_pins['TechPkwy_Long'], 5):
            return True
        time.sleep(0.2)
    return False

def monitor_120_pressure(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        if turn_in_progress:
            start = time.time()  # reset timer after turn
        if sustained_low(sensor_pins['120E_Short'], 5) or sustained_low(sensor_pins['120W_Short'], 5):
            print("[120 SENSORS] Pressure detected")
            return True
        time.sleep(0.2)
    print("[120 SENSORS] Timeout, no pressure")
    return False

def control_traffic():
    setup_gpio()
    print("[SYSTEM] Initializing intersection...")
    set_group_lights('120', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
    set_group_lights('MT', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    for t in ['Turn_Tech', 'Turn_120W', 'Turn_120E']:
        set_group_lights(t, GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    _thread.start_new_thread(flash_turn, ('Turn_120W', '120'))
    _thread.start_new_thread(flash_turn, ('Turn_120E', '120'))
    _thread.start_new_thread(monitor_turn_requests, ())

    while True:
        print("[GREEN] 120 STRAIGHT (max 45s)")
        wait_for_MT_request()

        print("[TRANSITION] 120 to red")
        set_group_lights('120', GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        set_group_lights('Turn_120W', GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        set_group_lights('Turn_120E', GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        time.sleep(3)
        set_group_lights('120', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        set_group_lights('Turn_120W', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        set_group_lights('Turn_120E', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        time.sleep(2)

        print("[GREEN] Martin & Tech (max 20s)")
        set_group_lights('MT', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
        _thread.start_new_thread(flash_turn, ('Turn_Tech', 'MT'))
        monitor_120_pressure(timeout=20)

        print("[TRANSITION] MT to red")
        set_group_lights('MT', GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        set_group_lights('Turn_Tech', GPIO.LOW, GPIO.HIGH, GPIO.LOW)
        time.sleep(3)
        set_group_lights('MT', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        set_group_lights('Turn_Tech', GPIO.HIGH, GPIO.LOW, GPIO.LOW)
        time.sleep(2)

        print("[RESUME] 120 STRAIGHT")
        set_group_lights('120', GPIO.LOW, GPIO.LOW, GPIO.HIGH)
        _thread.start_new_thread(flash_turn, ('Turn_120W', '120'))
        _thread.start_new_thread(flash_turn, ('Turn_120E', '120'))

if __name__ == "__main__":
    try:
        control_traffic()
    except KeyboardInterrupt:
        print("Shutting down...")
        for pin in light_pins.values():
            GPIO.output(pin, GPIO.LOW)

