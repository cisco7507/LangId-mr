# Windows Language-ID API (English vs French)

Production-ready FastAPI microservice that detects whether a WAV clip is **English** or **French**.
Backed by [faster-whisper] running locally on CPU (works on Windows). Includes:
- REST API (submit job, check status, retrieve result)
- Lightweight durable job queue on SQLite (no Redis/RabbitMQ needed for Windows)
- Background worker with retries
- Structured logging
- Health endpoint
- Simple Windows service run instructions (NSSM)

## Quick Start (Windows)

1) **Install Python 3.10–3.12** (64-bit). Ensure `python` and `pip` are on PATH.
2) In PowerShell (Run as Administrator if installing system-wide):
```powershell
cd .\langid_service
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
3) **Run the API** (first run downloads the Whisper model):
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Open http://localhost:8080/docs for interactive docs.

### Submit a job
```bash
curl -F "file=@path\to\audio.wav" http://localhost:8080/jobs
```
Response:
```json
{"job_id":"<uuid>","status":"queued"}
```

### Check status
```bash
curl http://localhost:8080/jobs/<uuid>
```

### Get result
```bash
curl http://localhost:8080/jobs/<uuid>/result
```

## Windows Service (Optional)

Use [NSSM](https://nssm.cc/) to run as a service:

- **Path:** `C:\full\path\to\langid_service\.venv\Scripts\uvicorn.exe`
- **Arguments:** `app.main:app --host 0.0.0.0 --port 8080`
- **Startup directory:** `C:\full\path\to\langid_service`

Ensure the service account has write access to `storage\` and `logs\`.

## Notes

- The detector uses `faster-whisper` **small** model by default. You can switch models in `app/services/detector.py`.
- CPU-only works fine for language ID; GPU is optional.
- Only English vs French are reported; other languages are mapped to `unknown`.

## API Summary

- `POST /jobs` — upload a `.wav` file (or remote URL), enqueues a job
- `GET /jobs/{job_id}` — get status (`queued`, `running`, `succeeded`, `failed`), progress, timestamps
- `GET /jobs/{job_id}/result` — get detection result (language, probability, optional transcript snippet)
- `GET /healthz` — health check
- `GET /metrics` — minimal metrics JSON

Enjoy!


## Run as Windows Service (NSSM)

1. Install NSSM and ensure `nssm.exe` is in PATH.
2. From PowerShell (as Admin):

```powershell
cd .\langid_service\scripts\windows
.
ssm_install.ps1 -ServiceName LangIdAPI -Port 8080 -PythonVenv "$PWD\..\..\.venv" -AppDir "$PWD\..\.."
```

To remove:

```powershell
.
ssm_uninstall.ps1 -ServiceName LangIdAPI
```

## CI (GitHub Actions)

A ready-to-use workflow is included at `.github/workflows/ci.yml`. It runs pytest on **windows-latest** with the detector mocked (no model download). Set `USE_MOCK_DETECTOR=0` to run the real model in your own runners.

## Testing locally

```powershell
# In repo root:
cd .\langid_service
pytest
```

