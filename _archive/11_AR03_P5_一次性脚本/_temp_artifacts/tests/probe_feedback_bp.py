"""Probe all feedback_bp endpoints against live server."""
import json
import urllib.request

BASE = "http://127.0.0.1:5000"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return r.status, r.read().decode("utf-8")


# 1. GET (full list)
s, b = get("/api/task-feedback")
print(f"GET  /api/task-feedback            -> {s}, body_len={len(b)}, rows={len(json.loads(b))}")

# 2. GET (filtered)
s, b = get("/api/task-feedback?task_id=2")
print(f"GET  /api/task-feedback?task_id=2  -> {s}, rows={len(json.loads(b))}")

# 3. POST (valid)
s, b = post("/api/task-feedback", {
    "task_id": 2,
    "event_type": "skip_task",
    "reason_category": "other",
    "reason_detail": "todo3 verify python probe",
})
print(f"POST /api/task-feedback (valid)    -> {s}, body={b[:200]}")

# 4. POST (invalid event_type)
s, b = post("/api/task-feedback", {
    "task_id": 2,
    "event_type": "garbage",
    "reason_category": "other",
})
print(f"POST /api/task-feedback (bad et)   -> {s}, body={b[:200]}")

# 5. POST /api/tasks/<id>/feedback (cross-domain write)
s, b = post("/api/tasks/2/feedback", {
    "energy_after": 7,
    "mood_after": "good",
})
print(f"POST /api/tasks/2/feedback          -> {s}, body={b[:200]}")

# 6. POST /api/tasks/<missing>/feedback (404)
s, b = post("/api/tasks/99999/feedback", {"energy_after": 5, "mood_after": "ok"})
print(f"POST /api/tasks/99999/feedback      -> {s}, body={b[:200]}")