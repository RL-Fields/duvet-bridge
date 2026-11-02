import asyncio, json, os, signal, sys, time
import paho.mqtt.client as mqtt
from bleak import BleakScanner, BleakClient

# --- config (from the environment; see ~/.duvet-bridge.env) ---
HOST = os.environ["MQTT_HOST"]
PORT = int(os.environ.get("MQTT_PORT", "1883"))
USER = os.environ.get("MQTT_USER")
PASS = os.environ.get("MQTT_PASS")
MAX_HEAT_HOURS = float(os.environ.get("MAX_HEAT_HOURS", "8"))  # auto-off safety

# --- BLE characteristics ---
def uuid(n): return f"0000{n}-0000-1000-8000-00805f9b34fb"
LIGHT, CLIMATE, CMD = uuid("2b50"), uuid("2b52"), uuid("2b53")
MAKE_BED = bytes.fromhex("0303130607")
BED_LOCKOUT = 90          # seconds
OFF_LEVEL = 6             # level 6 = off, higher = warmer, lower = cooler
MIN_LEVEL, MAX_LEVEL = 1, 11   # same range as the app
LIGHT_TYPE = 0x03         # UNTESTED guess, same trick that fixed the climate

# --- MQTT topics ---
BASE = "smartduvet"
STATUS = f"{BASE}/status"
DEV = {"identifiers": ["smartduvet_0003f8"], "name": "SmartDuvet",
       "manufacturer": "SmartDuvet", "model": "v1.3"}

levels = {"left": OFF_LEVEL, "right": OFF_LEVEL}
heat_since = None
last_bed = 0.0
light = {"state": "OFF", "color": {"r": 255, "g": 255, "b": 255}, "brightness": 128}
LOCK = None
loop = None
client = None
stopping = False


def pk(payload):
    d = [len(payload)] + list(payload)
    d.append(sum(d) // len(d))
    return bytes(d)

def climate_packet(l, r): return pk([0x03, 0x02, l, 0x03, r])
def light_packet(on, r, g, b, br): return pk([LIGHT_TYPE, 1 if on else 0, r, g, b, br])
def clamp(v, lo, hi): return max(lo, min(hi, v))


async def ble_do(fn):
    async with LOCK:
        last = None
        for attempt in range(3):
            try:
                dev = await BleakScanner.find_device_by_filter(
                    lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=15)
                if not dev:
                    raise RuntimeError("SMARTDUVET not found")
                async with BleakClient(dev, timeout=20) as c:
                    return await fn(c)
            except Exception as e:
                last = e
                print(f"BLE attempt {attempt + 1} failed: {e}", flush=True)
                await asyncio.sleep(2)
        raise last


def publish_levels():
    for side in ("left", "right"):
        client.publish(f"{BASE}/climate/{side}/state", str(levels[side]), retain=True)


async def set_climate(l, r):
    global heat_since
    l, r = clamp(l, MIN_LEVEL, MAX_LEVEL), clamp(r, MIN_LEVEL, MAX_LEVEL)
    pkt = climate_packet(l, r)

    async def fn(c):
        await c.write_gatt_char(CLIMATE, pkt, response=True)
        await asyncio.sleep(1.5)
        return await c.read_gatt_char(CLIMATE)

    try:
        rb = await ble_do(fn)
    except Exception as e:
        print(f"climate write failed: {e}", flush=True)
        return
    if len(rb) > 5:
        levels["left"], levels["right"] = rb[3], rb[5]
        if (rb[3], rb[5]) != (l, r):
            print(f"WARNING: asked {l}/{r} but box reports {rb[3]}/{rb[5]}", flush=True)
    publish_levels()
    off = levels["left"] in (0, OFF_LEVEL) and levels["right"] in (0, OFF_LEVEL)
    heat_since = None if off else (heat_since or time.time())
    print(f"climate now L={levels['left']} R={levels['right']}", flush=True)


async def make_bed():
    global last_bed
    if time.time() - last_bed < BED_LOCKOUT:
        print("make bed ignored (lockout)", flush=True)
        return
    last_bed = time.time()

    async def fn(c):
        await c.write_gatt_char(CMD, MAKE_BED, response=True)

    try:
        await ble_do(fn)
        print("make bed sent", flush=True)
    except Exception as e:
        last_bed = 0.0
        print(f"make bed failed: {e}", flush=True)


def publish_light():
    client.publish(f"{BASE}/light/state", json.dumps(
        {"state": light["state"], "color_mode": "rgb", "color": light["color"],
         "brightness": light["brightness"]}), retain=True)


async def set_light(payload):
    try:
        cmd = json.loads(payload)
    except Exception:
        return
    if "state" in cmd:
        light["state"] = "ON" if str(cmd["state"]).upper() == "ON" else "OFF"
    if "color" in cmd:
        light["color"].update({k: int(cmd["color"][k]) for k in "rgb" if k in cmd["color"]})
    if "brightness" in cmd:
        light["brightness"] = clamp(int(cmd["brightness"]), 1, 253)
    c_ = light["color"]
    pkt = light_packet(light["state"] == "ON", c_["r"], c_["g"], c_["b"], light["brightness"])

    async def fn(c):
        await c.write_gatt_char(LIGHT, pkt, response=True)

    try:
        await ble_do(fn)
    except Exception as e:
        print(f"light write failed: {e}", flush=True)
    publish_light()


async def handle(topic, payload):
    try:
        if topic == f"{BASE}/bed/press":
            await make_bed()
        elif topic == f"{BASE}/light/set":
            await set_light(payload)
        elif topic == f"{BASE}/climate/left/set":
            await set_climate(int(float(payload)), levels["right"] if levels["right"] else OFF_LEVEL)
        elif topic == f"{BASE}/climate/right/set":
            await set_climate(levels["left"] if levels["left"] else OFF_LEVEL, int(float(payload)))
    except Exception as e:
        print(f"handler error on {topic}: {e}", flush=True)


async def read_startup_levels():
    async def fn(c):
        return await c.read_gatt_char(CLIMATE), await c.read_gatt_char(LIGHT)
    try:
        rb, lb = await ble_do(fn)
        if len(rb) > 5 and 1 <= rb[3] <= 11 and 1 <= rb[5] <= 11:
            levels["left"], levels["right"] = rb[3], rb[5]
        if len(lb) > 6 and lb[2] in (0, 1) and any(lb[3:7]):
            light["state"] = "ON" if lb[2] == 1 else "OFF"
            light["color"] = {"r": lb[3], "g": lb[4], "b": lb[5]}
            light["brightness"] = clamp(lb[6], 1, 253)
    except Exception as e:
        print(f"startup read failed: {e}", flush=True)
    publish_levels()
    publish_light()
    print(f"startup: L={levels['left']} R={levels['right']} light={light['state']}", flush=True)


async def watchdog():
    # safety: turn everything off if left warm/cool for too long
    while not stopping:
        await asyncio.sleep(60)
        if heat_since and time.time() - heat_since > MAX_HEAT_HOURS * 3600:
            print("auto-off: max heat time reached", flush=True)
            await set_climate(OFF_LEVEL, OFF_LEVEL)


def discovery():
    avail = {"availability_topic": STATUS, "device": DEV}
    cfgs = {
        "light/smartduvet_0003f8/light": {
            "name": "Duvet light", "unique_id": "smartduvet_0003f8_light",
            "schema": "json", "command_topic": f"{BASE}/light/set",
            "state_topic": f"{BASE}/light/state", "brightness": True,
            "brightness_scale": 253, "supported_color_modes": ["rgb"], **avail},
        "button/smartduvet_0003f8/make_bed": {
            "name": "Make bed", "unique_id": "smartduvet_0003f8_make_bed",
            "command_topic": f"{BASE}/bed/press", **avail},
    }
    for side in ("left", "right"):
        cfgs[f"number/smartduvet_0003f8/{side}"] = {
            "name": f"Duvet {side} level", "unique_id": f"smartduvet_0003f8_{side}",
            "command_topic": f"{BASE}/climate/{side}/set",
            "state_topic": f"{BASE}/climate/{side}/state",
            "min": MIN_LEVEL, "max": MAX_LEVEL, "step": 1, "mode": "slider",
            "icon": "mdi:thermometer", **avail}
    for path, cfg in cfgs.items():
        client.publish(f"homeassistant/{path}/config", json.dumps(cfg), retain=True)


def on_connect(c, userdata, flags, rc, *args):
    print(f"MQTT connected: {rc}", flush=True)
    discovery()
    c.publish(STATUS, "online", retain=True)
    for t in ("bed/press", "light/set", "climate/left/set", "climate/right/set"):
        c.subscribe(f"{BASE}/{t}")


def on_message(c, userdata, msg):
    asyncio.run_coroutine_threadsafe(handle(msg.topic, msg.payload.decode()), loop)


async def main():
    global loop, client, LOCK, stopping
    loop = asyncio.get_running_loop()
    LOCK = asyncio.Lock()
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    if USER:
        client.username_pw_set(USER, PASS)
    client.will_set(STATUS, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(HOST, PORT, 60)
    client.loop_start()

    stop = asyncio.Event()
    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, stop.set)

    asyncio.create_task(read_startup_levels())
    asyncio.create_task(watchdog())
    await stop.wait()

    stopping = True
    print("shutting down: turning temperature off", flush=True)
    if levels["left"] not in (0, OFF_LEVEL) or levels["right"] not in (0, OFF_LEVEL):
        try:
            await asyncio.wait_for(set_climate(OFF_LEVEL, OFF_LEVEL), timeout=60)
        except Exception as e:
            print(f"could not confirm off at shutdown: {e}", flush=True)
    client.publish(STATUS, "offline", retain=True).wait_for_publish(5)
    client.loop_stop()
    client.disconnect()

asyncio.run(main())
