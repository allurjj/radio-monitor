# Docker Deployment - Radio Monitor

This directory contains Docker configuration files for containerized deployment of Radio Monitor.

## Files

- **Dockerfile** - Container image definition
- **docker-compose.yml** - Container orchestration configuration
- **README.md** - This file

## Quick Start

### Prerequisites

- Docker Desktop installed (Windows/Mac) or Docker Engine (Linux)
- Docker Compose (included with Docker Desktop)

### Build and Run

```bash
# From project root
cd docker

# Build and start container
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

**Access web interface:** http://localhost:5000

## Common Operations

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f radio-monitor
```

### Stop Container

```bash
# Stop (keeps data)
docker-compose stop

# Stop and remove container (keeps data volume)
docker-compose down

# Stop and remove everything including volumes (DELETES DATA)
docker-compose down -v
```

### Restart Container

```bash
docker-compose restart
```

### Update Application

```bash
# Stop container
docker-compose down

# Pull latest code (if using git)
cd ..
git pull
cd docker

# Rebuild image
docker-compose build --no-cache

# Start container
docker-compose up -d
```

### Access Container Shell

```bash
# Open bash shell inside running container
docker-compose exec radio-monitor bash

# Or using docker command
docker exec -it radio-monitor bash
```

### Backup Data

```bash
# Stop container
docker-compose down

# Backup data directory
cp -r data data-backup-$(date +%Y%m%d)

# Restart
docker-compose up -d
```

### Restore Data

```bash
# Stop container
docker-compose down

# Restore from backup
rm -rf data
cp -r data-backup-20260218 data

# Restart
docker-compose up -d
```

## Configuration

### Environment Variables

Edit `docker-compose.yml` to customize:

```yaml
environment:
  - TZ=America/Chicago           # Set your timezone
  - PYTHONUNBUFFERED=1
  - PYTHONDONTWRITEBYTECODE=1
```

### Port Mapping

Default: `5000:5000` (host:container)

To change host port (e.g., 8000):
```yaml
ports:
  - "8000:5000"
```

### Resource Limits

Default limits: 1 CPU, 1GB RAM

Adjust in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

## Data Persistence

Data is stored in the `data/` directory (relative to docker-compose.yml):

```
data/
├── radio_songs.db              # Database (all songs, artists, plays)
├── radio_monitor_settings.json # Settings
├── radio_monitor.log           # Application logs
└── auto-backups/               # Database backups
```

This directory is mounted as a Docker volume, so data persists even if the container is removed.

### Volume Location

**Windows:** `C:\Users\Public\RadioMonitor\data` (or current directory)
**Linux/Mac:** `./data` (relative to docker-compose.yml)

Check actual location:
```bash
docker inspect radio-monitor | grep -A 10 Mounts
```

## Deployment on Another Machine

### Method 1: Copy Project Files

```bash
# On source machine
cd ..
tar czf radio-monitor-docker.tar.gz \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='data' \
  --exclude='venv' \
  .

# Transfer to target machine
scp radio-monitor-docker.tar.gz user@target:/path/to/destination/

# On target machine
tar xzf radio-monitor-docker.tar.gz
cd radio-monitor/docker
docker-compose up -d
```

### Method 2: Docker Registry

```bash
# Build and tag image
docker build -t your-registry/radio-monitor:1.0.0 -f docker/Dockerfile .

# Login to registry
docker login your-registry

# Push image
docker push your-registry/radio-monitor:1.0.0

# On target machine
docker pull your-registry/radio-monitor:1.0.0
docker run -d -p 5000:5000 -v $(pwd)/data:/app/data your-registry/radio-monitor:1.0.0
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs radio-monitor

# Common issues:
# 1. Port already in use -> Change port mapping
# 2. Permission denied -> Fix data directory permissions
# 3. Out of memory -> Increase memory limit
```

### Can't Access Web Interface

```bash
# Check container is running
docker-compose ps

# Check port mapping
docker port radio-monitor

# Test from inside container
docker-compose exec radio-monitor curl http://localhost:5000

# Check firewall (allow port 5000)
```

### Database Issues

```bash
# Stop container
docker-compose down

# Start fresh (removes database)
rm -rf data
docker-compose up -d

# Or restore from backup
cp -r data-backup-YYYYMMDD data
docker-compose up -d
```

### View Container Resource Usage

```bash
docker stats radio-monitor
```

## Production Deployment

### Reverse Proxy (Nginx)

For production use, add Nginx as a reverse proxy (see docker-compose.yml).

Uncomment the nginx section and create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream radio_monitor {
        server radio-monitor:5000;
    }

    server {
        listen 80;
        server_name radio-monitor.example.com;

        location / {
            proxy_pass http://radio_monitor;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### SSL/HTTPS

Use Nginx with Let's Encrypt:

```bash
# Install certbot
apt-get install certbot

# Generate certificate
certbot certonly --standalone -d radio-monitor.example.com

# Update nginx.conf to use SSL
```

### Automatic Backups

Add backup service to docker-compose.yml or use host cron:

```bash
# Host cron (daily at 2 AM)
0 2 * * * cd /path/to/radio-monitor/docker && docker-compose exec -T radio-monitor python -m radio_monitor.cli --backup-db
```

## For More Information

- **Main Deployment Guide:** ../DeploymentInfo.md
- **Complete Docker Guide:** ../DockerInfo.md
- **Project README:** ../README.md
- **Docker Documentation:** https://docs.docker.com/
- **Docker Compose Documentation:** https://docs.docker.com/compose/
