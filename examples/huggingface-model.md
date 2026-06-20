# Monitoring a Hugging Face model download

If you're pulling models from Hugging Face, `hf download` writes sharded `.safetensors` files one at a time — perfect for Download Watcher.

## Setup

```bash
# Check how many shards the model has
# Usually visible on the model page or:
ls -1 ~/.cache/huggingface/hub/models--org--model/snapshots/*/ 2>/dev/null | grep safetensors | wc -l

# Create a systemd service (optional but recommended)
cat > ~/.config/systemd/user/hf-model-download.service << 'SERVICE'
[Unit]
Description=Download model from Hugging Face
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/home/greg/.local/bin/hf download org/model --local-dir /media/greg/drive/model-name --max-workers 1
MemoryMax=10G
IOSchedulingClass=2
IOSchedulingPriority=7
Nice=15

[Install]
WantedBy=default.target
SERVICE

# Start it
systemctl --user daemon-reload
systemctl --user start hf-model-download
```

## Watcher setup

```bash
bash watcher/dl-setup.sh
# Directory: /media/greg/drive/model-name
# Total files: 282 (or however many shards)
# Service name: hf-model-download

# Launch
bash watcher/dl-launcher.sh
```

The dashboard will show each shard landing, track the total size growing, and give you an ETA based on actual transfer speed. If the download stalls or fails, the alarm fires.

## Why --max-workers 1?

Hugging Face's downloader defaults to parallel workers. On spinning rust or USB drives, this thrashes the disk and actually slows things down. Single-worker is slower per-shard but more predictable and gentler on the drive.
