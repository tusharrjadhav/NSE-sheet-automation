"""
NSE top-250 (by turnover) auto-filler for the Google Sheet scanner.

Runs in GitHub Actions every evening: downloads the NSE Bhavcopy (EOD UDiFF CSV),
keeps the top 250 EQ stocks by turnover (TtlTrfVal), and writes them into the
"Top 250 Stocks" tab (columns A:C). The in-sheet GOOGLEFINANCE/CAR formulas do the rest.

Requires GitHub secret GCP_CREDENTIALS = the full JSON of a Google Cloud service
account that has Editor access to the sheet (share the sheet with its ...iam.gserviceaccount.com email).
"""

import io
import json
import os
import zipfile
from datetime import datetime, timedelta

import gspread
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials

# ── EDIT THIS: your Google Sheet ID (from the sheet URL, between /d/ and /edit) ──
SPREADSHEET_ID = "1SPXytBVd6yX12RIsMnTW91nbm2PKG6E28frffYtjtMY"

WORKSHEET_NAME = "Top 250 Stocks"
TOP_N = 250


def _parse_credentials(raw: str) -> dict:
    """Parse the GCP_CREDENTIALS secret, tolerating common paste mistakes."""
    if not raw:
        raise SystemExit("CRITICAL: GCP_CREDENTIALS secret is missing or empty!")

    cleaned = raw.strip().lstrip("\ufeff")  # strip whitespace + BOM

    # Diagnostic that never leaks the secret (first char of the JSON is always '{').
    print(
        f"  GCP_CREDENTIALS: length={len(cleaned)}, "
        f"starts={cleaned[:1]!r}, ends={cleaned[-1:]!r}"
    )

    # 1) Plain JSON (the normal case).
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        first_err = e

    # 2) Someone wrapped it in single/double quotes.
    if len(cleaned) >= 2 and cleaned[0] in "'\"" and cleaned[-1] == cleaned[0]:
        try:
            return json.loads(cleaned[1:-1])
        except json.JSONDecodeError:
            pass

    # 3) Someone base64-encoded the JSON file.
    try:
        import base64

        decoded = base64.b64decode(cleaned).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        pass

    raise SystemExit(
        "CRITICAL: GCP_CREDENTIALS is not valid JSON "
        f"({first_err}). Re-create the secret by pasting the ENTIRE contents of the "
        "downloaded service-account .json key file — the value must start with '{' and "
        "end with '}', with no surrounding quotes, and not be pasted twice."
    )


def get_client() -> gspread.Client:
    creds_dict = _parse_credentials(os.environ.get("GCP_CREDENTIALS", ""))
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


def fetch_bhavcopy(date_obj: datetime):
    """Return [[symbol, turnover, close], ...] top-N by turnover, or None if no file."""
    date_str = date_obj.strftime("%Y%m%d")
    url = (
        "https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return None
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            with z.open(z.namelist()[0]) as f:
                df = pd.read_csv(f)
    except Exception as e:
        print(f"  fetch/parse error for {date_str}: {e}")
        return None

    df.columns = [c.strip() for c in df.columns]
    sym_col = next((c for c in ["TckrSymb", "SYMBOL"] if c in df.columns), None)
    close_col = next((c for c in ["ClsPric", "CLOSE"] if c in df.columns), None)
    series_col = next((c for c in ["SctySrs", "SERIES"] if c in df.columns), None)
    turnover_col = next(
        (c for c in ["TtlTrfVal", "TtlTrdVal", "TURNOVER_LACS", "TURNOVER"] if c in df.columns),
        None,
    )
    if not all([sym_col, close_col, turnover_col]):
        print("  expected columns not found:", list(df.columns)[:12])
        return None

    if series_col:
        df = df[df[series_col].astype(str).str.strip() == "EQ"]
    df = df[~df[sym_col].astype(str).str.contains("BEES|ETF|GOLD|LIQUID", case=False, na=False)]
    df[turnover_col] = pd.to_numeric(df[turnover_col], errors="coerce")
    df = df.dropna(subset=[turnover_col])
    df_top = df.sort_values(by=turnover_col, ascending=False).head(TOP_N)
    return df_top[[sym_col, turnover_col, close_col]].values.tolist()


def main() -> None:
    ws = get_client().open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

    data, fetched = None, ""
    for i in range(7):  # walk back up to 7 days to skip weekends/holidays
        d = datetime.now() - timedelta(days=i)
        if d.weekday() >= 5:  # Sat/Sun
            continue
        data = fetch_bhavcopy(d)
        if data:
            fetched = d.strftime("%d-%b-%Y")
            break

    if not data:
        raise SystemExit("FAILED: no Bhavcopy found in the last 7 days.")

    ws.batch_clear(["A2:C251"])
    ws.update("A2", data)
    ist = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d-%b %H:%M")
    ws.update("K2", [[f"Data Date: {fetched} | Last Update: {ist} (IST)"]])
    print(f"SUCCESS: wrote {len(data)} rows for {fetched}")


if __name__ == "__main__":
    main()
