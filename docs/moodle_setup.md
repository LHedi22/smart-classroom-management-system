# Moodle Setup Guide

## 1. Start Docker Moodle

```bash
docker compose up -d moodle
```

Wait ~2 minutes for Moodle to finish initialising (watch with `docker compose logs -f moodle`).
Open http://localhost:8080 — default credentials: admin / admin123

---

## 2. Enable Web Services

1. **Site administration → Advanced features**
2. Check **Enable web services** ✓ → Save changes
3. **Site administration → Plugins → Web services → Overview**
4. Follow the guided setup:
   - Enable web services (already done)
   - Enable protocols → enable **REST** ✓
   - Create a specific user (or use admin)
   - Select a service → choose **Moodle mobile web service** (or create a custom one)
   - Add required capabilities to the user

---

## 3. Generate a Token

1. **Site administration → Plugins → Web services → Manage tokens**
2. Click **Add**
3. Select user: **admin** (or your dedicated service account)
4. Select service: **Moodle mobile web service**
5. Click **Save changes**
6. Copy the generated token

---

## 4. Add Token to Environment

Edit your `.env` file (copy from `.env.example` if not done yet):

```env
MOODLE_URL=http://localhost:8080
MOODLE_TOKEN=your_token_here
```

Then restart the backend:

```bash
# If running directly
uvicorn app.main:app --reload --port 8000

# If running in Docker
docker compose restart backend
```

---

## 5. Verify Connection

```bash
curl http://localhost:8000/api/moodle-test
```

Expected response when connected:
```json
{"connected": true, "moodle_url": "http://localhost:8080"}
```

If `connected: false`, check:
- `MOODLE_TOKEN` in `.env` is correct and not expired
- Moodle container is running: `docker compose ps`
- Web services are enabled in Moodle admin
- REST protocol is enabled

---

## 6. Install Attendance Plugin (Required for sync)

The `mod_attendance_add_attendance` web service function requires the
[Moodle Attendance Plugin](https://moodle.org/plugins/mod_attendance).

For the Docker Moodle instance (development/testing only):
```bash
# Enter the Moodle container
docker compose exec moodle bash

# Download and install the plugin
cd /bitnami/moodle/mod
curl -L https://moodle.org/plugins/download.php/... -o attendance.zip
unzip attendance.zip
# Then visit Site admin → Notifications to run the plugin install
```

Alternatively, for testing without the plugin, the sync endpoint gracefully
handles failures and queues the session for retry.

---

## 7. Sync Attendance Manually

After a session ends (auto-sync fires in background), you can also trigger
manual sync:

```bash
# Replace SESSION_ID with the actual session UUID
curl -X POST http://localhost:8000/api/sessions/SESSION_ID/sync-moodle
```

Expected response:
```json
{"session_id": "...", "synced": 5, "failed": 0}
```

---

## 8. Retry Queue

Failed syncs are pushed to the Redis key `moodle:retry_queue`.
The alert engine automatically retries every 10 minutes.

To inspect the queue manually:
```bash
docker compose exec redis redis-cli lrange moodle:retry_queue 0 -1
```

To force an immediate retry, restart the backend (the scheduler fires on start).
