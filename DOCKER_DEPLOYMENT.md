# Docker Deployment Guide - Radio Monitor

**Pre-built images from GitHub Container Registry (GHRC)**

No cloning required - just pull and run!

---

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose (included with Docker Desktop)

---

## Quick Start (3 Steps)

### 1. Create Project Directory

```bash
mkdir radio-monitor
cd radio-monitor
```

### 2. Download docker-compose File

**Option A: Download directly**
```bash
# Download the release docker-compose file
curl -O https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml
# Or on Windows:
# Invoke-WebRequest -Uri "https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml" -OutFile "docker-compose.release.yml"
```

**Option B: Create manually**
- Save the content from `docker-compose.release.yml` in the GitHub repo
- Save as `docker-compose.release.yml` in your directory

### 3. Start Container

```bash
docker-compose -f docker-compose.release.yml up -d
```

**Access web interface:** http://localhost:5000

---

## First-Time Setup

1. **Open the web interface** (http://localhost:5000)
2. **Follow the 5-step setup wizard**
3. **Configure integrations** (Lidarr, Plex, MusicBrainz)
4. **Start monitoring** radio stations

---

## Common Operations

### View Logs

```bash
# Follow logs in real-time
docker-compose -f docker-compose.release.yml logs -f

# Last 100 lines
docker-compose -f docker-compose.release.yml logs --tail=100
```

### Stop Container

```bash
# Stop (keeps data)
docker-compose -f docker-compose.release.yml stop

# Stop and remove container (keeps data volume)
docker-compose -f docker-compose.release.yml down

# Stop and remove everything including volumes (DELETES DATA)
docker-compose -f docker-compose.release.yml down -v
```

### Restart Container

```bash
docker-compose -f docker-compose.release.yml restart
```

### Update to Latest Version

```bash
# Pull latest image
docker-compose -f docker-compose.release.yml pull

# Restart with new image
docker-compose -f docker-compose.release.yml up -d
```

### Access Container Shell

```bash
docker-compose -f docker-compose.release.yml exec radio-monitor bash
```

---

## Data Persistence

All data is stored in the `./data` directory:

```
data/
├── radio_songs.db                # Database (all songs, artists, plays)
├── radio_monitor_settings.json   # Settings
├── radio_monitor.log             # Application logs
└── auto-backups/                  # Database backups
```

### Backup Data

```bash
# Stop container
docker-compose -f docker-compose.release.yml down

# Backup data directory
cp -r data data-backup-$(date +%Y%m%d)

# Restart
docker-compose -f docker-compose.release.yml up -d
```

### Restore Data

```bash
# Stop container
docker-compose -f docker-compose.release.yml down

# Restore from backup
rm -rf data
cp -r data-backup-20260220 data

# Restart
docker-compose -f docker-compose.release.yml up -d
```

---

## Configuration

### Change Port

Edit `docker-compose.release.yml`:

```yaml
ports:
  - "8000:5000"  # Use port 8000 instead of 5000
```

Then restart:
```bash
docker-compose -f docker-compose.release.yml up -d
```

### Change Timezone

Edit `docker-compose.release.yml`:

```yaml
environment:
  - TZ=America/New_York  # Change to your timezone
```

Available timezones: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

### Adjust Resource Limits

Edit `docker-compose.release.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Increase to 2 CPUs
      memory: 2G       # Increase to 2GB RAM
```

---

## Security Features

The container includes several security features:

- ✅ **Non-root user** - Runs as unprivileged `radio` user (UID 1000)
- ✅ **Minimal base image** - Based on `python:3.11-slim` (~130MB)
- ✅ **Multi-stage build** - Separates build and runtime dependencies
- ✅ **Small attack surface** - Only 7 Python dependencies
- ✅ **Health checks** - Automatic health monitoring
- ✅ **Resource limits** - CPU and memory constraints
- ✅ **Logging** - Rotating logs (10MB max, 3 files)

---

## Available Image Tags

```bash
# Latest version (recommended)
ghcr.io/allurjj/radio-monitor:latest

# Specific version
ghcr.io/allurjj/radio-monitor:v1.1.0

# Specific version + patch
ghcr.io/allurjj/radio-monitor:v1.1.0

# Multi-architecture support (amd64, arm64)
```

### Use Specific Version

Edit `docker-compose.release.yml`:

```yaml
services:
  radio-monitor:
    image: ghcr.io/allurjj/radio-monitor:v1.1.0  # Pin specific version
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose -f docker-compose.release.yml logs radio-monitor

# Common issues:
# 1. Port 5000 already in use -> Change port mapping
# 2. Permission denied -> Fix data directory permissions
# 3. Out of memory -> Increase memory limit
```

### Can't Access Web Interface

```bash
# Check container is running
docker-compose -f docker-compose.release.yml ps

# Check port mapping
docker port radio-monitor

# Test from inside container
docker-compose -f docker-compose.release.yml exec radio-monitor python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')"

# Check firewall (allow port 5000)
```

### Database Issues

```bash
# Stop container
docker-compose -f docker-compose.release.yml down

# Start fresh (removes database)
rm -rf data
docker-compose -f docker-compose.release.yml up -d

# Or restore from backup
cp -r data-backup-YYYYMMDD data
docker-compose -f docker-compose.release.yml up -d
```

### View Resource Usage

```bash
docker stats radio-monitor
```

---

## Production Deployment

### Reverse Proxy (Nginx)

For production use, add Nginx as a reverse proxy:

```yaml
# Add to docker-compose.release.yml
nginx:
  image: nginx:alpine
  container_name: radio-monitor-nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro
  depends_on:
    - radio-monitor
  restart: unless-stopped
  networks:
    - radio-monitor-net
```

### SSL/HTTPS

Use Let's Encrypt with Nginx:

```bash
# Install certbot on host
apt-get install certbot

# Generate certificate
certbot certonly --standalone -d radio-monitor.example.com

# Copy certificates to nginx/ssl/
```

---

## Advanced: Build from Source

If you prefer to build the image yourself (instead of using pre-built):

```bash
# Clone repository
git clone https://github.com/allurjj/radio-monitor.git
cd radio-monitor

# Build and run
docker-compose -f docker/docker-compose.yml up -d
```

---

## System Requirements

### Minimum

- **CPU:** 1 core
- **RAM:** 512MB
- **Disk:** 500MB (image) + data storage

### Recommended

- **CPU:** 2 cores
- **RAM:** 1GB
- **Disk:** 2GB (image) + 5GB (data)

---

## For More Information

- **Main Repository:** https://github.com/allurjj/radio-monitor
- **Documentation:** https://github.com/allurjj/radio-monitor/blob/main/README.md
- **Docker Documentation:** https://docs.docker.com/
- **GitHub Container Registry:** https://github.com/allurjj/radio-monitor/pkgs/container/radio-monitor

---

## Version Compatibility

| Radio Monitor Version | Docker Image Tag | Status |
|----------------------|------------------|--------|
| 1.1.0 | `v1.1.0`, `latest` | ✅ Current |
| 1.0.0 | `v1.0.0` | ✅ Stable |

---

**Last Updated:** 2026-02-20
**Docker Image:** ghcr.io/allurjj/radio-monitor:latest
