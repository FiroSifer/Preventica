# SafeSense AI

Local-first industrial camera monitoring and **operator decision support**, built with FastAPI, OpenCV, SQLite/SQLAlchemy, and a vanilla JavaScript dashboard. It is not a certified safety system and does not guarantee detection of unsafe conditions.

## Start on Windows (Python 3.11+)

From the repository root, in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

If your installed Python is newer, replace `py -3.11` with `py -3.12` (or your installed version). No PowerShell activation or execution-policy changes are required. Open `http://127.0.0.1:8000` on your own computer. API docs: `/docs`; health: `/api/health`. SQLite and its parent directory initialize automatically. Stop with Ctrl+C. Run a **single Uvicorn worker**, without reload during camera operation: multiple workers would open cameras repeatedly.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

No Node dependencies or frontend build step are required. Node 18+ is optional for frontend geometry tests. Internet is needed to install dependencies and manually obtain optional weights; ordinary operation is local.

## First demo / acceptance checklist

1. Start the server. Dashboard initially has zero cameras and explicitly reports no model.
2. **Add camera** → name `Demo workshop`, location of your choice, source type **Demo**, source `synthetic`. Live frames change over time and are labeled **SIMULATED VIDEO / DETECTIONS**. Demo detections are isolated to demo cameras; real feeds never receive simulated detections.
3. Click the camera. Select **Draw zone**, click four points around most of the frame, then **Finish polygon**. Name the zone, choose `restricted` or `danger`, severity `critical`, and optionally select `helmet`/`vest` in PPE requirements. Save.
4. A synthetic person moves horizontally. When its bottom-center enters the polygon for the configured number of inference observations, incidents appear through the real engine, database, API, and WebSocket. Required helmet/vest are intentionally not detected in this scenario. Findings always say **SIMULATED**. Gloves/boots are unsupported by the demo and cannot generate missing-PPE findings.
5. Review **Incidents**; filter severity, status, and camera. Acknowledge then resolve. Refresh/restart the application: cameras, zones, incident lifecycle, timestamps, and history persist. Current camera connection state is recomputed on restart.
6. Reopen the camera, edit a zone. Drag a vertex; click an edge to insert; select a vertex then press Delete to remove (minimum three retained). Alt-drag to move the whole polygon. Cancel discards all unsaved edits. Save persists them. Repeat with multiple independent zones; delete one and verify others remain.
7. Resize the browser: overlay coordinates follow the actual frame rectangle. Detail view takes the stream's real aspect ratio, with no letterboxing inside the editing surface. Dashboard tiles may letterbox video but do not accept editing coordinates.
8. Add another Demo camera with source `offline`. It must display a black unavailable tile with **monitoring unknown**, never “safe”. Disabling a camera also displays unavailable. Changing demo source back to `synthetic` reconnects it.
9. Toggle detection overlays, inspect current detections/PPE, edit source/name/location, disable/enable, and confirm removal. Camera deletion removes its zones but retains incidents with null deleted camera/zone references.
10. Test a real device separately using the steps below. Camera hardware and model accuracy cannot be established from demo validation.

## Real cameras and credentials

Add source type **USB**, source `0` (or `1` etc.). Windows must grant Python access to the camera; close software already using the device. USB indices 0–99 are supported.

For an IP camera select **Network** and use an RTSP/RTSPS/HTTP/HTTPS stream supported by OpenCV's FFmpeg build. Local files and arbitrary protocols are intentionally not accepted. The computer must have access to the camera's LAN. Prefer environment references for **all** secret-bearing URLs:

```dotenv
MY_CAMERA_URL=rtsp://operator:YOUR_PASSWORD@192.168.1.20:554/stream
```

Set the camera source to `env:MY_CAMERA_URL`. `.env` is loaded at startup; restart after editing it. API responses show only this reference, or `[configured URL]` for direct URLs. Direct URLs with embedded usernames/passwords are rejected; direct URLs (including query tokens) are saved in SQLite, so always use an environment reference for secrets. Blank source is invalid; leave `[configured URL]` unchanged in the UI to preserve a configured direct URL. Protect `.env` with OS file permissions. Do not share it or commit it. Capture failures expose generic errors, never URL exception strings. FFmpeg logging is suppressed to avoid leaking credentials. Credentials must be URL-encoded as necessary. Use trusted sources; a camera URL permits access from this machine to that network destination.

Each enabled camera has one capture thread and one inference thread, independent of viewers. Frames are capped at 1280 pixels wide; only the latest frame/JPEG is retained. Network reads/open use 3-second timeouts and reconnect backoff of 1–15 seconds. USB driver behavior is OS-dependent; a stuck native driver may not honor shutdown promptly. Capture failure affects that camera only. Disabled feeds have no capture worker. No recording is performed.

## Optional real AI model

The dashboard and real video work without AI. To enable real detections:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ai.txt
```

Obtain **trusted** compatible Ultralytics detection `.pt` weights separately, save under `models/`, and configure `.env`:

```dotenv
SAFESENSE_MODEL_PATH=models/your-ppe-model.pt
SAFESENSE_CONFIDENCE=0.45
SAFESENSE_IMAGE_SIZE=640
SAFESENSE_DEVICE=cpu
SAFESENSE_CAPTURE_FPS=12
SAFESENSE_INFERENCE_FPS=3
SAFESENSE_MIN_OBSERVATIONS=3
SAFESENSE_COOLDOWN_SECONDS=30
SAFESENSE_CLASS_MAP={"hardhat":"helmet","safety vest":"vest"}
```

Restart the server. Settings/model and `/api/model/status` report actual class metadata, mapped labels, supported PPE classes, and load errors. The app checks a local file exists before loading and never deliberately requests downloadable model names at startup. Missing weights or optional Ultralytics installation degrades to live video without inference. `.pt` loading may deserialize executable Python: load only trusted weights. Only local `.pt` detection models are supported by this MVP. The optional integration is not an accuracy certification; check licensing of Ultralytics and model weights for your use case.

A standard COCO model can detect `person` but does **not** imply PPE capability. Only actual metadata labels or explicit mappings enable `helmet`, `vest`, `gloves`, `boots` evaluation. Map positive PPE labels only: never map `no-helmet` to `helmet`. Unsupported classes produce `unsupported`, not absence alerts. Low confidence detections are filtered by the configured threshold. Very small or cropped people yield `insufficient_evidence`. `not_detected` means no sufficient detection evidence, **not proof that a person is missing equipment**.

Tracking uses greedy bounding-box IoU with a two-second expiry. IDs are temporary, per camera, and can change under occlusion or motion. No faces or identities are inferred. PPE centers must lie horizontally inside a person box and within a vertical body band (helmet -15–35%, vest 20–75%, gloves 25–90%, boots 70–110%). Each PPE box is assigned to at most one person, preferring the smaller compatible person box. Crowds and occlusion remain ambiguous; glove/boot presence does not establish both hands/feet are protected.

Rules use the tracked person's bottom-center point. Restricted/danger zones produce entry findings. Any enabled zone can specify PPE. Consecutive observations reset when evidence/zone presence disappears. With default 3 inference FPS and 3 observations, persistence is observation-based, not a guaranteed wall-clock duration. Open/acknowledged incidents de-duplicate by camera, zone, temporary track and category. Resolved incidents can recur after the cooldown if the finding persists; they are never removed automatically. Offline alerts are operational, separate from AI categories, and require operator resolution when coverage is restored. Camera display uses highest active severity, while an unavailable feed always remains visibly unavailable.

Future activity recognition has a disabled extension interface only. Fall, fight, and immobility detection are **not implemented**.

## Architecture

```text
app/config.py                 .env settings and repository-relative paths
app/database/{models,store}   SQLAlchemy entities, SQLite WAL and foreign keys
app/video/{sources,manager}   synthetic source, shared frames, capture/reconnect/inference workers
app/ai/{detector,tracking}    optional YOLO, metadata mapping, IoU tracking and PPE association
app/safety/                  geometry, rule persistence, incident de-duplication
app/events.py                bounded live-event queues; slow clients drop oldest events
app/main.py                  application factory, REST, MJPEG, WebSocket, frontend serving
frontend/                    HTML/CSS, API client, dashboard, polygon editor and geometry modules
tests/                       pytest integration/unit tests and Node geometry tests
models/                      optional local model weights (ignored)
data/                        runtime SQLite (ignored)
```

Pipeline: source → latest frame → inference worker → tracking → exclusive PPE association → normalized zone rules → incident persistence → REST/WebSocket → dashboard. Inference is serialized across cameras sharing one model; frames are dropped rather than queued. Live events use `{type, timestamp, data}`; the UI reconnects and polls authoritative API snapshots every 1.5 seconds to recover from dropped events. MJPEG viewers share capture but each viewer uses extra JPEG bandwidth. MJPEG is a local MVP transport, not an optimized multi-site surveillance solution. No claimed benchmark or large-camera capacity: profile your hardware and start with a few feeds. Slower inference changes persistence latency.

## APIs and storage

OpenAPI at `/docs` documents requests. Health, camera CRUD/status/stream, camera-scoped zone creation/listing, zone PUT/delete, incidents list/detail/acknowledge/resolve, system/model status, and `/ws/events` are implemented. Camera PATCH merges supplied fields and validates the result; zone PUT replaces the zone. Incidents can filter `status`, `severity`, `camera_id`, with `limit` up to 500 (the UI shows the newest 500). Lifecycle conflicts return 409, missing records 404, invalid inputs 422. Source errors do not expose tracebacks. No permissive CORS is enabled: frontend is served from the same origin. Cross-origin browser writes and WebSockets are rejected; HTTP Host is restricted to local names.

Schema version is the initial v1 SQLAlchemy schema. `create_all` initializes new databases; it does **not migrate existing schemas**. Before a future schema update, stop the application, back up `data/` securely, and supply/test a migration for that release before restarting. To reset a disposable demo database, stop the app and remove `data/safesense.db` plus associated `-wal`/`-shm` files; this destroys local history. Never do this to a database whose history you need. Move an existing database by setting `SAFESENSE_DATABASE` to an absolute path. SQLite data and backups may be sensitive even though video is not retained.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node tests/geometry.test.js
```

Linux equivalent: `.venv/bin/python -m pytest -q`. The Python suite uses temporary databases and exercises actual worker frames, persistence across application instances, API validation/CRUD, polygon geometry, confidence/capability-aware PPE states, rules, lifecycle/de-duplication, and WebSocket publication. Node tests exercise normalized coordinates and polygon/edge geometry. The manual checklist above covers deployment acceptance. Optional YOLO weights and real camera hardware require separate validation; demo tests do not validate detector accuracy.

## Troubleshooting and limitations

- **No image:** inspect camera detail error/status, enabled state, USB permissions, LAN connectivity and URL reference. Offline means coverage unknown, never safe. Camera warnings remain historical until resolved.
- **No AI:** inspect Settings/model, install optional AI dependencies, provide trusted local weights, verify metadata mapping. Inference errors appear in camera detail. Invalid weights never imply safe footage.
- **No incident:** check zone enabled/type, bottom-center position, PPE support, persistence count, cooldown, and existing open incident. Demo person must enter the polygon.
- **Geometry rejected:** use distinct points inside the image, at least three vertices, nonzero area and no intersecting edges. Finish before saving. The backend validates independently of the editor.
- **Device error:** CPU is the portable default. GPU use requires a compatible PyTorch/CUDA setup; it is not automatically provisioned.
- **Performance:** lower capture/inference FPS or input size, reduce camera/viewer count. Inference is bounded but CPU and MJPEG bandwidth are finite.
- **Future scaling:** authentication, TLS, audit actors, managed migrations, richer tracking and temporal evidence, access control, pagination, and a more efficient video transport are future work.

Bind to localhost as shown. Do not expose this MVP publicly: it has no user authentication or authorization. TrustedHost/origin checks are defense in depth, not authentication. Remote access requires a reviewed security design, authenticated TLS reverse proxy, explicit hosts/origins and network controls. Local users/processes can access the API. Do not retain video without a lawful privacy policy; follow applicable workplace monitoring laws. Predictions have false positives and false negatives and need trained human review.

### Optional Chromium smoke automation

`scripts/browser_smoke.py` reproduces the tested browser flow, including MJPEG byte validation and polygon vertex editing. Run it against a **fresh disposable database** (it creates demo records and expects camera ID 1). In a separate terminal start the server with `SAFESENSE_DATABASE` set to a new temporary database path, install `playwright` in a testing environment, set `CHROMIUM_PATH` to your Chromium executable (default `/usr/bin/chromium`), then run `python scripts/browser_smoke.py`. `SAFESENSE_TEST_URL` optionally overrides the local test URL. Do not run this destructive smoke scenario against operational records. The script saves a dashboard screenshot in the OS temporary directory. Playwright is optional test tooling, not a runtime requirement.
