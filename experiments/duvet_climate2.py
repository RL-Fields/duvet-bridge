import asyncio, sys
from bleak import BleakScanner, BleakClient

CLIMATE = "00002b52-0000-1000-8000-00805f9b34fb"
CMD     = "00002b53-0000-1000-8000-00805f9b34fb"
MIN_LEVEL, MAX_LEVEL = 4, 8

def packet(l, r):
    d = [0x05, 0x02, 0x02, l, 0x03, r]
    d.append(sum(d) // 6)
    return bytes(d)

async def main():
    l, r = int(sys.argv[1]), int(sys.argv[2])
    prelude = bytes.fromhex(sys.argv[3]) if len(sys.argv) > 3 else None
    for v in (l, r):
        assert MIN_LEVEL <= v <= MAX_LEVEL, "outside test limits"
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    def note(name):
        return lambda h, data: print("  notify", name, data.hex())
    async with BleakClient(dev, timeout=20) as c:
        await c.start_notify(CLIMATE, note("2b52"))
        await c.start_notify(CMD, note("2b53"))
        if prelude:
            print("prelude ->2b53", prelude.hex())
            await c.write_gatt_char(CMD, prelude, response=True)
            await asyncio.sleep(1.5)
        data = packet(l, r)
        print("climate ->2b52", data.hex())
        await c.write_gatt_char(CLIMATE, data, response=True)
        await asyncio.sleep(2)
        print("readback 2b52", (await c.read_gatt_char(CLIMATE)).hex())
        print("readback 2b53", (await c.read_gatt_char(CMD)).hex())
    if (l, r) != (6, 6):
        print("NOT OFF. To turn off: python duvet_climate2.py 6 6 0e020c0005")

asyncio.run(main())
