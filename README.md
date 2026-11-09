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
Chrome opens maximized (with the normal title bar) for larger screenshots. Each gallery image is displayed
at viewport size and saved as WebP, in addition to a listing screenshot.
Press Ctrl+C to stop.

To collect multiple search terms with separate entry targets, pass matching lists:

```powershell
.\.venv\Scripts\python.exe .\run_scraper.py --search cat dog --entries 50 40
```

This targets 50 successful entries for `cat`, then 40 for `dog`, using one browser
session and one CSV. Each row includes its search term. Quote multiword terms,
for example `--search "cat food" "dog food" --entries 50 40`.
`--entries` is an alias for `--limit`. A single count applies to every term;
otherwise the number of counts must match the number of terms. The default is
10 entries per term. If results run out or `--max-pages` is reached, collection
continues with the next term and the command exits with status 1 for the shortfall.
Access or verification blocks still stop the run.

## Options

| Option | Default | Use |
| --- | --- | --- |
| `--search` | Required | One or more search terms |
| `--market` | `vn` | Shopee region code (vn, id, ph, etc.) |
| `--limit`, `--entries` | `10` | Successful products per term; one shared count or matching counts |
| `--max-pages` | `10` | Maximum search pages per term |
| `--output` | Automatic | CSV path; must not already exist |
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
- Listing folders: `results/screenshots/<searchterm>/<date>/<searchterm>_<date>_<listing_index>/`
- WebP screenshots inside each listing folder: `<searchterm>_<date>_<listing_index>_<image_index>.webp`
- Extraction errors: `failures.json` in the screenshots folder.

Multi-term runs use `shopee_batch_<date>.csv`. Screenshots keep the default
folder structure for each term: `results/screenshots/<searchterm>/<date>/`.

The date includes time to separate runs. Missing CSV values stay blank.
Gallery image indices start at `1`; image index `0` is the listing screenshot.
If Shopee blocks access, the scraper stops. Check the terminal and screenshots.
If Chrome opens empty or cannot connect, close the leftover scraper Chrome
window before retrying.
