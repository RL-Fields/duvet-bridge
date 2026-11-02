import asyncio, sys
from bleak import BleakScanner, BleakClient

CLIMATE = "00002b52-0000-1000-8000-00805f9b34fb"
MIN_LEVEL, MAX_LEVEL = 4, 8

def packet(l, r):
    d = [0x05, 0x03, 0x02, l, 0x03, r]
    d.append(sum(d) // 6)
    return bytes(d)

async def main():
    l, r = int(sys.argv[1]), int(sys.argv[2])
    for v in (l, r):
        assert MIN_LEVEL <= v <= MAX_LEVEL, "outside test limits"
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    data = packet(l, r)
    print("writing", data.hex())
    async with BleakClient(dev, timeout=20) as c:
        await c.write_gatt_char(CLIMATE, data, response=True)
        await asyncio.sleep(2)
        print("readback", (await c.read_gatt_char(CLIMATE)).hex())
    if (l, r) != (6, 6):
        print("NOT OFF. To turn off: python duvet_climate4.py 6 6")

asyncio.run(main())
