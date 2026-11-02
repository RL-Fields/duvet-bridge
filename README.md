# duvet-bridge

Local Bluetooth (BLE) control of a SmartDuvet (Kickstarter v1.3) from a Raspberry Pi,
published to Home Assistant over MQTT. No cloud, no phone app.

**Unofficial, reverse-engineered, use at your own risk.** The duvet contains a heater.
Not affiliated with SmartDuvet. Always keep the level cap and auto-off in place.

## What you get in Home Assistant

- **Make bed** button
- **Duvet off** button (sets both sides to 6)
- **Duvet left level / right level** sliders (1-11, 6 = off)
- **Duvet light** (RGB + brightness)

## Safety built in

- Auto-off after `MAX_HEAT_HOURS` (default 8)
- Temperature set to off when the bridge stops or restarts
- Every temperature write is read back and the real level is reported

## Bluetooth connection

The duvet allows one BLE connection at a time. After a command, the bridge keeps its
connection open for `IDLE_SECONDS` (default 120) so follow-up changes are quick, then
closes it. **The phone app cannot connect during that window.** Wait for the log line
`idle: closing Bluetooth connection`, or stop the service. Set `IDLE_SECONDS` in the
env file to change it. On startup the bridge reads the box's current levels and light
state so Home Assistant matches what the duvet is doing.

## Protocol notes

Custom GATT characteristics, base UUID `0000XXXX-0000-1000-8000-00805f9b34fb`.
Only one BLE connection is allowed at a time, so close the phone app first.

Packet layout: `[length][type][payload...][checksum]`, where
`checksum = floor(sum of all preceding bytes / number of preceding bytes)`.

The box reports its state with type `02`, but it only accepts **writes with type `03`**.
Writes with type `02` are silently ignored.

| Characteristic | Purpose | Write packet |
|---|---|---|
| `2b52` | Temperature | `05 03 02 L 03 R chk` (L/R = level 1-11, 6 = off, higher = warmer) |
| `2b50` | Light | `06 03 on R G B brightness chk` (on = 01/00, brightness 01-fd) |
| `2b53` | Commands | Make bed `03 03 13 06 07`; schedule on `03 03 13 05 07`; schedule off `03 03 0e 00 05` |

The box forgets its light and temperature state if it loses power.

## Setup

    python3 -m venv ~/duvet-env
    ~/duvet-env/bin/pip install bleak paho-mqtt
    cp duvet-bridge.env.example ~/.duvet-bridge.env   # then edit; keep it out of git
    chmod 600 ~/.duvet-bridge.env

Run as a service with a systemd unit that uses
`EnvironmentFile=/home/<user>/.duvet-bridge.env`
(plain `NAME=value` lines, no `export`).

Use a dedicated, non-admin MQTT user for the bridge.

## Layout

- `duvet_bridge.py` - the bridge
- `tools/` - snapshot/diff tool and small test scripts
- `experiments/` - scripts used while working out the protocol
