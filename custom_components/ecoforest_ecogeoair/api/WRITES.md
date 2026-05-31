# Ecoforest API write operations

This document describes how to drive the heat pump via API writes, based on the vendor web app in `api/vendor_website/` (HTML and JS under `webpages/gama/fr/webpages/` and `webpages/gama/js/`).

## Write endpoints

All requests are POST to `/recepcion_datos_4.cgi` with form data.

### Digital (boolean) write – idOperacion=2011

- **Parameters**: `dir`, `num`, and the value as a separate form field (e.g. `0` or `1`).
- **Example**: `idOperacion=2011&dir=6101&num=1&0`
- **Value**: Integer 0 or 1 (or as required by the register).

### Analog / integer write – idOperacion=2012

- **Parameters**: `dir` (register address), `num` (number of registers, usually 1), and the value as **hex string** (4 characters, e.g. `0000`–`FFFF`).
- **Encoding**:
  - **Analog (temperature, pressure, etc.)**: value × 10, then convert to 16-bit hex. Negative: `65536 - abs(value)` then to hex.
  - **Temperature in Fahrenheit**: convert to Celsius first: `(F - 32) * 5/9`, then × 10, then to hex.
  - **Pressure in PSI**: convert to bar: `value / 14.5`, then × 10, then to hex.
  - **Integer**: value as signed 16-bit; same hex encoding for negatives.
- **Example**: set analog register at dir `1234` to 22.5 → 225 → hex `00E1` → `idOperacion=2012&dir=1234&num=1&00E1`.

Response format is the same as reads: first line `error_id=0` on success, then payload lines, last line `0`.

## Register map source

All register addresses below were extracted from the HTML under **`api/vendor_website/webpages/gama/fr/webpages/`** by searching for `set_reg(`, `set_reg_temp(`, and `set_reg_dttemp(`. Season register 6101 is set via `set_reg_loc(3, 6101, "estacion", 1, 0, 4)` in **`webpages/gama/js/on_off.js`**. Encoding rules come from **`webpages/gama/js/escribe_var.js`**.

A full machine-readable map is in **`api/register_map.json`** (symbolic names → dir, type, num, min, max, description). Type 1 = digital (2011), type 2 = analog/temperature (2012, value×10 hex), type 3 = integer (2012, signed 16-bit hex).

## Key registers for HA

| Usage | dir | Type | num | Range / values |
|-------|-----|------|-----|----------------|
| Machine on/off | 6100 | integer | 1 | 0=Off, 1=On, 2=Emergency |
| Season / program | 6101 | integer | 1 | 0=Winter, 1=Summer, 2=Auto, 3=Mixed, 4=Remote |
| **DHW on/off** | **1524** | digital | 1 | 0/1 |
| **DHW temperature setpoint** | **6106** | analog (temp×10) | 1 | °C (device unit) |
| DHW delta T | 6105 | analog | 1 | °C |
| **Heating enable** | **1552** | digital | 1 | 0/1 |
| Heating cutoff temp | 6159 | analog | 1 | °C |
| **Zone 1–5 heating setpoint** | **6459–6463** | analog | 1 | °C (supply/consigna) |
| Zone 1–5 terminal on/off | 6464–6468 | integer | 1 | 0/1 |
| **Pool on/off** | **1574** | digital | 1 | 0/1 (piscina_usuario en_acs) |
| **Pool setpoint temp** | **6253** | analog | 1 | °C |
| Cooling enable | 1568 | digital | 1 | 0/1 |

## Integration notes

The integration now uses this map through `EcoGeoAirApi.write_by_register()` and `EcoGeoAirApi.write_register_map()`. Public setters clamp values to the vendor min/max range and encode digital, analog, and integer writes before posting to the device.

Validate new writable fields against the vendor HTML/JS first, then add them to `api_mapping.json` or `register_map.json` with their register address, type, range, and a short description.

## Endpoint 2152 – two response layouts

The same endpoint **2152** is used in two different ways in the codebase and in the vendor app:

| Source | Layout | Indices 0–2 | 3–8 | 9–14 | 15–21 | 24–33 |
|--------|--------|-------------|-----|------|-------|-------|
| **Our `api_mapping.json`** | Zone/buffer/DHW | hdtsg1–hdtsg3 (zone heat setpoints) | … zone temps, regulation, cool setpoints … | … | buffers, DHW, pool setpoint |
| **Vendor `principal.js` (actualizarpagina4)** | Extended / ODU | tip, **pt** (pool temp), **ppdo** (pool offset) | **ss1–ss6** (ODU state: 1=on, 2=emergency, 3=off) | **es1–es6** (ODU present) | hgfi, dgfi, pgfi, cgfi, htfi, hcfi, ccfi | dcfi, pcf, efi, **hprb**, at, aux1–5 |

So the **same response positions** are interpreted as either zone/buffer/DHW data or as pool + ODU + feature flags. The device cannot return both interpretations at once, so **which layout you get depends on the device**:

- **EcoGeo (lg 1, 2, 5)** or single-unit / no-ODU firmware typically returns the **zone/buffer/DHW** layout (what we use today). That gives zone setpoints, zone temps, regulation %, buffer and DHW temps, pool setpoint.
- **EcoAir (lg 3, 4)** with **multi-ODU** capability (e.g. when HPRB&32 in 2100) appears to use the **extended** layout in the vendor UI: pool **current temperature** (pt), pool offset (ppdo), **ODU 1–6 state** (ss1–ss6) and **ODU present** (es1–es6), plus feature flags (hgfi, dgfi, …) and hprb, aux, etc. The vendor then shows “ODU 1” … “ODU 6” and “Pool temperature” from this block.

So it’s **model- and capability-dependent** (EcoGeo vs EcoAir, and whether ODUs are present), not necessarily a specific firmware version. Ecoforest don’t document this in the JS; the above is inferred from `principal.js`.

**What an “extended 2152” parser would add (only when the device returns this layout):**

- **Pool current temperature** (`pt`) – we don’t have it elsewhere; 2151/2152 zone layout only have pool setpoint.
- **ODU 1–6 state** (on/off/emergency) and **ODU present** – useful for EcoAir multi-ODU installs (sensors or diagnostics).
- **Feature flags** (hgfi, dgfi, pgfi, cgfi, htfi, hcfi, ccfi, dcfi, pcf, efi, hprb) – for diagnostics or to decide which parts of the UI/entities to show.

**Practical approach:** Keep using the current 2152 mapping (zone/buffer/DHW). If you add support for EcoAir with ODUs, either detect the layout (e.g. by response length or by model lg 3/4 and then trying the extended parse) and add an optional `get_zones_status_extended()` that parses the extended layout and exposes pool temp + ODU status when available.

## References

- **`api/vendor_website/webpages/gama/js/escribe_var.js`**: `set_reg`, `set_reg_temp`, `set_reg_pres`, `set_reg_dttemp` (encoding and 2011/2012 calls).
- **`api/vendor_website/webpages/gama/js/on_off.js`**: `set_reg_loc`, `programa()` (6101 season), endpoints 2100, 2110, 2127 for on/off and ODU state.
- **`api/vendor_website/webpages/gama/fr/webpages/`**: `acs_usuario.html`, `calefaccion_usuario.html`, `piscina_usuario.html`, `on_off.html`, `fecha_hora.html`, etc. – each `set_reg*(type, dir, ...)` gives the register address and type.
- **`api/register_map.json`**: Full register map extracted from the above HTML/JS.
