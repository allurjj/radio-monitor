# Docker Deployment Options - Radio Monitor

This directory contains Docker configurations for different deployment scenarios.

---

## 📦 Deployment Options

### Option 1: Pre-Built Image (Recommended for Users)

**File:** `../docker-compose.release.yml` (project root)

**Best for:** Users who want to run Radio Monitor without building anything

**Features:**
- ✅ Pulls pre-built images from GitHub Container Registry (GHRC)
- ✅ No cloning required
- ✅ Fast deployment (2 minutes)
- ✅ Automatic updates via `docker-compose pull`
- ✅ Multi-architecture support (amd64, arm64)

**Quick Start:**
```bash
curl -O https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml
docker-compose -f docker-compose.release.yml up -d
```

**Documentation:** [DOCKER_DEPLOYMENT.md](../DOCKER_DEPLOYMENT.md)

---

### Option 2: Build from Source

**File:** `docker-compose.yml` (this directory)

**Best for:** Developers and users who want to build from source

**Features:**
- ✅ Builds from local code
- ✅ Full control over build process
- ✅ Can modify code before building
- ✅ Useful for development/testing

**Quick Start:**
```bash
# From project root
cd docker
docker-compose up -d
```

**Documentation:** [README_BUILD.md](README_BUILD.md) (this file)

---

## 📁 Files in This Directory

| File | Purpose |
|------|---------|
| `Dockerfile` | Standard container image definition |
| `Dockerfile.secure` | Enhanced security hardening (read-only root, etc.) |
| `docker-compose.yml` | Build from source (Option 2) |
| `README.md` | This file |

---

## 🔒 Security Comparison

| Feature | Standard Dockerfile | Secure Dockerfile |
|---------|-------------------|-------------------|
| Base image pinning | Tag only (`python:3.11-slim`) | **Digest-pinned** (prevents supply chain) |
| Read-only root | ❌ No | ✅ Yes (except /app/data) |
| Security scanning | ❌ No | ✅ Yes (CI/CD integrated) |
| Runtime dependencies | wget, gnupg | wget, ca-certificates (minimal) |
| Cleanup | Basic | **Aggressive** (apt cache, tmp files) |
| Python hardening | ❌ No | ✅ Yes (random hash seed, etc.) |

**Recommendation:** Use `Dockerfile.secure` for production deployments.

---

## 🏗️ Building Images

### Standard Build

```bash
# From project root
docker build -f docker/Dockerfile -t radio-monitor:latest .
```

### Secure Build

```bash
# From project root
docker build -f docker/Dockerfile.secure -t radio-monitor:secure .
```

### Multi-Architecture Build

```bash
# Build for AMD64 and ARM64
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/Dockerfile \
  -t radio-monitor:latest \
  --push \
  .
```

---

## 🧪 Testing Images

### Test Standard Image

```bash
docker run --rm -p 5000:5000 -v $(pwd)/data:/app/data radio-monitor:latest
```

### Test Secure Image

```bash
docker run --rm -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --read-only \
  --tmpfs /tmp \
  radio-monitor:secure
```

---

## 📊 Image Sizes

| Image Type | Compressed Size | Uncompressed Size |
|-----------|-----------------|-------------------|
| Standard | ~45 MB | ~130 MB |
| Secure | ~43 MB | ~125 MB |

---

## 🔄 CI/CD Pipeline

The `.github/workflows/docker-image.yml` workflow:

✅ **Triggers on:**
- Push to `main` branch
- New tags (`v*.*.*`)
- Manual workflow dispatch

✅ **Builds:**
- Multi-architecture images (amd64, arm64)
- Uses layer caching for faster builds
- Runs security tests

✅ **Pushes to:**
- GitHub Container Registry (GHCR)
- Tags: `latest`, `v1.1.0`, `v1.1`, etc.

---

## 🛠️ Development Workflow

### Build and Test Locally

```bash
# Build image
docker-compose build

# Run container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop container
docker-compose down
```

### Build Changes

```bash
# After modifying code
docker-compose build --no-cache
docker-compose up -d
```

---

## 📝 Deployment Scenarios

### Scenario 1: Home User (Simple)

**Use:** `docker-compose.release.yml` (pre-built)

```bash
curl -O https://raw.githubusercontent.com/allurjj/radio-monitor/main/docker-compose.release.yml
docker-compose -f docker-compose.release.yml up -d
```

### Scenario 2: Developer (Custom Code)

**Use:** `docker/docker-compose.yml` (build from source)

```bash
git clone https://github.com/allurjj/radio-monitor.git
cd radio-monitor/docker
docker-compose up -d
```

### Scenario 3: Production (Secure)

**Use:** `Dockerfile.secure` + Nginx reverse proxy

```bash
# Build secure image
docker build -f docker/Dockerfile.secure -t radio-monitor:secure .

# Run with read-only root
docker run -d \
  --name radio-monitor \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  --read-only \
  --tmpfs /tmp \
  --security-opt no-new-privileges \
  radio-monitor:secure
```

---

## 🐛 Troubleshooting

### Build Fails

```bash
# Clean build
docker-compose build --no-cache

# Check Dockerfile syntax
docker build -f docker/Dockerfile --no-cache --progress=plain .
```

### Container Won't Start

```bash
# Check logs
docker-compose logs -f

# Check image was built
docker images | grep radio-monitor
```

### Permission Issues

```bash
# Fix data directory permissions
sudo chown -R 1000:1000 ./data
```

---

## 📚 More Information

- **User Deployment Guide:** [../DOCKER_DEPLOYMENT.md](../DOCKER_DEPLOYMENT.md)
- **Quick Start:** [../DOCKER_QUICKSTART.md](../DOCKER_QUICKSTART.md)
- **Main README:** [../README.md](../README.md)
- **Project Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md)

---

**Last Updated:** 2026-02-20
**Docker Image:** ghcr.io/allurjj/radio-monitor:latest
