# SafeSense AI — Safety, in sight.

A local industrial safety monitoring application built with FastAPI, SQLite, OpenCV and Ultralytics. This release adds the violet glass interface, login, an adaptive camera wall, camera connection validation, a polygon editor, reports, incident history, and three configured pretrained detectors.

## Start

Python **3.11 or newer** is required. Unzip the entire application into a writable folder.

- **Windows:** double-click `Start-SafeSense.bat`.
- **Linux / macOS:** run `python3 run.py` from the extracted folder.

The launcher creates `.venv`, installs CPU dependencies on its first run, copies `.env.example` to `.env` if needed, and opens **http://127.0.0.1:8000**. Internet is needed for the first dependency installation. The downloadable release includes the three model files. When running from a Git checkout, missing weights are downloaded and checked against `models/catalog.json` automatically.

Sign in with **admin / admin**. Change `SAFESENSE_ADMIN_NAME` and `SAFESENSE_ADMIN_PASSWORD` in `.env` to change the credentials, then restart. Sessions expire after eight hours by default; signing out invalidates the session on the server. Restarting also invalidates sessions.

Stop with Ctrl+C in the terminal. If the port is busy, run `python run.py --port 8002`. `--no-browser` suppresses opening a browser. Use one server process: multiple workers would open the same camera repeatedly.

### Manual setup

```sh
python3 -m venv .venv
.venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-ai.txt
.venv/bin/python scripts/setup_models.py
.venv/bin/python run.py --inside
```

On Windows use `py -3 -m venv .venv`, then `.venv\Scripts\python.exe` in place of `.venv/bin/python`.

## Exhibition walkthrough

1. Sign in. Choose **Try the exhibition** on the empty camera wall, or **System & models → Load exhibition cameras**. Six cameras and sample safety zones are created in the real SQLite database.
2. The scenes are generated still images with changing timestamps and simulated moving detection tracks. Labels on each feed and every incident identify simulated evidence. These scenarios exercise the actual tracking, zone rules, alerts, database, reports and incident lifecycle. Their detections are independent of real inference.
3. Move the pointer to the far left: the toolbar expands. It also works with keyboard focus or the menu button.
4. Select a camera to open the enlarged live frame and report. The report shows name, location, timestamp, detected classes, people, assessment state, recent findings and existing zones.
5. Select **Edit zones**. Enter a name and choose danger (red boundary) or restricted (purple boundary). Select warning/critical severity and optional required PPE. Click the image to place vertices; click the first point or **Finish polygon** to finish. Drag vertices to reshape, drag inside to move, or click an edge to insert a vertex. Select a point and press Delete to remove it, keeping at least three points. Confirm saves the zone. Repeat to create multiple zones.
6. Select an existing zone in the report to edit it. Cancel or close the camera with × to discard the current draft. Previously confirmed zones remain saved. The backend independently rejects crossed, degenerate or out-of-frame polygons.
7. **Delete cameras** enters removal mode. Each camera gets an × button. The custom confirmation supports Yes/No. Yes removes the camera and its zones from SQLite; historical incidents are retained with deleted references cleared. Use **Cancel** or click Delete cameras again to leave removal mode.
8. Review **Incident history**. Filter by camera, severity or status; acknowledge and resolve findings. Camera outlines indicate the highest active finding. Findings remain active until resolved, even if the person has moved away.
9. Toggle the sun/moon control for light/dark mode. The preference survives reload. **Focus mode** maximizes the camera wall; Escape returns to the standard view. **Sign out** returns to login.

All camera tiles fit in the viewport. One camera fills the wall, three use one wide top tile and two bottom tiles, and other counts use balanced rows chosen for the available screen shape. The wall has no scrolling. More cameras mean smaller tiles; up to 64 registrations are accepted, but practical inference capacity depends on your computer.

## Real cameras

Choose **Add camera**, enter its name and location, then select a source:

- **USB:** device number `0`, `1`, etc. Close other software using the device and grant Python camera permission in your OS settings.
- **Network URL:** an RTSP/RTSPS/HTTP/HTTPS video stream OpenCV can decode. The application computer must be on the camera's network.
- **Exhibition demo:** use `synthetic` for a simulated scene, or `offline` to test loss of coverage.

An enabled real camera must return an actual frame before it is saved. Invalid devices, unreachable streams, missing environment variables and duplicate sources produce form errors. You can register a disabled source without probing it. Re-enabling or changing a source checks the connection again. After a device disconnects, its worker retries with backoff; the tile displays unavailable rather than a safety assessment.

For URLs containing passwords or tokens, put the value in `.env`:

```dotenv
MY_CAMERA_URL=rtsp://operator:YOUR_PASSWORD@192.168.1.20:554/stream
```

Enter `env:MY_CAMERA_URL` in the camera form and restart after changing `.env`. Direct URLs with embedded usernames/passwords are rejected. Environment references and redacted direct URLs are returned to the browser; credential-bearing URLs should never be pasted into the UI. When editing a saved redacted URL, leave `[configured URL]` unchanged to keep it.

Camera registrations, zones, and incident history persist in `data/safesense.db`. No video recording is performed. Back up the database while the application is stopped. Keep `.env` private.

## Models and actual capabilities

Three pretrained `.pt` files are included in the downloadable application. Source checkouts keep weights out of Git; `python scripts/setup_models.py` downloads all three, verifies SHA-256 and runs a CPU inference check before updating `.env`. `--people-only` installs just the official person detector. Ordinary operation does not download models.

| Detector | Weight file | Purpose / source |
| --- | --- | --- |
| YOLO26 nano | `models/yolo26n.pt` | People/common objects; [official Ultralytics weights](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt) |
| Fine-tuned YOLO11 nano | `models/ppe-yolo11n.pt` | Helmet, vest, gloves, boots and other labels; [PPE model source](https://github.com/harshflodata/ppe-detection/tree/main/models/finetuned) |
| Fine-tuned YOLOv8 small | `models/fire-yolov8s.pt` | Fire and smoke; [fire/smoke model source](https://github.com/Yug-doshi/Fire-and-Smoke-Detection-main/tree/main/runs/detect/train/weights) |

Exact URLs, provenance and hashes are in `models/catalog.json`. The model files remain subject to their respective authors' terms; Ultralytics is AGPL-3.0 or commercially licensed. This application does not claim the third-party models' published accuracy as measured on your cameras.

You can replace any path in `.env` with your own trusted Ultralytics detection weights:

```dotenv
SAFESENSE_MODEL_PATH=models/yolo26n.pt
SAFESENSE_PPE_MODEL_PATH=models/ppe-yolo11n.pt
SAFESENSE_FIRE_MODEL_PATH=models/fire-yolov8s.pt
SAFESENSE_CONFIDENCE=0.45
SAFESENSE_DEVICE=cpu
SAFESENSE_INFERENCE_FPS=3
SAFESENSE_MIN_OBSERVATIONS=3
SAFESENSE_CLASS_MAP={}
```

Class mapping uses actual model metadata, with common positive label aliases (`hardhat` → `helmet`, `safety vest` → `vest`). Negative labels such as `no_helmet` are never mapped to positive PPE. PPE boxes are associated with a single compatible person using position/body region; low-resolution or cropped people yield insufficient evidence, and unsupported classes never produce absence alerts. Missing PPE means *not detected persistently*, not proof of absence.

Danger and restricted boundaries use a tracked person's bottom-center point. Distinct `danger_entry` and `restricted_entry` categories are generated after the configured number of consecutive observations. PPE requirements apply only inside their zone. Fire and smoke findings require repeated detections and generate critical alerts. Combined conditions produce separate findings so the report explains each condition. Restricted entry colors the tile purple, warnings yellow, and other critical findings red. An unavailable camera always displays unavailable.

**Gas detection and human injury detection are not implemented.** Ordinary RGB footage cannot reliably identify invisible gases; calibrated sensor hardware/integration is required. Injury/fall assessment needs a separately validated temporal/pose system. No simulated result is presented as a real gas or injury detection.

The System & models screen shows the actual loaded classes, capabilities and failures. If weights are missing or cannot load, video remains available and the UI indicates the missing capability.

## Verification

```sh
python -m pytest -q
npm test
```

The Python suite checks authentication, connection-error handling, duplicate rejection, camera/zone CRUD, independent polygon validation, actual JPEG bytes, demo workers, tracking/PPE association, danger/restricted/hazard persistence, incident lifecycle, restart persistence, WebSocket events and origin protection. Node tests check normalized geometry.

`scripts/browser_smoke.py` exercises login, six simultaneous feeds and responsive controls, invalid USB rejection, polygon draw/save/move/type/cancel, X-to-discard, incident acknowledgement/resolution, persistent themes, camera deletion Yes/No, 3-camera layout, viewport fitting at desktop/tablet/mobile sizes, focus and logout. Run only against a **disposable database**: it removes demo cameras. It refuses to remove real cameras.

Example with a separate server:

```sh
SAFESENSE_DATABASE=/absolute/path/to/test.db python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8001
# In another terminal, after installing playwright:
SAFESENSE_TEST_URL=http://127.0.0.1:8001 CHROMIUM_PATH=/path/to/chromium python scripts/browser_smoke.py
```

The three pretrained models were loaded and executed on CPU. The integrated detector found people in the Ultralytics reference image. These checks establish software execution, not accuracy on your workplace or physical camera compatibility. USB/RTSP hardware must be checked on the computer used for the exhibition.

## Operational details

- Localhost binding, HTTP-only SameSite session cookies, constant-time credential comparison, login throttling, same-origin write/WebSocket checks and local Host restrictions.
- API docs at `/docs`; API calls and video require login. Health is public at `/api/health`.
- Camera wall: 4 snapshot updates/second avoids HTTP/1 connection exhaustion with six or more cameras. Enlarged view: continuous shared MJPEG. Capture defaults to 12 FPS, inference to 3 FPS; actual speed depends on hardware.
- One capture/inference worker per enabled camera; one shared model instance per detector with serialized inference. Latest frames replace old frames rather than growing a queue. Frame width is capped at 1280.
- Network open/read timeouts are 3 seconds. Some USB drivers cannot be interrupted promptly; camera probing/shutdown timing depends on the OS driver.
- Incident deduplication persists findings until acknowledged/resolved. Resolved findings can recur after the cooldown. Person IDs are temporary camera-local tracks, not identities.
- SQLite foreign keys and WAL are enabled. Initial tables are created automatically; there is no destructive schema migration in this release.
- This is local operator decision support. Real-world detections can be wrong or missed; review them before acting. Remote/public deployment requires additional hosting and network configuration. The app does not implement a hosted camera gateway.

## Files

`frontend/` contains the interface and geometry editor. `app/` contains REST/auth/video, database, models, tracking and safety rules. `scripts/setup_models.py` handles explicit downloads; `models/catalog.json` records provenance. `run.py` and the platform launchers handle first-run setup. Generated exhibition imagery is in `frontend/assets/facility.png`.
