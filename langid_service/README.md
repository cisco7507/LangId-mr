# **LangID Service — EN/FR Gated Language Detection with VAD Retry**
*FastAPI • Whisper • Background Workers • EN/FR Gate • VAD Retry • Windows Server Ready*

---

## **Overview**

**LangID-Service** is a production-ready microservice that performs **English vs French language detection** on audio files using:

- **FastAPI**
- **Faster-Whisper**
- **Custom EN/FR gating logic**
- **VAD-based retries**
- **Fallback scoring**
- **Background worker threads**
- **Storage + DB job tracking**
- **Windows Server–friendly deployment**
- **Dashboard UI**

This system is highly robust for:

- Streaming workflows (Telestream Vantage, etc.)
- Clear or noisy audio
- Silence handling
- Long/short clips
- Incorrect Whisper autodetections (e.g., Spanish, Portuguese, etc.)

---

# **📦 Architecture**

## **System Overview**

```mermaid
flowchart TD

Client[Client: cURL / Vantage / Dashboard] --> API[FastAPI Server]

API -->|Submit job (/jobs)| DB[(SQLite DB)]
API -->|Store file| Storage[(storage/ Directory)]

Worker[Background Worker Threads] --> DB
Worker --> Storage
Worker --> Whisper[Whisper Model]

Whisper --> Gate[EN/FR Gate + VAD Retry]
Gate --> Worker
Worker --> DB

Dashboard --> API

subgraph Host
    API
    Worker
    DB
    Storage
end
```

---

# **🎧 Audio Processing Pipeline**

```mermaid
flowchart LR
    A[Receive Audio (Upload or URL)] --> B[Save to storage/]
    B --> C[Create Job in DB]
    C --> D[Worker Pulls Job]

    D --> E[Probe Audio Segment]

    E --> F1[Whisper Autodetect]
    F1 -->|lang in {en,fr} AND p >= threshold| G[Accept autodetect]

    F1 -->|lang NOT in {en,fr}| H[Reject → VAD Retry]
    F1 -->|p < threshold| H[Reject → VAD Retry]

    H --> F2[Whisper Autodetect (VAD-cut audio)]
    F2 -->|good| G

    F2 -->|still not EN/FR| I[Fallback Scoring]
    I --> J[Pick EN vs FR]

    G & J --> K[Transcription Snippet Extraction]
    K --> L[Store Result in DB]
    L --> M[API Returns Result]
```

---

# **📂 Repository Structure**

```
langid_service/
├── app/
│   ├── main.py
│   ├── worker/
│   ├── services/
│   ├── lang_gate.py
│   ├── models/
│   ├── maintenance/
│   ├── utils.py
│   ├── metrics.py
│   └── ...
├── dashboard/
├── .env.example
├── requirements.txt
└── run_server.py
```

---

# **⚙️ Components**

## **FastAPI Application (`app/main.py`)**

Handles:

- job submission (upload + URL)
- job querying
- result retrieval
- worker thread startup

---

## **Worker (`app/worker/runner.py`)**

Each worker:

- pulls jobs
- loads Whisper model (cached)
- runs EN/FR detection pipeline
- stores results in SQLite

---

## **Detector (`services/detector.py`)**

Responsible for:

- Faster-Whisper inference
- transcript extraction
- autodetected language
- VAD support
- metadata reporting

---

## **EN/FR Gate (`lang_gate.py`)**

Core logic:

1. Whisper autodetects language + probability  
2. Reject if:
   - not EN/FR  
   - below probability threshold (`LANG_DETECT_MIN_PROB`)
3. Retry with VAD-processed audio  
4. If still not EN/FR:
   - run fallback scoring (EN vs FR)
5. Return final EN/FR decision

---

## **Storage (`storage/`)**

Holds uploaded or downloaded audio files.

---

## **SQLite DB**

Tracks job states:

- queued
- processing
- done
- failed

File:  
```
langid.sqlite
```

---

# **🧪 API Endpoints**

## **Submit File**

```bash
curl -F "file=@audio.wav" http://localhost:8080/jobs
```

---

## **Submit URL**

```bash
curl -X POST http://localhost:8080/jobs/by-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/audio.mp3"}'
```

---

## **Check Job**

```bash
curl http://localhost:8080/jobs/<id>
```

---

## **Get Result**

```bash
curl http://localhost:8080/jobs/<id>/result
```

---

# **🗄 Environment Variables (.env.example)**

| Variable | Description |
|----------|-------------|
| `WHISPER_MODEL_SIZE` | tiny/base/small/medium/large-v3 |
| `WHISPER_DEVICE` | cpu / cuda |
| `WHISPER_COMPUTE` | float32 / float16 / int8 |
| `MAX_UPLOAD_BYTES` | upload limit |
| `MAX_WORKERS` | number of worker threads |
| `DB_URL` | SQLite or external DSN |
| `STORAGE_DIR` | audio storage directory |
| `LANG_DETECT_MIN_PROB` | min autodetection probability |
| `ENFR_STRICT_REJECT` | restrict only EN/FR if true |

---

# **💠 Windows Server Installation**

This project is fully optimized for **Windows Server 2016/2019/2022**.

---

## **1. Install Python 3.12**

Download from:  
https://www.python.org/downloads/windows/

Enable during install:

- Add to PATH  
- Install pip  
- Disable path length limit  

---

## **2. Create virtual environment**

```powershell
cd C:\LangId
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## **3. Install FFmpeg**

```powershell
choco install ffmpeg -y
```

Or install manually and add to PATH.

---

## **4. Install NSSM**

Place `nssm.exe` in:

```
C:\Tools\nssm\nssm.exe
```

Add to PATH:

```powershell
setx PATH "$env:PATH;C:\Tools\nssm" -m
```

---

## **5. Install LangID API as a Windows service**

```powershell
nssm install LangIdAPI "C:\LangId\.venv\Scripts\python.exe" "C:\LangId\run_server.py"
nssm set LangIdAPI AppDirectory "C:\LangId"
nssm start LangIdAPI
```

---

# **♻️ Scheduled Maintenance Tasks (Windows Task Scheduler)**

The project includes:

- DB purge script  
- Storage purge capability  

---

## **1. Purge Storage Script** (`purge-storage.ps1`)

```powershell
$storage = "C:\LangId\storage"
Get-ChildItem $storage -Recurse | Remove-Item -Force -Recurse
```

---

## **2. Purge Database**

```powershell
python C:\LangId\langid_service\app\maintenance\purge_db.py
```

---

## **3. Register Daily Cleanup Task**

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "C:\LangId\purge-storage.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 3am
Register-ScheduledTask -TaskName "PurgeLangIDStorage" -Action $action -Trigger $trigger -RunLevel Highest
```

---

# **🧹 Manual Cleanup**

## **Purge Storage Directory**

```bash
rm -rf storage/*
```

## **Purge Database**

```bash
python langid_service/app/maintenance/purge_db.py
```

---

# **📊 Metrics**

Located in:

```
app/metrics.py
```

Exposes:

- job counters  
- average worker latency  
- VAD retries  
- fallback gate activations  

---

# **🌐 Dashboard**

Located in:

```
dashboard/
```

Build:

```bash
npm install
npm run build
```

---

# **🔧 Development**

## **Start API with Hot Reload**

```bash
python -m uvicorn langid_service.app.main:app --reload --host 0.0.0.0 --port 8080
```

---

# **🐛 Troubleshooting**

### **Whisper returns wrong language**
Check:

- audio length
- noise
- foreign language → fallback will override

### **Empty transcript**
Likely:

- VAD removed entire signal  
- Silence in audio  
- Corrupt MP3  

### **Workers not running**
Check:

```bash
python -m uvicorn langid_service.app.main:app
```

Look for logs related to:

- FFmpeg missing  
- Missing Python modules  
- Permission issues  

---

# **🚀 Conclusion**

This README provides:

- complete architecture  
- full processing pipeline  
- EN/FR gating logic + VAD retry  
- Windows Server deployment  
- service installation  
- scheduled maintenance  
- API documentation  
- developer workflows  
- troubleshooting  

Your LangID service is now fully documented and production-ready.

