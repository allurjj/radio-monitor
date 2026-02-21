# Docker Deployment Architecture - Radio Monitor

**Visual Guide to Deployment Options**

---

## 📊 Deployment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Repository                         │
│                    (allurjj/radio-monitor)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Push to main / tags
                           ▼
                  ┌─────────────────┐
                  │  GitHub Actions  │
                  │  Auto-Build     │
                  └────────┬─────────┘
                           │
                           │ docker build + push
                           ▼
          ┌──────────────────────────────────────┐
          │  GitHub Container Registry (GHRC)    │
          │  ghcr.io/allurjj/radio-monitor:latest│
          └──────────┬───────────────────────────┘
                     │
                     │ docker pull
                     ▼
    ┌────────────────────────────────────────────────────────┐
    │              User's Machine (Docker)                   │
    │                                                        │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │  docker-compose.release.yml                      │  │
    │  │                                                  │  │
    │  │  image: ghcr.io/allurjj/radio-monitor:latest     │  │
    │  │  volumes: ./data → /app/data                    │  │
    │  │  ports: 5000:5000                               │  │
    │  └─────────────────────────────────────────────────┘  │
    │                        │                              │
    │                        │ docker-compose up -d        │
    │                        ▼                              │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │     Container (radio-monitor)                   │  │
    │  │                                                 │  │
    │  │  • User: radio (UID 1000, non-root)            │  │
    │  │  • Base: python:3.11-slim (~130MB)             │  │
    │  │  • Port: 5000 (Flask GUI)                      │  │
    │  │  • Data: /app/data (persistent volume)         │  │
    │  │  • Health: HTTP check every 30s                │  │
    │  └─────────────────────────────────────────────────┘  │
    │                        │                              │
    │                        ▼                              │
    │  ┌─────────────────────────────────────────────────┐  │
    │  │      Web Interface (http://localhost:5000)       │  │
    │  │                                                 │  │
    │  │  • Setup Wizard (5 steps)                       │  │
    │  │  • Dashboard (18 pages)                         │  │
    │  │  • Radio Scraping (7 stations)                  │  │
    │  │  • Lidarr Integration                           │  │
    │  │  • Plex Playlists                               │  │
    │  └─────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────┘
```

---

## 🔐 Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     Security Architecture                     │
└─────────────────────────────────────────────────────────────┘

  ┌───────────────────────────────────────────────────────┐
  │  Layer 1: Container Security                           │
  │  • Non-root user (radio:1000)                         │
  │  • Read-only root filesystem (except /app/data)       │
  │  • No shell access for non-root users                 │
  │  • Resource limits (1 CPU, 1GB RAM)                   │
  └───────────────────────────────────────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────────────┐
  │  Layer 2: Image Security                               │
  │  • Minimal base image (python:3.11-slim)              │
  │  • Digest-pinned (prevents supply chain attacks)      │
  │  • Multi-stage build (no build tools in runtime)      │
  │  • Aggressive cleanup (APT cache, tmp files)          │
  │  • Small attack surface (only 7 dependencies)         │
  └───────────────────────────────────────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────────────┐
  │  Layer 3: CI/CD Security                               │
  │  • Trivy vulnerability scanner (weekly)               │
  │  • SBOM generation (Software Bill of Materials)       │
  │  • GitHub Security tab integration                    │
  │  • Fails on CRITICAL/HIGH severity                    │
  └───────────────────────────────────────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────────────┐
  │  Layer 4: Runtime Security                             │
  │  • Health checks (HTTP every 30s)                     │
  │  • Logging rotation (10MB max, 3 files)               │
  │  • Restart policy (unless-stopped)                    │
  │  • Network isolation (bridge network)                 │
  └───────────────────────────────────────────────────────┘
```

---

## 🔄 Update Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Developer      │────▶│  GitHub Push    │────▶│  GitHub Actions │
│  (Code Change)  │     │  (main branch)  │     │  (Auto-Build)   │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                              │
                                                              ▼
                                                    ┌─────────────────┐
                                                    │  GHCR Push      │
                                                    │  :latest tag    │
                                                    └────────┬────────┘
                                                             │
                                                             ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User Pull      │────▶│  Docker Compose │────▶│  Container      │
│  (New Image)    │     │  (Restart)      │     │  (Updated)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**User commands:**
```bash
# Pull latest image
docker-compose -f docker-compose.release.yml pull

# Restart with new image
docker-compose -f docker-compose.release.yml up -d
```

---

## 📦 Image Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                     Image Sizes                             │
└─────────────────────────────────────────────────────────────┘

  v1.0.0 (with Selenium)         v1.1.0 (current)
  ┌─────────────────────┐        ┌─────────────────────┐
  │  Base: 50 MB        │        │  Base: 50 MB        │
  │  + Python: 30 MB    │        │  + Python: 30 MB    │
  │  + Deps: 15 MB      │        │  + Deps: 5 MB       │
  │  + Chrome: 80 MB    │  →     │  + App: 10 MB       │
  │  + App: 10 MB       │        │                      │
  │  = ~185 MB          │        │  = ~95 MB            │
  └─────────────────────┘        └─────────────────────┘

  Compressed: ~75 MB              Compressed: ~45 MB
  Uncompressed: ~200 MB           Uncompressed: ~130 MB

  Savings: ~30 MB (40% reduction)
```

---

## 🚀 Deployment Comparison

```
┌─────────────────────────────────────────────────────────────┐
│              Deployment Options Comparison                   │
└─────────────────────────────────────────────────────────────┘

  Option 1: Pre-Built (Recommended)        Option 2: Build from Source
  ┌───────────────────────────┐           ┌───────────────────────────┐
  │ • Time: 2 minutes         │           │ • Time: 5-10 minutes       │
  │ • Complexity: Low         │           │ • Complexity: Medium       │
  │ • Flexibility: Low        │           │ • Flexibility: High        │
  │ • Updates: One command    │           │ • Updates: Manual rebuild  │
  │ • Disk: ~45 MB            │           │ • Disk: ~45 MB             │
  │ • Multi-arch: Yes         │           │ • Multi-arch: Manual       │
  │                           │           │                           │
  │ docker-compose pull &&    │           │ docker-compose build &&   │
  │ docker-compose up -d      │           │ docker-compose up -d      │
  └───────────────────────────┘           └───────────────────────────┘

  Use when:                          Use when:
  • Quick deployment needed                 • Code customization needed
  • No code modifications                  • Development/testing
  • Production deployment                  • Learning Docker
  • Regular updates                        • Offline environments
```

---

## 🔍 Container Structure

```
┌─────────────────────────────────────────────────────────────┐
│                 Container File System                        │
└─────────────────────────────────────────────────────────────┘

  / (root, read-only except /app/data)
  │
  ├─── /app
  │    ├─── /radio_monitor/       (application code, read-only)
  │    ├─── /templates/           (Jinja2 templates, read-only)
  │    ├─── /prompts/             (AI prompts, read-only)
  │    └─── /data/                (PERSISTENT VOLUME)
  │         ├─── radio_songs.db
  │         ├─── radio_monitor_settings.json
  │         ├─── radio_monitor.log
  │         └─── auto-backups/
  │
  ├─── /usr/local                (Python dependencies, read-only)
  │    └─── lib/python3.11/
  │
  ├─── /tmp                      (tmpfs, in-memory only)
  │
  └─── /home/radio               (user home, read-only)
```

---

## 🌐 Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Network Layout                           │
└─────────────────────────────────────────────────────────────┘

  Host Machine (port 5000)
          │
          │ 0.0.0.0:5000 → 5000
          ▼
  ┌─────────────────────────┐
  │   Docker Bridge         │
  │   (radio-monitor-net)   │
  └──────────┬──────────────┘
             │
             │ 172.18.0.2:5000
             ▼
  ┌─────────────────────────┐
  │   Container             │
  │   (radio-monitor)       │
  │                         │
  │   Flask (0.0.0.0:5000)  │
  └─────────────────────────┘

  Accessible via:
  • http://localhost:5000
  • http://127.0.0.1:5000
  • http://192.168.x.x:5000 (LAN IP)
```

---

## 📊 Performance Metrics

```
┌─────────────────────────────────────────────────────────────┐
│                   Resource Usage                             │
└─────────────────────────────────────────────────────────────┘

  Startup Time:      ~30-40 seconds
  Memory Usage:      ~150-300 MB (idle)
  CPU Usage:         ~5-10% (idle), ~50% (scraping)
  Disk Usage:        ~130 MB (image) + data storage
  Network:           ~10-50 MB/day (scraping)

  Limits (configurable):
  • CPU: 1.0 cores (can be increased)
  • Memory: 1 GB (can be increased)
```

---

## ✅ Checklist

### For Users:
- [ ] Install Docker Desktop
- [ ] Download `docker-compose.release.yml`
- [ ] Run `docker-compose up -d`
- [ ] Open http://localhost:5000
- [ ] Complete setup wizard
- [ ] Start monitoring

### For Updates:
- [ ] Run `docker-compose pull`
- [ ] Run `docker-compose up -d`
- [ ] Verify version in GUI

### For Production:
- [ ] Use `Dockerfile.secure`
- [ ] Add Nginx reverse proxy
- [ ] Enable SSL/HTTPS
- [ ] Set up automated backups
- [ ] Monitor logs regularly
- [ ] Pin specific version tags

---

**Last Updated:** 2026-02-20
**Version:** 1.1.0
**Architecture:** Multi-stage, security-hardened, minimal footprint
