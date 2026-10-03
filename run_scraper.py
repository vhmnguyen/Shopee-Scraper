"""Collect Shopee search results into CSV using SeleniumBase CDP."""
import argparse
import base64
import csv
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

from bs4 import BeautifulSoup
from app.scraping.csv_output import FIELDS, extract_csv_row
from app.scraping.handlers.search_handler import SearchHandler
from app.scraping.prices import read_price

ROOT = Path(__file__).resolve().parent
MARKETS = {
    'vn': ('shopee.vn', 'VND'), 'id': ('shopee.co.id', 'IDR'),
    'ph': ('shopee.ph', 'PHP'), 'sg': ('shopee.sg', 'SGD'),
    'my': ('shopee.com.my', 'MYR'), 'th': ('shopee.co.th', 'THB'),
    'tw': ('shopee.tw', 'TWD'), 'br': ('shopee.com.br', 'BRL'),
}


class AccessBlocked(RuntimeError):
    pass


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('Must be greater than zero')
    return number


def nonnegative(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError('Must be finite and nonnegative')
    return number


def check_access(sb, allow_pending=False):
    text = sb.cdp.get_text('body').casefold()
    path = urlparse(sb.cdp.get_current_url()).path.casefold()
    blocked = ('page unavailable', 'trang không khả dụng', "verification can't be completed",
               'verification cannot be completed')
    pending = 'please verify your identity' in text or any(part in path for part in ('/verify', '/captcha'))
    if any(message in text for message in blocked) or pending and not allow_pending:
        raise AccessBlocked('Shopee returned an access or verification screen; stopping without retrying.')
    return not pending and '/buyer/login' not in path and not sb.cdp.is_element_visible('input[type="password"]')


def login(sb, timeout, domain):
    sb.activate_cdp_mode(f'https://{domain}/buyer/login')
    print('Complete login and verification in Chrome. Collection will start automatically.', flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sb.sleep(3)
        if check_access(sb, allow_pending=True) and sb.cdp.is_element_visible('input.shopee-searchbar-input__input'):
            return
    raise RuntimeError('Login timed out. Complete login before starting another run.')


def product_links(html, base_url, domain):
    links = {}
    for anchor in BeautifulSoup(html, 'html.parser').select('a[href]'):
        href = urljoin(base_url, anchor['href'])
        parsed = urlparse(href)
        if parsed.scheme != 'https' or parsed.hostname != domain:
            continue
        match = re.search(r'-i\.(\d+)\.(\d+)(?:/|$)', parsed.path)
        match = match or re.fullmatch(r'/product/(\d+)/(\d+)/?', parsed.path)
        if match:
            key = (match[1], match[2])
            links.setdefault(key, href)
    return links


def page_url(search_url, page):
    parts = urlparse(search_url)
    query = dict(parse_qsl(parts.query))
    query['page'] = str(page)
    return urlunparse(parts._replace(query=urlencode(query)))


def collect_page(sb, seen, domain):
    links = {}
    for _ in range(8):
        if not check_access(sb):
            raise AccessBlocked('Shopee returned to login during collection; stopping.')
        links.update(product_links(sb.cdp.get_page_source(), sb.cdp.get_current_url(), domain))
        sb.cdp.evaluate('window.scrollBy(0, window.innerHeight)')
        sb.sleep(2)
    return [(key, url) for key, url in links.items() if key not in seen]


def save_diagnostic(sb, directory, name):
    try:
        import mycdp
        # SeleniumBase's save_screenshot defaults to PNG regardless of suffix.
        # Request WebP directly from Chrome instead of just renaming PNG bytes.
        data = sb.cdp.loop.run_until_complete(sb.cdp.page.send(
            mycdp.page.capture_screenshot(format_='webp', quality=90,
                                         capture_beyond_viewport=False)))
        prefix = f'{directory.parent.name}_{directory.name}'
        (directory / f'{prefix}_{name}.webp').write_bytes(base64.b64decode(data))
    except Exception as error:
        print(f'Could not save diagnostics: {error}', file=sys.stderr)


def collect(sb, args, handle, diagnostics):
    domain, currency = MARKETS[args.market]
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    handle.flush()
    count = 0
    seen = set()
    failures = []
    try:
        try:
            SearchHandler(args.search).search(sb)
        except RuntimeError as error:
            if 'Failed to retrieve total pages' not in str(error):
                raise
            print('Page count unavailable; using --max-pages.', flush=True)
        if not check_access(sb):
            raise AccessBlocked('Search returned to login; stopping.')
        search_url = sb.cdp.get_current_url()
        if urlparse(search_url).path != '/search' or urlparse(search_url).hostname != domain:
            raise RuntimeError('Search did not reach a search results page.')
        for page in range(args.max_pages):
            print(f'Collecting search page {page + 1}...', flush=True)
            if page:
                sb.cdp.get(page_url(search_url, page))
                sb.sleep(5)
            listings = collect_page(sb, seen, domain)
            if not listings:
                print('No new product links found; collection finished.', flush=True)
                break
            for key, url in listings:
                seen.add(key)
                number = len(seen)
                try:
                    print(f'Opening product {number}; saved {count}/{args.limit}...', flush=True)
                    sb.cdp.get(url)
                    sb.sleep(5)
                    if not check_access(sb):
                        raise AccessBlocked('Product returned to login; stopping.')
                    # Load lower product specifications and description.
                    for _ in range(3):
                        sb.cdp.evaluate('window.scrollBy(0, window.innerHeight)')
                        sb.sleep(2)
                        if not check_access(sb):
                            raise AccessBlocked('Product returned to login; stopping.')
                    sb.cdp.evaluate('window.scrollTo(0, 0)')
                    row = extract_csv_row(sb.cdp.get_page_source(), url, read_price(sb, currency))
                    writer.writerow(row)
                    handle.flush()
                    count += 1
                    save_diagnostic(sb, diagnostics, f'{number:04d}')
                    print(f'[{count}/{args.limit}] {row["product_name"]}', flush=True)
                    if count == args.limit:
                        return count
                except AccessBlocked:
                    save_diagnostic(sb, diagnostics, f'{number:04d}')
                    raise
                except Exception as error:
                    failures.append({'url': url, 'error': str(error)})
                    save_diagnostic(sb, diagnostics, f'{number:04d}')
                    print(f'Product failed: {error}', file=sys.stderr)
                sb.sleep(args.pause)
        return count
    finally:
        if failures:
            (diagnostics / 'failures.json').write_text(json.dumps(failures, indent=2), encoding='utf-8')
        print(f'Saved {count}/{args.limit} products.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search', required=True)
    parser.add_argument('--market', choices=MARKETS, default='vn', help='Shopee region (default: vn)')
    parser.add_argument('--limit', type=positive_int, default=10)
    parser.add_argument('--max-pages', type=positive_int, default=10)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--pause', type=nonnegative, default=10, help='Seconds between products')
    parser.add_argument('--login-timeout', type=positive_int, default=300)
    parser.add_argument('--profile-dir', type=Path, help='Override the region-specific Chrome profile')
    args = parser.parse_args()
    domain, _ = MARKETS[args.market]
    if args.profile_dir is None:
        args.profile_dir = (ROOT / 'trial_browser_profile' if args.market == 'vn'
                            else ROOT / 'browser_profiles' / args.market)
    if not args.search.strip():
        parser.error('--search must not be blank')
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
    term = re.sub(r'[^\w-]+', '_', args.search).strip('_') or 'search'
    output = args.output or ROOT / 'results' / f'shopee_{term}_{stamp}.csv'
    output.parent.mkdir(parents=True, exist_ok=True)
    diagnostics = ROOT / 'results' / 'screenshots' / term / stamp
    diagnostics.mkdir(parents=True, exist_ok=True)
    from seleniumbase import SB
    # Exclusive creation fails before browser startup if the destination exists.
    with output.open('x', encoding='utf-8-sig', newline='') as handle:
        try:
            with SB(uc=True, headed=True, user_data_dir=str(args.profile_dir.resolve())) as sb:
                try:
                    login(sb, args.login_timeout, domain)
                    count = collect(sb, args, handle, diagnostics)
                except Exception:
                    save_diagnostic(sb, diagnostics, '0000')
                    raise
            return 0 if count == args.limit else 1
        finally:
            print(f'CSV: {output.resolve()}\nDiagnostics: {diagnostics}', flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('Interrupted. CSV rows already saved are preserved.', file=sys.stderr)
        sys.exit(130)
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
