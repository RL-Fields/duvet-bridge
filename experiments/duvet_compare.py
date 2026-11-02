import asyncio, time
from bleak import BleakScanner, BleakClient

def u(x): return f"0000{x}-0000-1000-8000-00805f9b34fb"
CH = ["2b50", "2b52", "2b53", "2b54", "2b55"]
t0 = time.monotonic()

async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    async with BleakClient(dev, timeout=20) as c:
        for x in CH:
            def cb(_, data, x=x):
                print(f"  [{time.monotonic()-t0:5.1f}s] notify {x}: {data.hex()}")
            try:
                await c.start_notify(u(x), cb)
            except Exception as e:
                print("notify failed", x, e)
        await asyncio.sleep(2)

        async def test(label, x, hexv):
            print(label, "-> write", x, hexv)
            await c.write_gatt_char(u(x), bytes.fromhex(hexv), response=True)
            await asyncio.sleep(2)
            print("   readback", x, (await c.read_gatt_char(u(x))).hex())

        await test("1) light, app packet (blue, low, on)", "2b50", "06020144a1ff0146")
        await test("2) schedule-off value", "2b53", "03030e0005")

        for x in CH:
            try:
                await c.stop_notify(u(x))
            except Exception:
                pass

asyncio.run(main())
