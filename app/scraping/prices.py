"""Read the active product price, excluding original and recommendation prices."""
import re
from decimal import Decimal


def parse_price_range(text, currency):
    text = text.replace('\u00a0', ' ').strip()
    parts = re.split(r'\s*[-–—]\s*', text)
    if len(parts) not in (1, 2):
        raise ValueError(f'Unrecognized price range: {text!r}')
    amounts = []
    for part in parts:
        amount = re.sub(r'(?:NT\$|R\$|S\$|RP|RM|VND|IDR|PHP|SGD|MYR|THB|TWD|BRL|[₫đ฿₱$\s])', '', part, flags=re.I)
        if currency in ('VND', 'TWD'):
            if not re.fullmatch(r'\d+|\d{1,3}(?:[.,]\d{3})+', amount):
                raise ValueError(f'Unrecognized {currency} price: {part!r}')
            amount = amount.replace('.', '').replace(',', '')
        elif currency in ('IDR', 'BRL'):
            if not re.fullmatch(r'(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?', amount):
                raise ValueError(f'Unrecognized {currency} price: {part!r}')
            amount = amount.replace('.', '').replace(',', '.')
        else:
            amount = amount.replace(',', '')
            if not re.fullmatch(r'\d+(?:\.\d+)?', amount):
                raise ValueError(f'Unrecognized price: {part!r}')
        amounts.append(amount)
    if len(amounts) == 1:
        amounts *= 2
    if Decimal(amounts[0]) > Decimal(amounts[1]):
        raise ValueError('Minimum price exceeds maximum price')
    return amounts[0], amounts[1]


def read_price(sb, currency='VND'):
    snapshot = sb.cdp.evaluate(r"""(() => {
        const visible = el => el.getClientRects().length &&
            getComputedStyle(el).visibility !== 'hidden';
        // Shopee announces active prices in a live region. Scope to that
        // region so shipping amounts and recommended products cannot match.
        const region = [...document.querySelectorAll('section[aria-live]')]
            .find(el => visible(el) && /[₫฿₱$]|(?:Rp|RM)\s*\d/i.test(el.innerText));
        if (!region) return null;
        const candidates = [...region.querySelectorAll('*')].filter(el => {
            const style = getComputedStyle(el);
            return visible(el) && /[₫฿₱$]|(?:Rp|RM)\s*\d/i.test(el.innerText) &&
                !el.closest('del,s') && !style.textDecorationLine.includes('line-through') &&
                ![...el.children].some(child => /[₫฿₱$]|(?:Rp|RM)\s*\d/i.test(child.innerText));
        });
        candidates.sort((a, b) => parseFloat(getComputedStyle(b).fontSize) -
                                    parseFloat(getComputedStyle(a).fontSize));
        return candidates.length ? candidates[0].innerText : null;
    })()""")
    if not snapshot:
        raise RuntimeError('Active product price was not found; refusing to save a zero price.')
    minimum, maximum = parse_price_range(snapshot, currency)
    return minimum, maximum, currency, snapshot.strip()
