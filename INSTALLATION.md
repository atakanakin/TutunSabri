# Installation Guide

This guide targets Ubuntu and installs the bot as a long-running system service.

## 1. Install system packages

```bash
sudo apt update
sudo apt install -y git curl redis-server python3 python3-venv python3-pip
```

## 2. Clone the project

```bash
cd ~
sudo git clone https://github.com/atakanakin/TutunSabri.git tutunsabri
sudo chown -R $USER:$USER ~/tutunsabri
cd ~/tutunsabri
```

## 3. Install `uv`

Install `uv` with the official installer:

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

Add `uv` to `PATH` for Bash:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Add `uv` to `PATH` for Zsh:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Make sure `uv` is reachable:

```bash
uv --version
```

## 4. Create the environment file

Create `.env` in the project root:

```bash
cd ~/tutunsabri
cp .example.env .env
```

Fill out the BOT_TOKEN part

## 5. Install Python dependencies

```bash
uv sync
```

## 6. Start and enable Redis

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server
```

## 7. Initialize the database

The project auto-creates tables on startup. You can also initialize them manually once:

```bash
uv run python init_db.py
```

## 8. Create the first admin user

Use the bootstrap script with a Telegram private chat ID:

```bash
uv run python create_admin_user.py <TELEGRAM_CHAT_ID>
```

## 9. Install systemd units

Copy the provided unit files:

```bash
sudo cp deploy/systemd/tutunsabri-bot.service /etc/systemd/system/
sudo cp deploy/systemd/tutunsabri-worker.service /etc/systemd/system/
sudo cp deploy/systemd/tutunsabri.target /etc/systemd/system/
```

Edit these fields in both service files before enabling them:

- `User`
- `Group`
- `Environment=PATH=...`

If your `uv` binary is under another path, update the `PATH` line or replace `/usr/bin/env uv` with the absolute path to `uv`.

The provided service files are currently prepared for this layout:

- user: `ubuntu`
- home: `/home/ubuntu`
- project path: `/home/ubuntu/tutunsabri`

## 10. Enable and start the services

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tutunsabri.target
```

## 11. Check service status

```bash
sudo systemctl status tutunsabri-bot.service
sudo systemctl status tutunsabri-worker.service
sudo systemctl status tutunsabri.target
```

## 12. Follow logs

```bash
sudo journalctl -u tutunsabri-bot.service -f
sudo journalctl -u tutunsabri-worker.service -f
```

## 13. Restart after configuration changes

```bash
sudo systemctl restart tutunsabri.target
```

## 14. Optional manual run commands

Use these only for direct troubleshooting:

```bash
uv run python bot.py
uv run taskiq worker tasks.worker:broker
```

## Notes

- The bot must run from the project root because it uses local paths such as `data/` and `.env`.
- Redis must be running before the worker starts.
- SQLite is stored under `./data/app.db` by default.
- On every startup, the bot restores open YHT search tasks from the database.
