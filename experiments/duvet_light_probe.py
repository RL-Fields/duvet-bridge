import asyncio
from bleak import BleakScanner, BleakClient

LIGHT = "00002b50-0000-1000-8000-00805f9b34fb"
PKT = bytes.fromhex("060201ff00000125")  # red, lowest brightness

async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    async with BleakClient(dev, timeout=20) as c:
        ch = c.services.get_characteristic(LIGHT)
        print("properties:", ch.properties)

        async def readback(label):
            await asyncio.sleep(1.5)
            print(label, "->", (await c.read_gatt_char(LIGHT)).hex())

        await c.write_gatt_char(LIGHT, PKT, response=False)
        await readback("A: write without response")

        def on_note(_, data):
            print("   notification:", data.hex())
        await c.start_notify(LIGHT, on_note)
        await c.write_gatt_char(LIGHT, PKT, response=True)
        await readback("B: notify on, write with response")

        await c.write_gatt_char(LIGHT, PKT, response=False)
        await readback("C: notify on, write without response")
        await c.stop_notify(LIGHT)

asyncio.run(main())
