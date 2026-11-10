# SafeSense AI — Safety, in sight.

A local industrial safety monitoring application built with FastAPI, SQLite, OpenCV and Ultralytics. The default workspace is a viewport-fitted camera dashboard with black controls with white icons, an auto-hiding navigation rail, camera connection validation, a polygon editor, incident history, and three configured pretrained detectors. The old dashboard header has been removed; the compact menu at the left opens navigation.

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

1. Sign in and choose **Try video exhibition**, or **Video exhibition** in navigation. Three openly licensed recordings are bundled: workshop worker, pedestrian walkway, and individual entrance. They loop at their native playback speed and run through the same real inference, tracking, PPE association, polygon rules and incident pipeline as a USB/network camera. Labels distinguish **PLAYBACK / RECORDED · REAL AI** from live cameras. If models are unavailable, the app explicitly says so.
2. The workshop recording includes a worker wearing a helmet and vest. The other recordings show people without industrial PPE, so a PPE checkpoint can demonstrate missing-item alerts. These are actual model results; there are no scripted detections on the recordings. Models can make mistakes. Empty sections of a recording correctly show no person.
3. The video exhibition replaces old synthetic still-image exhibition cameras when you load it. USB/network cameras remain registered. Existing exhibition samples are reused, so loading again does not duplicate them. Removing old demo cameras retains historical incidents with cleared deleted references.
4. Select a feed to enlarge it. **Findings** shows persisted incidents; **Zones** shows saved polygons. **Edit zones** creates a polygon directly over the moving video. Click vertices, finish the polygon, drag vertices or the whole boundary, select severity and required helmet/vest/gloves/boots, then confirm. You can have multiple polygons per recording or live camera. Cancel or × discards the draft.
5. Danger/restricted boundaries are red, PPE checkpoints yellow, and custom boundaries white. All boundaries are thicker. Critical findings have an **8 px red frame and a solid red banner**; warnings have an **8 px yellow frame and a solid yellow banner**. The enlarged view also shows a prominent banner. Alert text identifies missing items. Historical findings remain active until resolved.
6. The live PPE panel distinguishes checking, required PPE detected, missing items, and items that cannot be verified. Missing helmet and missing vest accumulate separate consecutive-observation counts. Seeing one item does not suppress a missing other item. Low-resolution/hidden body regions remain unverified; cropped legs no longer disable a visible head/torso check. The visible torso or footpoint must be inside the PPE zone. Danger/restricted entry uses the footpoint.
7. **Interface sounds** controls click, whoosh, pop, delete and confirmation sounds. **Alert sounds** controls distinct warning and danger signals. Critical alerts use three pulses; open alerts repeat every 10 seconds. Multiple camera events are combined to avoid alarm overlap. Acknowledge/resolve an incident to stop its repeating sound. Preferences survive reload. Browsers require a click or key gesture before audio can play; after automatic session restoration, interact once to enable audio.
8. Use **Incident history** to filter, acknowledge and resolve findings. **Delete cameras** enters removal mode; confirm a camera to remove it and its zones. Navigation also contains theme controls, sign-out and **Media credits**. All camera tiles fit the viewport.

Footage: [Intel IoT DevKit sample-videos](https://github.com/intel-iot-devkit/sample-videos), CC BY 4.0. Sounds: [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds), CC0 1.0; WAV conversion by Calinou. Original asset names, source links and SHA-256 hashes are recorded in `frontend/assets/media-catalog.json`; license texts are bundled beside the assets. No source endorsement is implied.

All camera tiles fit in the viewport. One camera fills the wall, three use one wide top tile and two bottom tiles, and other counts use balanced rows chosen for the available screen shape. The wall has no scrolling. More cameras mean smaller tiles; up to 64 registrations are accepted, but practical inference capacity depends on your computer.

## Real cameras

Choose **Add camera**, enter its name and location, then select a source:

- **USB:** device number `0`, `1`, etc. Close other software using the device and grant Python camera permission in your OS settings.
- **Network URL:** an RTSP/RTSPS/HTTP/HTTPS video stream OpenCV can decode. The application computer must be on the camera's network.
- **Recorded footage:** choose a bundled workshop, walkway or entrance sample. Playback and inference are local, so videos work without an internet connection after installation. Legacy `demo` sources remain accepted by the API for regression tests; new exhibition feeds use `video` sources.

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

Class mapping uses actual model metadata, with common positive label aliases (`hardhat` → `helmet`, `safety vest` → `vest`). Negative labels such as `no_helmet` are never mapped to positive PPE. People from the PPE detector supplement any people missed by the general detector; overlapping person boxes are merged. PPE boxes are associated with a single compatible person using position/body region; low-resolution or cropped people yield insufficient evidence, and unsupported classes never produce absence alerts. Missing PPE means *not detected persistently*, not proof of absence.

Danger and restricted boundaries use a tracked person's bottom-center point. PPE zones also accept the visible torso center for webcam views with cropped legs. Distinct `danger_entry` and `restricted_entry` categories are generated after the configured number of consecutive observations. PPE requirements apply only inside their zone. Fire and smoke findings require repeated detections and generate critical alerts. Combined conditions produce separate findings so the report explains each condition. Critical findings, including restricted entry, color the tile red; warnings color it yellow. An unavailable camera always displays unavailable.

**Gas detection and human injury detection are not implemented.** Ordinary RGB footage cannot reliably identify invisible gases; calibrated sensor hardware/integration is required. Injury/fall assessment needs a separately validated temporal/pose system. No simulated result is presented as a real gas or injury detection.

The camera panel shows detected classes and any capture/inference error. The model status API at `/api/model/status` exposes loaded classes, capabilities and failures. If weights are missing or cannot load, video remains available.

## Verification

```sh
python -m pytest -q
npm test
```

The Python suite additionally checks per-item webcam visibility, missing one/all items, alternating evidence, leaving a PPE zone, recording playback/looping, local-path rejection, and specialist person fallback. The Python suite checks authentication, connection-error handling, duplicate rejection, camera/zone CRUD, independent polygon validation, actual JPEG bytes, demo workers, tracking/PPE association, danger/restricted/hazard persistence, incident lifecycle, restart persistence, WebSocket events and origin protection. Node tests check normalized geometry.

`scripts/browser_smoke.py` exercises login, three simultaneous real-video feeds and responsive controls, invalid USB rejection, polygon draw/save/move/type/cancel, X-to-discard, incident acknowledgement/resolution, persistent themes, camera deletion Yes/No, 3-camera layout, viewport fitting for the wall, camera, zone editor, camera form and incident history at desktop/tablet/mobile sizes; two-stage navigation, shared overlay visibility and logout. Run only against a **disposable database**: it removes demo cameras. It refuses to remove USB/network cameras. `scripts/audio_smoke.py` checks actual WAV decoding/playback, gesture unlock, warning/critical alarm behavior, acknowledgement, throttling and mute; physical speaker output still depends on the operator’s device.

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

`frontend/` contains the interface and geometry editor. `app/` contains REST/auth/video, database, models, tracking and safety rules. `scripts/setup_models.py` handles explicit downloads; `models/catalog.json` records provenance. `run.py` and the platform launchers handle first-run setup. Openly licensed exhibition videos and sounds are in `frontend/assets/videos/` and `frontend/assets/sounds/`. `frontend/assets/facility.png` is retained only for legacy synthetic regression scenarios.
