import asyncio
from bleak import BleakScanner, BleakClient

CLIMATE = "00002b52-0000-1000-8000-00805f9b34fb"

def pk(payload):
    d = [len(payload)] + payload
    d.append(sum(d) // len(d))
    return bytes(d)

OFF = pk([0x02, 0x02, 6, 0x03, 6])
TRIES = [
    ("same, write-without-response", pk([0x02, 0x02, 7, 0x03, 6]), False),
    ("type 03",                      pk([0x03, 0x02, 7, 0x03, 6]), True),
    ("left zone only",               pk([0x02, 0x02, 7]),          True),
    ("left only, no response",       pk([0x02, 0x02, 7]),          False),
    ("zones 01/02",                  pk([0x02, 0x01, 7, 0x02, 6]), True),
]

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
                    await c.write_gatt_char(CLIMATE, data, response=resp)
                except Exception as e:
                    print("   error:", e); continue
                await asyncio.sleep(2)
                rb = await c.read_gatt_char(CLIMATE)
                print("   readback", rb.hex())
                if len(rb) > 3 and rb[3] == 7:
                    print("   *** ACCEPTED ***"); break
        finally:
            await c.write_gatt_char(CLIMATE, OFF, response=True)
            print("sent off:", OFF.hex())

asyncio.run(main())
