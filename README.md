# Sheet Automation — nightly NSE top-250 filler

Automates columns A:C of the **`Top 250 Stocks`** tab in your scanner sheet.
Files here:

- `update_sheet.py` — downloads NSE Bhavcopy, writes top-250 by turnover
- `requirements.txt` — Python deps
- `.github/workflows/update-sheet.yml` — runs it every weekday ~20:15 IST

---

## One-time setup (≈15 min)

### 1. Make the sheet a *native* Google Sheet
`gspread` can only write to a Google Sheet, not an uploaded `.xlsx`.
- Upload `NSE-Volume-Breakout-Scanner.xlsx` to Google Drive → **Open with → Google Sheets**
- **File → Save as Google Sheets**
- Copy its **ID** from the URL: `.../spreadsheets/d/<THIS_IS_THE_ID>/edit`
- Paste it into `update_sheet.py` → `SPREADSHEET_ID = "..."`

### 2. Create a Google Cloud service account (the "robot")
- Go to https://console.cloud.google.com/apis/library
- Enable **Google Sheets API** and **Google Drive API**
- **Credentials → + Create Credentials → Service Account** (e.g. `stock-updater-bot`) → Create
- Open the account → **Keys → Add Key → Create new key → JSON** → download it
- Copy the account's email (`...iam.gserviceaccount.com`)

### 3. Share the sheet with the robot
- In your Google Sheet → **Share** → paste the service-account email → give it **Editor** → Send

### 4. Put the code on GitHub
- Create a **private** GitHub repo (e.g. `NSE-Auto-Sheet`)
- Push the contents of this `sheet-automation/` folder to the repo **root** (so the workflow lands at
  `.github/workflows/update-sheet.yml` and `update_sheet.py` is at the top level)

### 5. Add the credentials secret
- Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `GCP_CREDENTIALS`
- Value: paste the **entire** contents of the downloaded JSON key file → Save

### 6. Test it
- Repo → **Actions** tab → *Update NSE Scanner Sheet* → **Run workflow** (manual trigger)
- Watch the log for `SUCCESS: wrote 250 rows ...`
- Your sheet's A2:C251 should fill, and K2 shows the data date / update time

After that it runs automatically every weekday evening. The in-sheet formulas
(CMP, DMAs, CAR, Final List) recompute on their own.

---

## Common gotchas (the blog says ~50% of failures are these)

- **Wrong / missing Sheet ID** or accidentally deleting the quotes around it in `update_sheet.py`.
- **Forgot to share** the sheet with the service-account email → `PermissionError`.
- **Tab renamed** — the script looks for a tab named exactly `Top 250 Stocks`.
- **APIs not enabled** — both Sheets API *and* Drive API must be enabled.
- GitHub cron can be delayed by several minutes at peak times — normal, not an error.

## Want volume *and* turnover (2 tabs)?
Add a second tab named exactly `Top 250 Turnover`, then extend `fetch_bhavcopy` to also
sort by `TtlTradgVol` and write that list to the second worksheet (the blog's "2-in-1" code).
Ask and I'll generate that version.
