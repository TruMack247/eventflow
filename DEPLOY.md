# Cloud Deployment Guide: Sharing EventFlow With Your Partner

This guide explains how to deploy EventFlow to the cloud so both you and your fiancée can view and edit the exact same wedding plan concurrently 24/7 on any device (phone, laptop, tablet).

---

## Architecture Overview

```
[ Your Phone / Laptop ]  \
                           ---> [ Cloud Container ] ---> [ Persistent SQLite DB (/data) ]
[ Partner's Phone/Laptop] /
```
- **Single Source of Truth**: All edits (marking tasks done, shifting dates, creating events) are committed to a single persistent SQLite database in the cloud.
- **Shared Access**: Real-time sync ensures that when one partner updates a task, the other partner sees the update immediately.

---

## Option 1: Deploy to Render.com (Recommended — 3 Minutes)

Render provides automatic container builds, free SSL (`https://...`), and persistent disks.

### Steps:
1. **Push Repo to GitHub**:
   - Push this repository to your GitHub account (public or private).
2. **Open Render**:
   - Go to [render.com](https://render.com) and sign in.
3. **New Blueprint or Web Service**:
   - Click **New +** $\to$ **Blueprint** (or **Web Service**).
   - Select your GitHub repository.
   - Render will detect `render.yaml` automatically, provisioning:
     - Web service with Docker runtime.
     - Persistent 1GB disk mounted at `/data`.
     - Environment variables: `DATABASE_PATH=/data/event_planner.db`.
4. **Set Shared Passcode (Optional)**:
   - In Render Dashboard under **Environment**, set `APP_PASSCODE=ourwedding2027` (or leave empty for open shared access).
5. **Start Planning**:
   - Render gives you a live link like `https://eventflow-wedding-planner.onrender.com`.
   - Send the link to your fiancée!

---

## Option 2: Deploy to Fly.io (Alternative)

Fly.io is great for running lightweight Docker containers with mounted volumes:

```bash
# 1. Install Fly CLI & authenticate
fly auth login

# 2. Launch container configuration
fly launch --no-deploy

# 3. Create persistent disk volume for SQLite
fly volumes create eventflow_data --size 1

# 4. Attach volume in fly.toml:
# [mounts]
#   source = "eventflow_data"
#   destination = "/data"

# 5. Deploy
fly deploy
```

---

## Option 3: Local Network Sharing (Immediate Testing at Home)

If both of you are on the same home Wi-Fi and you want to test together right now:
1. Start the server:
   ```bash
   python src/event_planner/web/server.py
   ```
2. Find your laptop's local IP address (e.g. `192.168.1.45`).
3. Have your fiancée open `http://192.168.1.45:8080` in Safari/Chrome on her phone.
