# Monitoring an rsync transfer

Large rsync jobs over the network are a perfect use case. Wrap it in a systemd service and point Download Watcher at the destination.

## Setup

Create a service wrapper — rsync doesn't write files one-at-a-time the same way, but you can watch byte growth:

```bash
cat > ~/.config/systemd/user/big-rsync.service << 'SERVICE'
[Unit]
Description=Large rsync transfer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/rsync -avhP --progress /media/greg/internal-drive/data/ /media/greg/external-drive/backup/data/
MemoryMax=4G
IOSchedulingClass=2
IOSchedulingPriority=7
Nice=15

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user start big-rsync
```

## Watcher setup

```bash
bash watcher/dl-setup.sh
# Directory: /media/greg/external-drive/backup/data/
# Total files: 1 (or the file count if you know it — set to 0 for byte-only tracking)
# Service name: big-rsync

bash watcher/dl-launcher.sh
```

With `TOTAL_FILES=0`, the progress bar goes by byte count instead of file count — you'll see total size grow, speed, and ETA based on rate.

For multi-file rsync where you know the exact file count:
```bash
# Count files to transfer first
rsync -av --dry-run /source/ /dest/ | tail -n +2 | head -n -3 | wc -l
# Use that number in setup
```