# Docker Quick Start - Radio Monitor

🚀 **Up and running in 2 minutes**

---

## One-Line Command

```bash
curl -fsSL https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml -o docker-compose.yml && docker-compose up -d
```

**Then open:** http://localhost:5000

---

## Windows Quick Start

```powershell
# Download docker-compose file
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml" -OutFile "docker-compose.yml"

# Start container
docker-compose up -d
```

**Then open:** http://localhost:5000

---

## What Happens Next?

1. **Container starts** (~30 seconds)
2. **Open browser** to http://localhost:5000
3. **Follow the 5-minute setup wizard**
4. **Start monitoring** radio stations

---

## Update Later

```bash
docker-compose pull && docker-compose up -d
```

---

## Stop/Start

```bash
# Stop
docker-compose stop

# Start
docker-compose start

# Remove container (keeps data)
docker-compose down
```

---

## Where's My Data?

All data in `./data` directory:
- Database: `./data/radio_songs.db`
- Settings: `./data/radio_monitor_settings.json`
- Logs: `./data/radio_monitor.log`

---

## Need Help?

- **Full Guide:** [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **GitHub:** https://github.com/allurjj/radio-monitor
