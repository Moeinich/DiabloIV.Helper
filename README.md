# Diablo IV Rotation Assistant

A combat rotation assistant for Diablo IV with macro capabilities. Configure per-skill behavior modes, priorities, cooldown detection, and more through an integrated overlay UI.

## Features

- **Macro System** — Per-skill configurable modes: ready, delay, hold, hp_guard, resource_guard
- **Pixel-Based Cooldown Detection** — Calibrate 2 check pixels per skill for reliable ready/cooldown state
- **HP & Resource Orb Reading** — Circle-based orb fill detection for HP and resource thresholds
- **Live Visualizer** — Real-time overlay showing skill states with color-coded indicators
- **Integrated Toolbox** — All configuration accessible directly from the overlay bar
- **Per-Class Configs** — Each class has its own config file for easy sharing (`src/config/ClassName/config.yml`)
- **Humanized Casting** — Layered randomized delays and micro-variations for natural behavior

## Requirements

- Python 3.9+
- Windows (uses Win32 API for pixel reading)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run:
   ```
   run.bat
   ```

## Usage

1. Select your class from the dropdown in the overlay bar
2. Open the **TOOLBOX** to configure skill positions, keybinds, and macro rules
3. Calibrate each skill's cooldown detection by clicking **CAL** and picking 2 pixels on the skill icon
4. Set up HP/Resource orb detection in the **Bar Setup** tab
5. Press the configured hotkey (default: `X`) or click **START** to begin rotation

## Controls

- **Hotkey** (default `X`) — Toggle rotation on/off
- **LIVE** — Toggle live skill state visualizer
- **TOOLBOX** — Open/close integrated configuration panel
- **EXIT** — Stop and quit

## Configuration

Configuration is stored per-class in `src/config/`:

```
src/config/
  shared.yml          # Global settings (hotkey, orb calibration, etc.)
  Barbarian/config.yml
  Druid/config.yml
  Sorceress/config.yml
  ...
```

Share a class config by copying its folder to another installation.

## Credits

This project started from [DarkDBx/DiabloIV.Helper](https://github.com/DarkDBx/DiabloIV.Helper).
