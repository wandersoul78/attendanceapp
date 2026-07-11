# Company Attendance App

A simple daily punch-in / punch-out attendance app for a small team, built with
Streamlit and backed by a Google Sheet. Deployable for free on Streamlit
Community Cloud and accessible from any phone browser.

## How it works

- Employees are listed in the **Employees** tab of your Google Sheet.
- Each punch (check-in or check-out) is read from / written to the
  **Attendance** tab — one row per employee per day.
- The dashboard reads the sheet on every page load, so it's always current.

---

## 1. Create the Google Sheet

1. Create a new Google Sheet (e.g. "attendance2627").
2. Create two tabs, named exactly (lowercase):

   **employees**
   | Employee |
   |----------|
   | Rahul    |
   | Amit     |
   | Deepak   |
   | Vijay    |
   | Rakesh   |

   **attendance** (just the header row — the app fills in the rest)
   | Employee | Date | IN | OUT |
   |----------|------|----|-----|

   Each row is one employee's record for one day. `Date` holds just the date
   (e.g. `11-Jul-2026`) — handy for date-range formulas in another sheet.
   `IN` / `OUT` hold the full date+time (e.g. `11-Jul-2026 02:30:23 PM`),
   written automatically by the app. There's no separate Status column —
   status is worked out from whether IN/OUT are filled.

   ⚠️ If you have test rows from an earlier version of this app, clear them
   out — older layouts aren't compatible with this one.

3. Copy the spreadsheet ID from the URL — the long string between `/d/` and
   `/edit`:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART_IS_THE_ID`**`/edit`
   (This is different from the sheet's display name, e.g. "attendance2627" —
   the ID is the long random string in the URL, and that's what goes in
   `secrets.toml`, not the display name.)

## 2. Create a Google service account (so the app can read/write the sheet)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Enable two APIs: **Google Sheets API** and **Google Drive API**.
4. Go to **IAM & Admin → Service Accounts → Create Service Account**.
5. Give it any name, click through, no roles needed.
6. Open the new service account → **Keys → Add Key → Create new key → JSON**.
   This downloads a `.json` credentials file — keep it private.
7. Copy the `client_email` value from that JSON file. Open your Google Sheet,
   click **Share**, and share it with that email address as an **Editor**.

   ⚠️ If you're reusing a service account from another project, sharing is
   **per-sheet**, not global — you still need to explicitly share this new
   sheet (e.g. "attendance2627") with that same service account email, even
   if it already has access to other sheets.

## 3. Configure secrets locally

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Fill in the values from the JSON key file you downloaded (they map
   directly: `project_id`, `private_key`, `client_email`, etc).
3. Set `spreadsheet_id` under `[sheet]` to the ID you copied in step 1.
4. **Never commit `secrets.toml`** — it's already excluded via `.gitignore`.

## 4. Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

## 5. Push to GitHub

```bash
git init
git add .
git commit -m "Initial attendance app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

`secrets.toml` will **not** be pushed (it's git-ignored) — that's intentional.

## 6. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
2. Click **New app**, pick your repo, branch `main`, main file `app.py`.
3. Before (or after) deploying, open **Advanced settings → Secrets** and
   paste in the *contents* of your filled-in `secrets.toml` (same TOML
   format, real values).
4. Deploy. You'll get a public URL like
   `https://your-app-name.streamlit.app`.
5. Save that URL as a home-screen shortcut on each employee's phone — no
   installation needed.

## Folder structure

```
Attendance_App/
├── app.py                      # Main entry point (streamlit run app.py)
├── attendance.py                # Check-in / check-out logic & UI
├── dashboard.py                 # Today's summary + employee roster
├── sheets.py                    # All Google Sheets read/write calls
├── utils.py                     # Date/time helpers
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml.example     # Copy to secrets.toml and fill in
└── assets/                      # (optional) logo/images if you add any
```

## Notes

- The app writes one row per employee per day. On check-in it appends a new
  row; on check-out it updates that same row (no duplicates).
- If someone's employee list changes, just edit the **Employees** tab — no
  code changes needed.
- If you outgrow 5 employees or want auth (so people can't punch in for each
  other), that's a reasonable next step — just ask.
