import asyncio, json, sys
from bleak import BleakScanner, BleakClient

async def snap(label):
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    out = {}
    async with BleakClient(dev, timeout=20) as c:
        for svc in c.services:
            for ch in svc.characteristics:
                if "read" in ch.properties:
                    try:
                        out[ch.uuid[4:8]] = (await c.read_gatt_char(ch.uuid)).hex()
                    except Exception as e:
                        out[ch.uuid[4:8]] = f"ERR {e}"
    json.dump(out, open(f"snap_{label}.json", "w"), indent=1)
    for k, v in out.items():
        print(k, v)

def diff(a, b):
    A = json.load(open(f"snap_{a}.json")); B = json.load(open(f"snap_{b}.json"))
    for k in sorted(set(A) | set(B)):
        if A.get(k) != B.get(k):
            print(f"CHANGED {k}\n  {a}: {A.get(k)}\n  {b}: {B.get(k)}")

if sys.argv[1] == "diff":
    diff(sys.argv[2], sys.argv[3])
else:
    asyncio.run(snap(sys.argv[1]))
