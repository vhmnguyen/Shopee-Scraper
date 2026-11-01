import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

FIELDS = ['URL', 'Title', 'Seller', 'Seller URL', 'Price', 'Condition',
          'Unit Weight (kg)', 'Number Sold', 'Stock Quanity', 'Minimum Purchase',
          'Category', 'Showcase', 'Product Description', 'Date Collected',
          'Search Term', 'Species (common name)', 'Scientific Name',
          'Live Animal (Y/N)', 'CITES Appendix', 'Confidence', 'Type', 'Screenshot']


def find_product(data):
    if isinstance(data, dict):
        kind = data.get('@type', [])
        if kind == 'Product' or isinstance(kind, list) and 'Product' in kind:
            return data
        for value in data.values():
            found = find_product(value)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_product(value)
            if found:
                return found
    return {}


def extract_csv_row(html, url, price=None, search_term=''):
    soup = BeautifulSoup(html, 'html.parser')
    product = {}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            product = find_product(json.loads(script.get_text()))
        except (ValueError, TypeError):
            continue
        if product:
            break
    row = dict.fromkeys(FIELDS, '')
    row['URL'] = url
    row['Search Term'] = search_term
    row['Date Collected'] = datetime.now(timezone.utc).isoformat()
    heading = soup.find('h1')
    row['Title'] = heading.get_text(' ', strip=True) if heading else product.get('name', '')
    offers = product.get('offers') or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    seller = offers.get('seller') or product.get('seller') or {}
    if isinstance(seller, dict):
        row['Seller'] = seller.get('name', '')
        row['Seller URL'] = urljoin(url, seller['url']) if seller.get('url') else ''
    if price:
        low, high, currency, display = price
    else:
        low = offers.get('lowPrice', offers.get('price', ''))
        high = offers.get('highPrice', low)
        currency = offers.get('priceCurrency', '')
    if low != '':
        row['Price'] = f'{low} {currency}' if low == high else f'{low} - {high} {currency}'
    condition = offers.get('itemCondition') or product.get('itemCondition') or ''
    row['Condition'] = condition.rsplit('/', 1)[-1]
    row['Product Description'] = product.get('description', '')
    labels = {'Condition': ['condition', 'tình trạng'],
              'Unit Weight (kg)': ['weight', 'trọng lượng', 'berat produk'],
              'Stock Quanity': ['stock', 'kho hàng', 'stok'],
              'Minimum Purchase': ['minimum purchase', 'min. pembelian', 'mua tối thiểu'],
              'Category': ['category', 'danh mục', 'kategori']}
    for section in soup.find_all('section'):
        title = section.find(['h2', 'h3'], recursive=False)
        if title and title.get_text(' ', strip=True).casefold() in ('product description', 'mô tả sản phẩm'):
            content = title.find_next_sibling()
            if content:
                row['Product Description'] = content.get_text('\n', strip=True)
    for label in soup.find_all('h3'):
        key = label.get_text(' ', strip=True).casefold()
        value = label.find_next_sibling()
        if not value:
            continue
        for field, names in labels.items():
            if key not in names:
                continue
            text = value.get_text(' ', strip=True)
            if field == 'Stock Quanity' and not re.fullmatch(r'[\d.,]+', text):
                continue  # IN STOCK is availability, not a quantity.
            if field == 'Category':
                text = ' > '.join(a.get_text(' ', strip=True) for a in value.find_all('a')
                                  if a.get_text(' ', strip=True).casefold() != 'shopee') or text
            row[field] = text
    for element in soup(['script', 'style', 'noscript']):
        element.decompose()
    text = soup.get_text(' ', strip=True)
    sold = re.search(r'([\d.,]+\s*(?:k|m|rb|ribu|jt)?\+?)\s*(?:sold|đã bán|terjual)\b', text, re.I)
    if sold:
        row['Number Sold'] = sold[1].strip()
    if not row['Title'] or not row['Price']:
        raise RuntimeError('Product name or price missing; CSV row was not saved.')
    return row


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path
