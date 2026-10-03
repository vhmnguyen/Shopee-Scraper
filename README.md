# Shopee scraper

## Setup

Install Python 3.10+ and Google Chrome. Open PowerShell in this folder.
If `.venv` is already installed, skip setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe .\run_scraper.py --search coffee --market id --limit 10
```

Complete login and verification in the Chrome window if prompted. Collection
starts automatically, and Chrome closes when finished. Run one scraper at a time.
Press Ctrl+C to stop.

## Options

| Option | Default | Use |
| --- | --- | --- |
| `--search` | Required | Search term |
| `--market` | `vn` | Shopee region code (vn, id, ph, etc.) |
| `--limit` | `10` | Number of successful products to save |
| `--max-pages` | `10` | Maximum search pages |
| `--output` | Automatic | CSV path; must not already exist |
| `--pause` | `10` | Seconds between products |
| `--login-timeout` | `300` | Seconds allowed for login |
| `--profile-dir` | Per region | Override Chrome profile with saved login |

## Change region

Select a region with `--market`, for example:

```powershell
.\.venv\Scripts\python.exe .\run_scraper.py --market id --search kopi --limit 10
```

Codes: `vn` Vietnam, `id` Indonesia, `ph` Philippines, `sg` Singapore,
`my` Malaysia, `th` Thailand, `tw` Taiwan, `br` Brazil.
Log in on the first run for each region. Vietnam keeps `trial_browser_profile`;
others use `browser_profiles/<market>`. 

**NOTE:** Only Vietnam has been verified live.

## Find your results

- CSV: `results/shopee_<searchterm>_<date>.csv`
- WebP screenshots: `results/screenshots/<searchterm>/<date>/<searchterm>_<date>_<index>.webp`
- Extraction errors: `failures.json` in the screenshots folder.

The date includes time to separate runs. Missing CSV values stay blank.
If Shopee blocks access, the scraper stops. Check the terminal and screenshots.
If Chrome opens empty or cannot connect, close the leftover scraper Chrome
window before retrying.

