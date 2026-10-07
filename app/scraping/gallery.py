"""Find gallery images and display them for browser screenshots."""
import json
import re
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
from .csv_output import find_product


def gallery_images(html, thumbnails=()):
    sources = []
    for script in BeautifulSoup(html, 'html.parser').select('script[type="application/ld+json"]'):
        try:
            product = find_product(json.loads(script.get_text()))
        except (ValueError, TypeError):
            continue
        images = product.get('image', [])
        if not isinstance(images, list):
            images = [images]
        for image in images:
            if isinstance(image, dict):
                image = image.get('contentUrl') or image.get('url')
            if isinstance(image, str):
                sources.append(image)
    sources.extend(thumbnails)
    unique = {}
    for source in sources:
        parsed = urlparse(source)
        if parsed.scheme != 'https':
            continue
        path = re.sub(r'@resize.*$', '', parsed.path)
        path = re.sub(r'_tn$', '', path)
        url = urlunparse(parsed._replace(path=path))
        unique.setdefault((parsed.hostname, path), url)
    return list(unique.values())


def discover_gallery(sb):
    # Restrict fallback to the media preceding the product heading, excluding
    # seller avatars, description images, and recommendations below the product.
    thumbnails = sb.cdp.evaluate(r"""(() => {
        const heading = document.querySelector('h1');
        if (!heading) return [];
        return [...document.querySelectorAll('img')].filter(img => {
            const rect = img.getBoundingClientRect();
            return (img.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING) &&
                rect.width >= 40 && rect.height >= 40 &&
                /(?:img\.susercontent\.com|cf\.shopee\.[^/]+)\/file\//.test(img.currentSrc || img.src);
        }).map(img => img.currentSrc || img.src);
    })()""")
    return gallery_images(sb.cdp.get_page_source(), thumbnails or [])


def show_gallery_image(sb, url):
    sb.cdp.evaluate("""(() => {
        document.getElementById('scraper-gallery-capture')?.remove();
        const panel = document.createElement('div');
        panel.id = 'scraper-gallery-capture';
        panel.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:white;display:flex;align-items:center;justify-content:center';
        const img = document.createElement('img');
        img.style.cssText = 'width:100%;height:100%;object-fit:contain';
        img.src = """ + json.dumps(url) + """;
        panel.appendChild(img);
        document.body.appendChild(panel);
    })()""")


def image_loaded(sb):
    return sb.cdp.evaluate("""(() => {
        const img = document.querySelector('#scraper-gallery-capture img');
        return !!img && img.complete && img.naturalWidth > 0;
    })()""")


def hide_gallery(sb):
    sb.cdp.evaluate("document.getElementById('scraper-gallery-capture')?.remove()")
