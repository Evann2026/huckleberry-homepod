# Huckleberry → HomePod Reminders

This project runs continuously on a Mac, reads Huckleberry SweetSpot and feeding data, and announces reminders in Chinese on a HomePod via AirPlay.

The default quiet period is from 9:00 PM (inclusive) to 8:00 AM (exclusive). Reminders that become due during quiet hours are not played later. Announcements use 70% volume by default; change `HOMEPOD_VOLUME` in `.env` to adjust it.

> Huckleberry does not offer a public API. This project uses an unofficial, reverse-engineered client that may stop working after backend changes. It only reads Huckleberry data and never writes to it.

## 1. Installation

You need:

- A Mac that can stay powered on
- A HomePod on the same network as the Mac
- A Huckleberry account with SweetSpot enabled

```bash
brew install uv
git clone https://github.com/Evann2026/huckleberry-homepod.git
cd ~/Projects/huckleberry-homepod
uv python install 3.14
uv sync
cp .env.example .env
```

Open `.env` and configure:

- `HUCKLEBERRY_EMAIL` and `HUCKLEBERRY_PASSWORD`
- `BABY_NAME`: the name used in announcements
- `TIMEZONE`: your local time zone
- The reminder timing, volume, and quiet-hour settings as needed

The `.env` file is ignored by Git and remains on your Mac. Never commit, screenshot, or share it.

## 2. Find and test your HomePod

Make sure the Mac and HomePod are on the same network. In the Apple Home app, set **Allow Speaker & TV Access** to **Anyone On the Same Network**.

```bash
uv run hb-homepod scan
```

Find the HomePod's `Identifier` in the results, copy it to `HOMEPOD_ID` in `.env`, and test playback:

```bash
uv run hb-homepod test-homepod
```

macOS may ask for Local Network permission the first time.

## 3. Verify Huckleberry data

Enable SweetSpot Alert in Huckleberry first. The default sleep configuration uses the three-nap SweetSpot schedule.

The feeding reminder reads the latest nursing or bottle entry and treats three hours later as the next feeding time. It becomes eligible for playback after 2 hours and 29 minutes to compensate for up to one minute of polling delay, while the spoken message still says that 30 minutes remain.

Sleep reminders use the same compensation: they become eligible 16 minutes before the SweetSpot time, while the spoken message says that 15 minutes remain.

```bash
# Print the current schedule without announcing
DRY_RUN=1 uv run hb-homepod inspect

# Sync once and announce any reminder that is due
uv run hb-homepod once

# Run continuously in the foreground
uv run hb-homepod run
```

If the account contains multiple child profiles, set `HUCKLEBERRY_CHILD_ID` to the desired profile ID. The first profile is used by default.

## 4. Run automatically at login

After completing the previous steps, install the background service:

```bash
chmod +x scripts/install-launch-agent.sh
./scripts/install-launch-agent.sh
```

Logs are written to `~/Library/Logs/huckleberry-homepod/`. To uninstall:

```bash
launchctl bootout "gui/$(id -u)/com.local.huckleberry-homepod"
rm ~/Library/LaunchAgents/com.local.huckleberry-homepod.plist
```

## Keep the Mac awake

The display may turn off, but the Mac itself must not sleep. In System Settings, enable the option that prevents automatic sleep while the display is off and the Mac is connected to power.
