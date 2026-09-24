# MHARS

Underground mine robotic rover — hazard dashboard + hardware link.

## Folders

```
clg-major-project/
├── FORM-2 _B9.docx     ← patent / project doc
├── README.md           ← this file
├── CONNECT.md          ← how to wire hardware → software
├── backend/            ← Python server (hazard + nav + API)
├── dashboard/          ← remote monitoring UI
└── firmware/           ← ESP32 example sketch
```

## Run (no hardware)

**Terminal 1 — server**
```bash
cd backend
.\.venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — UI**
```bash
cd dashboard
npm run dev
```

Open **http://127.0.0.1:5173**

First time only:
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

cd ..\dashboard
npm install
```

## Connect hardware

See **[CONNECT.md](CONNECT.md)** — short guide for Wi‑Fi / USB / sensors.
