import asyncio
from bleak import BleakScanner, BleakClient

LIGHT = "00002b50-0000-1000-8000-00805f9b34fb"

def pk(payload):
    d = [len(payload)] + list(payload)
    d.append(sum(d) // len(d))
    return bytes(d)

def light(t, on, r, g, b, br):
    return pk([t, 1 if on else 0, r, g, b, br])

TRIES = [
    ("type 03, red, dim",              light(3, 1, 255, 0, 0, 20), True),
    ("type 03, red, dim, no response", light(3, 1, 255, 0, 0, 20), False),
    ("type 03, blue, brighter",        light(3, 1, 0, 0, 255, 100), True),
]
OFF = light(3, 0, 0, 0, 255, 1)

async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    async with BleakClient(dev, timeout=20) as c:
        try:
            for name, data, resp in TRIES:
                print(name, "->", data.hex())
                try:
                    await c.write_gatt_char(LIGHT, data, response=resp)
                except Exception as e:
                    print("   error:", e); continue
                await asyncio.sleep(3)
                rb = await c.read_gatt_char(LIGHT)
                print("   readback", rb.hex())
                if len(rb) > 5 and rb[2] == 1 and tuple(rb[3:6]) == tuple(data[3:6]):
                    print("   *** ACCEPTED - did the light change? ***")
                    await asyncio.sleep(4)
                    break
        finally:
            await c.write_gatt_char(LIGHT, OFF, response=True)
            await asyncio.sleep(2)
            print("sent off, readback", (await c.read_gatt_char(LIGHT)).hex())

asyncio.run(main())
