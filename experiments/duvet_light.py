import asyncio, sys
from bleak import BleakScanner, BleakClient

LIGHT = "00002b50-0000-1000-8000-00805f9b34fb"

def packet(on, r, g, b, br):
    d = [0x06, 0x02, 1 if on else 0, r, g, b, br]
    d.append(sum(d) // 7)
    return bytes(d)

async def main():
    on = sys.argv[1] == "on"
    r, g, b, br = (int(x) for x in sys.argv[2:6])
    assert all(0 <= v <= 255 for v in (r, g, b)) and 1 <= br <= 253
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    data = packet(on, r, g, b, br)
    print("writing", data.hex())
    async with BleakClient(dev, timeout=20) as c:
        await c.write_gatt_char(LIGHT, data)
        print("readback", (await c.read_gatt_char(LIGHT)).hex())

asyncio.run(main())
