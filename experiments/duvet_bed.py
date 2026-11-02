import asyncio, sys
from bleak import BleakScanner, BleakClient

BED = "00002b53-0000-1000-8000-00805f9b34fb"

async def main():
    data = bytes.fromhex(sys.argv[1])
    assert len(data) == 5
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    async with BleakClient(dev, timeout=20) as c:
        await c.write_gatt_char(BED, data)
        print("readback", (await c.read_gatt_char(BED)).hex())

asyncio.run(main())
