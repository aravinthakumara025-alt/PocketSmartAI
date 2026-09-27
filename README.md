# PocketSmart AI

A responsive FastAPI application for budget planning across home interiors, parties, and jewelry. Accounts, planner inputs, and recommendations are stored in SQLite. Text recommendations use Groq when configured; deterministic local recommendations are available with `MOCK_AI=true` for development.

## Features
- Registration, sign in/out, password hashing, JWT in an HTTP-only cookie, and safe session endpoints.
- Three planners with server-side input validation, item search links, and Python-recalculated totals.
- Recommendation history and owner-checked detail/deletion routes.
- Optional validated JPG/PNG/WEBP outfit image upload (max 5 MB). Image analysis is not claimed: a vision provider must be configured before uploaded images can be analyzed.
- Responsive accessible layouts, loading feedback, mobile navigation, and image previews.

## Architecture
FastAPI routes live in `main.py`; SQLAlchemy models/database setup are in `models.py` and `database.py`; recommendation provider and planner logic are under `services/`; Jinja templates are in `templates/`; CSS/JS are in `static/`. SQLite is the default database. Passwords use salted scrypt hashes. JWT tokens are signed with `SECRET_KEY`; browser cookies are HTTP-only and SameSite=Lax.

## Setup
Requires Python 3.11+.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a strong random `SECRET_KEY`. Set `MOCK_AI=true` to run without an API key, or set `MOCK_AI=false` and supply `GROQ_API_KEY`. `GROQ_MODEL` selects the Groq model (default `openai/gpt-oss-120b`). Optional `DATABASE_URL` defaults to `sqlite:///./pocketsmart.db`; `ACCESS_TOKEN_EXPIRE_MINUTES`, `ALGORITHM`, and `MAX_UPLOAD_MB` tune auth and upload settings. Set `APP_ENV=production` to enforce a strong secret, configured Groq (unless mock mode is intentionally on), and secure cookies over HTTPS. Never commit `.env`.

```powershell
uvicorn main:app --reload
```

Open http://127.0.0.1:8000.

## AI, prices, and uploads
Mock mode provides transparent planning examples generated locally so the interface can be exercised. With mock mode off, planner prompts go through the Groq SDK and must return structured JSON. The server validates prices/quantities, trims items if their combined estimate exceeds the submitted budget, and calculates totals in Python. Estimates are not live prices. Search buttons link to provider search pages; there are no product API integrations. Uploads are size limited, image-decoded, extension/type checked, named randomly, and saved under `uploads/`. Image vision is intentionally not simulated; outfit notes state when provider support is missing.

## Tests

```powershell
python -m compileall .
pytest
```

Database tables and upload directory are created at application startup. For production, set `COOKIE_SECURE=true` behind HTTPS and use a managed database, strong secret, and configured Groq credentials.


