#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║          SOLAR LOAD CALCULATOR — Household Edition           ║
║    Calculates solar panel size, battery capacity & inverter  ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import os

# ── ANSI colour helpers ──────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
ORANGE = "\033[33m"
BLUE   = "\033[94m"
WHITE  = "\033[97m"

def clr(text, *codes): return "".join(codes) + str(text) + RESET
def header(text):      return clr(f"\n{'─'*62}\n  {text}\n{'─'*62}", BOLD, CYAN)
def subheader(text):   return clr(f"\n  {text}", BOLD, YELLOW)
def ok(text):          return clr(f"  ✔  {text}", GREEN)
def info(text):        return clr(f"  ℹ  {text}", BLUE)
def warn(text):        return clr(f"  ⚠  {text}", ORANGE)
def err(text):         return clr(f"  ✘  {text}", RED)

# ── Default appliance catalogue ──────────────────────────────────────────────
DEFAULT_APPLIANCES = [
    # (name,                  typical_watts, category)
    ("LED Bulb (1 unit)",            10,  "Lighting"),
    ("Ceiling Fan",                  75,  "Cooling"),
    ("Desktop Computer",            200,  "Electronics"),
    ("Laptop",                       65,  "Electronics"),
    ("42\" LED TV",                  80,  "Entertainment"),
    ("Refrigerator (mid-size)",     150,  "Kitchen"),
    ("Microwave Oven",             1000,  "Kitchen"),
    ("Electric Kettle",            1500,  "Kitchen"),
    ("Washing Machine",            500,  "Laundry"),
    ("Water Pump (0.5 HP)",        400,  "Utility"),
    ("Phone Charger",               10,  "Electronics"),
    ("Wi-Fi Router",                15,  "Electronics"),
    ("Air Conditioner (1 ton)",   1000,  "Cooling"),
    ("Iron",                       1000,  "Laundry"),
    ("Security Light (outdoor)",    20,  "Security"),
    ("Custom Appliance",             0,  "Custom"),
]

# ── Input helpers ────────────────────────────────────────────────────────────

def prompt(msg, default=None):
    """Prompt with optional default, return stripped string."""
    suffix = f" [{default}]" if default is not None else ""
    try:
        raw = input(clr(f"  → {msg}{suffix}: ", BOLD, WHITE)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return raw if raw else (str(default) if default is not None else "")

def prompt_float(msg, default=None, mn=0.0, mx=None):
    while True:
        raw = prompt(msg, default)
        try:
            val = float(raw)
            if val < mn:
                print(err(f"Value must be ≥ {mn}"))
                continue
            if mx is not None and val > mx:
                print(err(f"Value must be ≤ {mx}"))
                continue
            return val
        except ValueError:
            print(err("Please enter a valid number."))

def prompt_int(msg, default=None, mn=0, mx=None):
    return int(prompt_float(msg, default, mn=mn, mx=mx))

# ── Appliance entry ──────────────────────────────────────────────────────────

def choose_appliance():
    """Show catalogue and let user pick or enter custom."""
    print(subheader("Appliance Catalogue"))
    for i, (name, watts, cat) in enumerate(DEFAULT_APPLIANCES, 1):
        watt_str = clr(f"{watts:>5} W", DIM) if watts else clr("  custom", DIM)
        print(f"   {clr(f'{i:>2}.', DIM, CYAN)} {name:<34} {watt_str}  {clr(cat, DIM)}")
    print()
    choice = prompt_int("Select appliance number", mn=1, mx=len(DEFAULT_APPLIANCES))
    name, watts, cat = DEFAULT_APPLIANCES[choice - 1]

    if name == "Custom Appliance":
        name  = prompt("Appliance name", "My Appliance")
        watts = prompt_float("Power rating (Watts)", mn=1)
        cat   = "Custom"
    elif watts == 0:
        watts = prompt_float(f"Power rating for '{name}' (Watts)", mn=1)

    qty   = prompt_int( f"Quantity of '{name}'", default=1, mn=1, mx=100)
    hours = prompt_float(f"Daily usage hours for '{name}'", default=4, mn=0.5, mx=24)

    return {"name": name, "watts": watts, "qty": qty, "hours": hours, "category": cat}

def collect_appliances():
    appliances = []
    print(header("STEP 1 — Add Your Appliances"))
    while True:
        appliances.append(choose_appliance())
        print(ok(f"Added: {appliances[-1]['qty']}× {appliances[-1]['name']}"))
        again = prompt("\nAdd another appliance? (y/n)", default="y").lower()
        if again != "y":
            break
    return appliances

# ── Calculation engine ───────────────────────────────────────────────────────

def calculate(appliances, peak_sun_hours, days_autonomy, battery_voltage,
              system_efficiency, battery_dod, safety_factor):
    """
    Returns a results dict with all sizing recommendations.

    Formulas
    ────────
    Daily energy (Wh)       = Σ (watts × qty × hours)
    Adjusted energy (Wh)    = daily_energy / system_efficiency
    Solar panel size (W)    = adjusted_energy / peak_sun_hours × safety_factor
    Battery capacity (Ah)   = (daily_energy × autonomy_days) / (battery_voltage × dod)
    Battery capacity (kWh)  = daily_energy × autonomy_days / (dod × 1000)
    Inverter rating (W)     = peak_load × safety_factor  (round to next standard)
    """
    # --- daily energy --------------------------------------------------------
    total_daily_wh = sum(a["watts"] * a["qty"] * a["hours"] for a in appliances)
    adjusted_wh    = total_daily_wh / system_efficiency

    # --- peak / surge load ---------------------------------------------------
    total_peak_w   = sum(a["watts"] * a["qty"] for a in appliances)

    # --- solar panels --------------------------------------------------------
    panel_kw_raw   = (adjusted_wh / peak_sun_hours) * safety_factor / 1000
    # round up to nearest 0.25 kW
    panel_kw       = round(((panel_kw_raw * 4) + 0.99) // 1 / 4, 2)
    panel_w        = panel_kw * 1000

    # --- battery -------------------------------------------------------------
    battery_kwh_raw = (total_daily_wh * days_autonomy) / (battery_dod * 1000)
    battery_kwh     = round(battery_kwh_raw * 1.05, 2)          # +5 % margin
    battery_ah      = round((battery_kwh * 1000) / battery_voltage, 0)

    # standard Ah sizes (12/24/48 V systems)
    std_ah = [20, 40, 60, 100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000]
    recommended_ah = next((s for s in std_ah if s >= battery_ah), battery_ah)

    # --- inverter ------------------------------------------------------------
    inverter_raw  = total_peak_w * safety_factor
    std_inv = [300, 500, 700, 1000, 1500, 2000, 2500, 3000, 4000, 5000,
               6000, 7500, 8000, 10000, 12000, 15000]
    inverter_w = next((s for s in std_inv if s >= inverter_raw), inverter_raw)

    return {
        "total_daily_wh":   round(total_daily_wh, 1),
        "adjusted_wh":      round(adjusted_wh, 1),
        "total_peak_w":     round(total_peak_w, 1),
        "panel_kw":         panel_kw,
        "panel_w":          panel_w,
        "battery_kwh":      battery_kwh,
        "battery_ah":       recommended_ah,
        "battery_voltage":  battery_voltage,
        "inverter_w":       inverter_w,
        "days_autonomy":    days_autonomy,
    }

# ── System parameters ────────────────────────────────────────────────────────

def get_system_params():
    print(header("STEP 2 — System Parameters"))
    print(info("Press Enter to accept defaults (suitable for East Africa / Kenya)\n"))

    psh   = prompt_float("Peak sun hours per day", default=5.5, mn=1.0, mx=12.0)
    days  = prompt_int(  "Days of battery autonomy (backup days)", default=1, mn=1, mx=7)
    volts = prompt_int(  "Battery bank voltage (12 / 24 / 48 V)", default=24, mn=12, mx=48)

    print(subheader("Advanced  (press Enter for defaults)"))
    eff   = prompt_float("System efficiency % (wiring + inverter losses)", default=85, mn=50, mx=99) / 100
    dod   = prompt_float("Battery Depth of Discharge % (LiFePO4=90, Lead=50)", default=80, mn=20, mx=95) / 100
    sf    = prompt_float("Safety / growth factor (e.g. 1.25 = 25 % headroom)", default=1.25, mn=1.0, mx=3.0)

    return psh, days, volts, eff, dod, sf

# ── Report ───────────────────────────────────────────────────────────────────

def print_report(appliances, results):
    r = results
    bar = "═" * 62

    print(f"\n{clr(bar, BOLD, YELLOW)}")
    print(clr("  ☀  SOLAR SYSTEM SIZING REPORT", BOLD, YELLOW))
    print(clr(bar, BOLD, YELLOW))

    # Appliance table
    print(subheader("Appliance Load Summary"))
    fmt = f"  {{:<32}} {{:>4}} {{:>6}} W  {{:>5}} h  {{:>8}} Wh"
    print(clr(fmt.format("Appliance", "Qty", "Each", "Hrs/d", "Daily"), DIM))
    print(clr("  " + "─"*60, DIM))

    for a in appliances:
        daily = a["watts"] * a["qty"] * a["hours"]
        print(fmt.format(
            a["name"][:32],
            f"×{a['qty']}",
            f"{a['watts']:.0f}",
            f"{a['hours']:.1f}",
            f"{daily:.0f}"
        ))

    print(clr("  " + "─"*60, DIM))
    print(clr(fmt.format("TOTAL", "", f"{r['total_peak_w']:.0f}", "", f"{r['total_daily_wh']:.0f}"), BOLD, WHITE))

    # Energy summary
    print(subheader("Energy Analysis"))
    print(f"  {'Raw daily load':<38} {r['total_daily_wh']:>8.1f} Wh")
    print(f"  {'Adjusted (system losses)':<38} {r['adjusted_wh']:>8.1f} Wh")
    print(f"  {'Peak / surge load':<38} {r['total_peak_w']:>8.1f} W")

    # Recommendations
    print(f"\n{clr(bar, BOLD, GREEN)}")
    print(clr("  ✦  RECOMMENDED SYSTEM SPECIFICATIONS", BOLD, GREEN))
    print(clr(bar, BOLD, GREEN))

    specs = [
        ("☀  Solar Panels",   f"{r['panel_kw']} kWp  ({r['panel_w']:.0f} W)",   ""),
        ("🔋 Battery Bank",   f"{r['battery_kwh']} kWh  ({r['battery_ah']:.0f} Ah @ {r['battery_voltage']} V)", ""),
        ("⚡ Inverter",        f"{r['inverter_w']:,} W  ({r['inverter_w']/1000:.1f} kVA)", ""),
    ]
    for label, value, note in specs:
        print(f"\n  {clr(label, BOLD, YELLOW)}")
        print(f"      {clr(value, BOLD, WHITE)}{('  ' + clr(note, DIM)) if note else ''}")

    print(f"\n  {clr('Autonomy:', BOLD, CYAN)} {r['days_autonomy']} day(s) without sun")

    # Indicative sizing guide
    print(f"\n{clr(bar, DIM)}")
    print(clr("  ⊞  INDICATIVE PANEL CONFIGURATION", BOLD, CYAN))
    print(clr(bar, DIM))
    for watt in [100, 200, 250, 300, 400, 500, 550]:
        count = -(-r["panel_w"] // watt)           # ceiling division
        actual = count * watt
        note = " ◄ common size" if watt == 400 else ""
        print(f"    {count:>3}× {watt} W panels  →  {actual:.0f} Wp installed{clr(note, DIM, GREEN)}")

    print(f"\n{clr(bar, DIM)}")
    print(clr("  DISCLAIMER: These are estimates. Consult a certified solar installer", DIM))
    print(clr("  for a site survey, shade analysis, and final system design.", DIM))
    print(clr(bar, DIM))
    print()

# ── Save report ──────────────────────────────────────────────────────────────

def save_report(appliances, results, params):
    filename = "solar_report.txt"
    r = results
    psh, days, volts, eff, dod, sf = params
    lines = [
        "SOLAR LOAD CALCULATOR — REPORT",
        "=" * 60,
        "",
        "APPLIANCES",
        "-" * 60,
    ]
    for a in appliances:
        daily = a["watts"] * a["qty"] * a["hours"]
        lines.append(f"  {a['qty']}× {a['name']}: {a['watts']} W × {a['hours']} h = {daily:.0f} Wh/day")

    lines += [
        "",
        f"Total daily load  : {r['total_daily_wh']:.1f} Wh",
        f"Adjusted load     : {r['adjusted_wh']:.1f} Wh",
        f"Peak load         : {r['total_peak_w']:.1f} W",
        "",
        "SYSTEM PARAMETERS",
        "-" * 60,
        f"  Peak sun hours  : {psh} h/day",
        f"  Autonomy        : {days} day(s)",
        f"  Battery voltage : {volts} V",
        f"  Efficiency      : {eff*100:.0f} %",
        f"  DoD             : {dod*100:.0f} %",
        f"  Safety factor   : {sf}",
        "",
        "RECOMMENDATIONS",
        "-" * 60,
        f"  Solar panels    : {r['panel_kw']} kWp  ({r['panel_w']:.0f} W)",
        f"  Battery bank    : {r['battery_kwh']} kWh  ({r['battery_ah']:.0f} Ah @ {r['battery_voltage']} V)",
        f"  Inverter rating : {r['inverter_w']:,} W  ({r['inverter_w']/1000:.1f} kVA)",
        "",
        "Disclaimer: Estimates only. Consult a certified solar installer.",
    ]
    with open(filename, "w") as f:
        f.write("\n".join(lines))
    return filename

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.system("clear" if os.name == "posix" else "cls")
    print(clr("""
  ╔══════════════════════════════════════════════════════════╗
  ║   ☀   S O L A R   L O A D   C A L C U L A T O R   ☀   ║
  ║      Size your off-grid or hybrid solar system           ║
  ╚══════════════════════════════════════════════════════════╝""", BOLD, YELLOW))
    print(info("This tool calculates the minimum recommended solar panel capacity,"))
    print(info("battery bank size, and inverter rating for your household loads.\n"))

    appliances = collect_appliances()
    params     = get_system_params()
    psh, days, volts, eff, dod, sf = params
    results    = calculate(appliances, psh, days, volts, eff, dod, sf)
    print_report(appliances, results)

    save = prompt("Save report to solar_report.txt? (y/n)", default="y").lower()
    if save == "y":
        fname = save_report(appliances, results, params)
        print(ok(f"Report saved → {fname}\n"))

    again = prompt("Calculate another scenario? (y/n)", default="n").lower()
    if again == "y":
        main()
    else:
        print(clr("\n  Thanks for using Solar Load Calculator. Stay powered! ☀\n", BOLD, GREEN))

if __name__ == "__main__":
    main()
