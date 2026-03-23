# Database Upload Scripts

Systemd timer that periodically uploads a SQLite database file to a Discord webhook.

## Prerequisites

- `curl`
- `systemd` with user units enabled (`loginctl enable-linger <user>`)

## Installation

### 1. Configure the webhook URL

```bash
cp scripts/upload-db.env.example ~/.config/upload-db.env
chmod 600 ~/.config/upload-db.env
```

Edit `~/.config/upload-db.env` and set `WEBHOOK_URL` to your Discord webhook URL
(`https://discord.com/api/webhooks/{id}/{token}`).

### 2. Make the script executable

```bash
chmod +x scripts/upload-db.sh
```

### 3. Edit the service unit

Open `scripts/upload-db.service` and update the `ExecStart` line to point to the
actual paths for the script and database on your system. The `%h` specifier
expands to the user's home directory at runtime.

### 4. Install the systemd units

```bash
mkdir -p ~/.config/systemd/user
cp scripts/upload-db.service scripts/upload-db.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now upload-db.timer
```

### 5. Enable linger (so timers run when logged out)

```bash
loginctl enable-linger "$USER"
```

## Usage

Check timer status:

```bash
systemctl --user status upload-db.timer
systemctl --user list-timers
```

Trigger a manual run:

```bash
systemctl --user start upload-db.service
```

View logs:

```bash
journalctl --user -u upload-db.service
```

## Customisation

- **Schedule**: edit `OnCalendar=` in `upload-db.timer` (e.g. `*-*-* 03:00:00` for 3 AM daily).
- **DB path**: edit the `ExecStart` line in `upload-db.service`.
