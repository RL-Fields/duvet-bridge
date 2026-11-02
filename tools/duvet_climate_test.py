import asyncio
from bleak import BleakScanner, BleakClient

CLIMATE = "00002b52-0000-1000-8000-00805f9b34fb"

def packet(l, r):
    assert 5 <= l <= 7 and 5 <= r <= 7, "outside test limits"
    d = [0x05, 0x03, 0x02, l, 0x03, r]
    d.append(sum(d) // 6)
    return bytes(d)

STEPS = [(6, 6), (6, 7), (5, 6), (6, 5), (7, 7), (6, 6)]

async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, a: d.name and "SMARTDUVET" in d.name.upper(), timeout=20)
    if not dev:
        print("SMARTDUVET not found"); return
    async with BleakClient(dev, timeout=20) as c:
        try:
            for l, r in STEPS:
                data = packet(l, r)
                await c.write_gatt_char(CLIMATE, data, response=True)
                await asyncio.sleep(2)
                rb = await c.read_gatt_char(CLIMATE)
                ok = len(rb) > 5 and rb[3] == l and rb[5] == r
                print(f"set L={l} R={r}  wrote {data.hex()}  readback {rb.hex()}  {'OK' if ok else 'MISMATCH'}")
        finally:
            await c.write_gatt_char(CLIMATE, packet(6, 6), response=True)
            await asyncio.sleep(2)
            rb = await c.read_gatt_char(CLIMATE)
            print("final", rb.hex(), "OFF" if rb[3] == 6 and rb[5] == 6 else "NOT OFF - run duvet_climate4.py 6 6")

asyncio.run(main())
