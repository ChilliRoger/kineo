# Kineo

Real-time return-support agent with FastAPI backend, Firestore integration, WebSocket session handling, and Gemini-powered response flow.

## Prerequisites

1. Python 3.11+ (project has been used with newer Python versions on Windows).
2. A virtual environment in `.venv`.
3. Firestore credentials file at `service-account.json`.
4. Environment variables set in `.env`.

Required `.env` values:

- `GEMINI_API_KEY`
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `FIRESTORE_COLLECTION_CUSTOMERS`
- `FIRESTORE_COLLECTION_SESSIONS`
- `GOOGLE_APPLICATION_CREDENTIALS=./service-account.json`
- `PORT=8000`

## Setup

Run from `E:\kineo`:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run The Test Server

Start the app:

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

When running, you can access:

- App UI: `http://localhost:8000/`
- Health: `http://localhost:8000/health`
- WebSocket: `ws://localhost:8000/session`

## Validate Server Is Up

In a second terminal:

```powershell
.\.venv\Scripts\Activate.ps1
curl http://localhost:8000/health
```

Expected result: HTTP `200` and JSON with `"status":"ok"`.

## Run Tests

Keep the server running in one terminal, then use a second terminal for tests.

### 1) Backend feature tests

```powershell
.\.venv\Scripts\Activate.ps1
python test_new_features.py
```

This covers order endpoints, webhook behavior, and language-support flow checks.

### 2) Gemini generation check (optional)

```powershell
.\.venv\Scripts\Activate.ps1
python test_gemini_generate.py
```

If Gemini quota is exhausted, you may see API-limit errors. The app can still run in demo/fallback mode.

## Useful API Checks

With server running:

```powershell
curl http://localhost:8000/customers
curl http://localhost:8000/orders/customer/cust_sarah_001
```

Test webhook:

```powershell
$body = @{
	event_type = 'replacement.shipped'
	order_id = 'ORD-2024-001'
	tracking_number = '1Z999NEW123456'
	notes = 'Replacement shipped'
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/webhook/order-update" -Method POST -Body $body -ContentType "application/json"
```

## Stop Test Servers

Preferred method (if running in foreground):

- Press `Ctrl+C` in the server terminal.

If needed, force stop by port on Windows:

```powershell
$pid = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
Stop-Process -Id $pid -Force
```

Verify shutdown:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

No output means the server is stopped.

## Troubleshooting

- `Address already in use`: stop the existing process on port `8000`.
- Firestore errors: confirm `service-account.json` path and project permissions.
- Gemini `429 RESOURCE_EXHAUSTED`: wait for quota reset or use another API key.
- Import issues: run commands from the project root `E:\kineo`.