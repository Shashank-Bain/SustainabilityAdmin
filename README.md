# CoE Portal (Minimal Flask Skeleton)

## Setup

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Initialize and apply database migrations:

   ```powershell
   flask --app run.py db init
   flask --app run.py db migrate -m "Initial migration"
   flask --app run.py db upgrade
   ```

4. Run the app:

   ```powershell
   python run.py
   ```

The app uses SQLite by default (`sqlite:///app.db`). Configure `DATABASE_URL` and `SECRET_KEY` via environment variables (or `.env`) as needed.

## Wave 2: Billing logic

- `billed_per_day` is selected from DAILY `BillingRate` tiers by exact FTE match first.
- If no exact match exists, interpolation is applied between the nearest lower/upper FTE tiers.
- If only the `4.5` tier exists, billing is prorated as `amount_4_5 * (charged_fte / 4.5)`.
- For case types `IP (Z5LB/J2RC)`, `Other CD/IP Codes`, and `Investment`, fallback billing uses `1080/day @ 4.5 FTE`, scaled by `charged_fte/4.5` and then by `hours/8`.
