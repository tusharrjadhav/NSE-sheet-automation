# NSE Volume/Turnover Breakout Scanner — Setup & Formula Reference

Companion to **`NSE-Volume-Breakout-Scanner.xlsx`**.
Strategy source: Mahesh Kaushik — https://www.maheshkaushik.com/2026/05/blog-post.html
(Class-2 video: https://youtu.be/tyeG16q9214)

---

## What this scanner does

1. A nightly **GitHub Action** downloads the NSE Bhavcopy (EOD file) and writes the
   **top 250 stocks by turnover** (or volume) into the `Top 250 Stocks` tab (columns A–C).
2. Google Sheets formulas (columns D–J) compute **CMP, 50/100/200 DMA, a bull-run flag,
   % distance from the 200 DMA, and the CAR rating**.
3. The `Final List` tab runs one master `QUERY` that surfaces only stocks that are in a
   **Bull Run** *and* have **CAR = "Buy/Average Out"**, sorted by turnover.

**CAR (Cumulative Average Rule):** finds the 52-week high, takes closes from that high to
today, builds the running cumulative average, and checks whether the last 10 cumulative
averages are strictly rising (9/9 up ⇒ "Buy/Average Out").

---

## How to use the template

1. Upload `NSE-Volume-Breakout-Scanner.xlsx` to Google Drive → right-click → **Open with →
   Google Sheets** (this activates all GOOGLEFINANCE/QUERY/LET formulas).
2. File → **Save as Google Sheets** (keep the two tab names exactly: `Top 250 Stocks`,
   `Final List`).
3. 5 sample tickers are pre-filled in A2:A6 so you can confirm formulas work immediately.
4. Wire up the nightly automation (Google Cloud service account + GitHub Action) per the
   blog's Steps 2–5 so columns A–C refill automatically every evening.
5. **If the import mangled the CAR (J) or master (A3) formula**, re-paste them from the
   sections below — Google's xlsx importer occasionally breaks array literals (`{0;0;...}`).

> ⚠️ Performance note: each CAR cell makes several historical `GOOGLEFINANCE` calls, so 250
> live CAR formulas is heavy and can hit Google's data limits / show `Loading...` for a
> while. Consider filling CAR only for the rows you care about, or reducing the universe.

---

## Formulas — `Top 250 Stocks` tab

Headers (Row 1): `A NSE Code | B Volume/Turnover | C Close Price | D CMP | E 50 DMA |
F 100 DMA | G 200 DMA | H Bull Run | I Diff from 200 DMA | J CAR | K Status`

Paste into **row 2**, then drag/fill down to **row 251** (250 stocks):

**D2 — CMP (live price):**
```
=IFERROR(GOOGLEFINANCE("NSE:"&$A2,"price"),"")
```

**E2 — 50 DMA:**
```
=IFERROR(AVERAGE(QUERY(GOOGLEFINANCE("NSE:"&$A2,"close",TODAY()-100,TODAY()),"select Col2 order by Col1 desc limit 50 label Col2 ''",0)),"")
```

**F2 — 100 DMA:**
```
=IFERROR(AVERAGE(QUERY(GOOGLEFINANCE("NSE:"&$A2,"close",TODAY()-200,TODAY()),"select Col2 order by Col1 desc limit 100 label Col2 ''",0)),"")
```

**G2 — 200 DMA:**
```
=IFERROR(AVERAGE(QUERY(GOOGLEFINANCE("NSE:"&$A2,"close",TODAY()-400,TODAY()),"select Col2 order by Col1 desc limit 200 label Col2 ''",0)),"")
```

**H2 — Bull Run (price > 50DMA > 100DMA > 200DMA):**
```
=IF(AND(N(D2)>0,D2>E2,E2>F2,F2>G2),"Bull Run","No")
```

**I2 — Difference from 200 DMA (format as %):**
```
=IFERROR((D2-G2)/G2,"")
```

**J2 — CAR rating (verbatim from the blog):**
```
=IFERROR(IF(A2="","ENTER STOCK",
  LET(
    raw_high, GOOGLEFINANCE("NSE:" & A2, "high", TODAY()-365, TODAY()),
    high_date, IFERROR(TO_DATE(QUERY(raw_high, "SELECT Col1 WHERE Col2 IS NOT NULL ORDER BY Col2 DESC LIMIT 1 LABEL Col1 ''", 1)), TODAY()-30),
    raw_data, IFERROR(GOOGLEFINANCE("NSE:" & A2, "close", high_date, TODAY()), GOOGLEFINANCE("NSE:" & A2, "close", TODAY()-10, TODAY())),
    prices, IFERROR(CHOOSEROWS(INDEX(raw_data, 0, 2), SEQUENCE(ROWS(raw_data)-1, 1, 2, 1)), {0}),
    count_rows, ROWS(prices),
    cum_avg, SCAN(0, SEQUENCE(count_rows), LAMBDA(a,n, AVERAGE(CHOOSEROWS(prices, SEQUENCE(n))))),
    last_10, IF(count_rows < 10, {0;0;0;0;0;0;0;0;0;0}, CHOOSEROWS(cum_avg, SEQUENCE(10, 1, count_rows - 9, 1))),
    check, SUMPRODUCT(--(CHOOSEROWS(last_10, SEQUENCE(9, 1, 2, 1)) > CHOOSEROWS(last_10, SEQUENCE(9, 1, 1, 1)))),
    IF(count_rows < 10, "Short History", IF(check = 9, "Buy/Average Out", "Avoid/Hold"))
  )
), "TICKER NOT FOUND")
```

---

## Formula — `Final List` tab

Row 1: merged heading `Stocks In Bull Run`.
Row 2 headers: `A NSE Code | B Volume | C Previous Close | D CMP | E Difference from 200 DMA | F CAR`

**A3 — master filter (paste once, it spills the whole list):**
```
=IFERROR(QUERY('Top 250 Stocks'!$A$2:$J$251,"select A, B, C, D, I, J where H = 'Bull Run' and J = 'Buy/Average Out' order by B desc label A '', B '', C '', D '', I '', J ''",0),"No stocks match yet")
```

---

## Notes / caveats

- **DMA formulas are reconstructions.** The blog showed D2–I2 and the master A3 as images
  (they didn't render as text), so these are faithful, working GoogleFinance equivalents of
  what's described (they may differ slightly from Mahesh Kaushik's exact cell formulas). The
  **CAR (J2)** formula is verbatim from the blog.
- **GOOGLEFINANCE has delayed/limited data** and no F&O — this is an EOD swing-screening aid,
  not an intraday or execution tool. Treat its output as a *research shortlist* only.
- This fits the vault's safety chain as a **research** input: any name it surfaces still goes
  through strategy notes → backtest → paper → approval before any live order.
