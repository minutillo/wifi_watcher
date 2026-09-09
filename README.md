# WiFi Watcher

WiFi Watcher is a small Python utility that helps detect when neighborhood power is restored after an outage.

I built this for a practical home power scenario: when utility power fails, I use a transfer switch (generator interlock kit) to safely run my home from a generator. While using a generator interlock kit, it can be hard to know exactly when utility power is back. This script monitors nearby Wi-Fi networks and alerts me when networks reappear, which is a strong signal that grid power has returned in the area.

## How it works

- Runs `system_profiler SPAirPortDataType` on macOS at a fixed interval.
- Parses nearby Wi-Fi network data.
- Tracks SSIDs seen over time.
- Sends an email when newly discovered networks appear.
- Appends scan results to:
  - `wifi_watcher.log` (raw output)
  - `wifi_watcher.csv` (structured history)

## Requirements

- macOS (uses `system_profiler`)
- Python 3.9+
- A Gmail account configured with an App Password for SMTP

## Setup

1. Clone the repository.
2. Create a virtual environment (optional but recommended).
3. Install dependencies:

```bash
pip install python-dotenv
```

4. Create a `.env` file in the repository root using `sample.env` as a guide:

```env
SENDER_EMAIL="your_email@gmail.com"
SENDER_PASSWORD="your_16_digit_google_app_password"
RECIPIENT_EMAIL="destination_email@example.com"
```

## Usage

Run:

```bash
python wifi_watcher.py
```

The script scans continuously every 15 seconds by default and sends an email when new networks are detected.

Stop with `Ctrl+C`.

## Configuration

In `wifi_watcher.py`:

- `SCAN_INTERVAL_SECONDS` controls scan frequency.
- `RAW_LOG_FILENAME` controls raw log output filename.
- `CSV_FILENAME` controls CSV output filename.

## Notes

- For Gmail, use an App Password (not your normal Google password).
- Keep your `.env` file private. It is ignored by `.gitignore` by default.
- Detection is heuristic: returning Wi-Fi networks usually indicate local power restoration, but results can vary by environment.
