import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

FIELDS = ['url', 'product_name', 'seller', 'seller_url', 'price', 'condition',
          'unit_weight', 'sold_count', 'stock_quantity', 'minimum_purchase',
          'category', 'pack_type', 'consumables_form', 'volume', 'ingredient',
          'circulation_number', 'description', 'date_collected']


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


def extract_csv_row(html, url, price=None):
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
    row.update(url=url, date_collected=datetime.now(timezone.utc).isoformat())
    heading = soup.find('h1')
    row['product_name'] = heading.get_text(' ', strip=True) if heading else product.get('name', '')
    offers = product.get('offers') or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    seller = offers.get('seller') or product.get('seller') or {}
    if isinstance(seller, dict):
        row['seller'] = seller.get('name', '')
        row['seller_url'] = urljoin(url, seller['url']) if seller.get('url') else ''
    if price:
        low, high, currency, display = price
    else:
        low = offers.get('lowPrice', offers.get('price', ''))
        high = offers.get('highPrice', low)
        currency = offers.get('priceCurrency', '')
    if low != '':
        row['price'] = f'{low} {currency}' if low == high else f'{low} - {high} {currency}'
    condition = offers.get('itemCondition') or product.get('itemCondition') or ''
    row['condition'] = condition.rsplit('/', 1)[-1]
    row['description'] = product.get('description', '')
    labels = {'condition': ['condition', 'tình trạng'], 'unit_weight': ['weight', 'trọng lượng', 'berat produk'],
              'stock_quantity': ['stock', 'kho hàng', 'stok'],
              'minimum_purchase': ['minimum purchase', 'min. pembelian', 'mua tối thiểu'],
              'category': ['category', 'danh mục', 'kategori'],
              'pack_type': ['pack type', 'loại đóng gói'],
              'consumables_form': ['consumables form', 'dạng sản phẩm'],
              'volume': ['volume', 'thể tích', 'dung tích'],
              'ingredient': ['ingredient', 'ingredients', 'thành phần'],
              'circulation_number': ['circulation number', 'số lưu hành']}
    for section in soup.find_all('section'):
        title = section.find(['h2', 'h3'], recursive=False)
        if title and title.get_text(' ', strip=True).casefold() in ('product description', 'mô tả sản phẩm'):
            content = title.find_next_sibling()
            if content:
                row['description'] = content.get_text('\n', strip=True)
    for label in soup.find_all('h3'):
        key = label.get_text(' ', strip=True).casefold()
        value = label.find_next_sibling()
        if not value:
            continue
        for field, names in labels.items():
            if key not in names:
                continue
            text = value.get_text(' ', strip=True)
            if field == 'stock_quantity' and not re.fullmatch(r'[\d.,]+', text):
                continue  # IN STOCK is availability, not a quantity.
            if field == 'category':
                text = ' > '.join(a.get_text(' ', strip=True) for a in value.find_all('a')
                                  if a.get_text(' ', strip=True).casefold() != 'shopee') or text
            row[field] = text
    for element in soup(['script', 'style', 'noscript']):
        element.decompose()
    text = soup.get_text(' ', strip=True)
    sold = re.search(r'([\d.,]+\s*(?:k|m|rb|ribu|jt)?\+?)\s*(?:sold|đã bán|terjual)\b', text, re.I)
    if sold:
        row['sold_count'] = sold[1].strip()
    if not row['product_name'] or not row['price']:
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
