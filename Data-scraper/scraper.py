import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import re
import time
import random
import json
import pandas as pd
from collections import deque
import tldextract

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
]
DELAY = random.uniform(1, 3)
PRICE_REGEX = re.compile(r'(\$?[\d,]+(?:\.\d{1,2})?)')
PRODUCT_PATH_PATTERNS = [
    r'/collections/[^/]+/products/',
    r'/products/',
    r'/product/',
    r'/shop/',
    r'/item/',
    r'/p/',
    r'/buy/',
    r'/furniture/'
]
MAX_PAGES_PER_DOMAIN = 50
MAX_PRODUCTS_PER_DOMAIN = 100
MAX_DEPTH = 3

ROBOTS_CACHE = {}


def normalize_url(url):
    parsed = urlparse(url)
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean_url.rstrip('/')


def get_domain(url):
    extracted = tldextract.extract(url)
    return f"{extracted.domain}.{extracted.suffix}"


def get_robots_parser(url):
    domain = get_domain(url)
    if domain in ROBOTS_CACHE:
        return ROBOTS_CACHE[domain]

    parser = RobotFileParser()
    base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
    try:
        parser.set_url(base_url)
        parser.read()
        ROBOTS_CACHE[domain] = parser
        return parser
    except Exception:
        permissive_parser = RobotFileParser()
        permissive_parser.parse([])
        ROBOTS_CACHE[domain] = permissive_parser
        return permissive_parser


def extract_prices(soup):
    prices = {'regular': None, 'sale': None}

    script_data = soup.find('script', type='application/ld+json')
    if script_data:
        try:
            ld_json = json.loads(script_data.string)
            if isinstance(ld_json, list):
                ld_json = ld_json[0] if ld_json else {}

            offers = ld_json.get('offers', {})
            if isinstance(offers, list) and offers:
                offers = offers[0]

            if 'price' in offers:
                prices['regular'] = offers['price']
            if 'salePrice' in offers:
                prices['sale'] = offers['salePrice']
        except Exception:
            pass

    price_selectors = [
        {'class': ['price', 'product-price', 'price-item']},
        {'itemprop': 'price'},
        {'class': 'regular-price'},
        {'class': 'current-price'},
        {'class': 'sale-price'},
        {'data-product-price': True},
        {'id': 'price'},
    ]

    for selector in price_selectors:
        element = soup.find(attrs=selector)
        if element:
            price_text = element.get_text(strip=True)
            price_match = PRICE_REGEX.search(price_text)
            if price_match:
                price_value = price_match.group(1)
                classes = element.get('class', [])
                class_str = ' '.join(classes).lower()
                if 'sale' in class_str or 'discount' in class_str:
                    prices['sale'] = price_value
                else:
                    prices['regular'] = prices['regular'] or price_value

    if not prices['regular']:
        product_section = soup.find(class_=re.compile(r'product|item|detail', re.I))
        if product_section:
            price_text = product_section.get_text()
            price_match = PRICE_REGEX.search(price_text)
            if price_match:
                prices['regular'] = price_match.group(1)

    if prices['sale'] and not prices['regular']:
        prices['regular'] = prices['sale']
        prices['sale'] = None

    return prices


def extract_product_name(soup, url):
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content'].strip()

    title_selectors = [
        {'class': ['product-title', 'product-name', 'product__title']},
        {'id': 'product-title'},
        {'itemprop': 'name'},
        {'class': 'product-single__title'},
        {'data-product-title': True}
    ]

    for selector in title_selectors:
        element = soup.find(attrs=selector)
        if element:
            return element.get_text(strip=True)

    h1_tags = soup.find_all('h1')
    for h1 in h1_tags:
        classes = h1.get('class', [])
        if any(cls in ['product-title', 'title', 'name'] for cls in classes):
            return h1.get_text(strip=True)

    return url.split('/')[-1].replace('-', ' ').title()


def extract_product_description(soup):
    meta_desc = soup.find('meta', property='og:description')
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content'].strip()

    script_data = soup.find('script', type='application/ld+json')
    if script_data:
        try:
            ld_json = json.loads(script_data.string)
            if isinstance(ld_json, list):
                ld_json = ld_json[0] if ld_json else {}
            description = ld_json.get('description')
            if description:
                return description.strip()
        except:
            pass

    description_selectors = [
        {'class': ['product-description', 'description', 'product__description']},
        {'id': 'product-description'},
        {'itemprop': 'description'},
        {'class': 'product-single__description'},
        {'data-product-description': True}
    ]

    for selector in description_selectors:
        element = soup.find(attrs=selector)
        if element:
            return element.get_text(strip=True)

    first_paragraph = soup.find('p')
    if first_paragraph:
        return first_paragraph.get_text(strip=True)

    return None


def is_product_page(url):
    path = urlparse(url).path.lower()
    for pattern in PRODUCT_PATH_PATTERNS:
        if re.search(pattern, path):
            return True
    return False


def find_collection_pages(soup, base_url):
    collection_links = set()

    nav_selectors = [
        {'class': ['nav', 'navigation', 'main-menu']},
        {'id': 'main-nav'},
        {'class': 'site-nav'},
        {'role': 'navigation'}
    ]

    content_selectors = [
        {'class': ['collection-grid', 'product-grid', 'shop-grid']},
        {'id': 'collections'},
        {'class': 'collection-list'},
        {'class': 'shop-by-category'}
    ]

    for selector in nav_selectors:
        nav_element = soup.find('nav', attrs=selector)
        if nav_element:
            links = nav_element.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '/collections/' in href or '/collection/' in href or '/shop/' in href:
                    absolute_url = urljoin(base_url, href)
                    collection_links.add(normalize_url(absolute_url))

    for selector in content_selectors:
        content_element = soup.find('div', attrs=selector)
        if content_element:
            links = content_element.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '/collections/' in href or '/collection/' in href or '/shop/' in href:
                    absolute_url = urljoin(base_url, href)
                    collection_links.add(normalize_url(absolute_url))

    return list(collection_links)


def find_product_links(soup, base_url):
    product_links = set()

    card_selectors = [
        {'class': re.compile(r'card|product-card|grid-item', re.I)},
        {'class': re.compile(r'product-item|product-grid-item', re.I)},
        {'class': re.compile(r'collection-item|product-block', re.I)},
        {'class': re.compile(r'product-thumbnail|product-info', re.I)}
    ]

    for selector in card_selectors:
        cards = soup.find_all(attrs=selector)
        for card in cards:
            link = card.find('a', href=True)
            if link:
                href = link['href']
                if href and not href.startswith(('mailto:', 'tel:', 'javascript:')):
                    absolute_url = urljoin(base_url, href)
                    if is_product_page(absolute_url):
                        product_links.add(normalize_url(absolute_url))

    return list(product_links)


def scrape_product_page(url):
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        print(f"Scraping product page: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"   Failed to fetch product page (status: {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        name = extract_product_name(soup, url)
        prices = extract_prices(soup)
        description = extract_product_description(soup)
        regular, sale = prices.get('regular'), prices.get('sale')

        if not name:
            print(f"   Product name not found on: {url}")
            return None

        product_data = {
            'name': name,
            'regular_price': regular,
            'sale_price': sale,
            'description': description,
            'url': url
        }

        print(f"   Found product: {name}")
        if regular or sale:
            print(f"      Regular: {regular} | Sale: {sale}")
        else:
            print("      No price found")
        if description:
            print(f"      Description: {description[:50]}...")

        return product_data
    except Exception as e:
        print(f"Error scraping product page {url}: {str(e)}")
        return None


def crawl_domain(start_urls):
    domain = get_domain(start_urls[0])
    robots_parser = get_robots_parser(start_urls[0])
    visited = set()
    queue = deque([(url, 0) for url in start_urls])  # (url, depth)
    product_data = []

    print(f"Discovering product pages for {domain}...")
    while queue and len(visited) < MAX_PAGES_PER_DOMAIN and len(product_data) < MAX_PRODUCTS_PER_DOMAIN:
        url, depth = queue.popleft()
        normalized_url = normalize_url(url)

        if normalized_url in visited:
            continue
        visited.add(normalized_url)

        # Respect robots.txt and crawling depth
        if depth > MAX_DEPTH or not robots_parser.can_fetch('*', url):
            continue

        try:
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            print(f"Fetching: {url} (depth: {depth})")
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            if '/collections/' in url.lower() or '/collection/' in url.lower() or '/shop/' in url.lower():
                product_links = find_product_links(soup, url)
                print(f"   Found {len(product_links)} product links")

                for product_url in product_links:
                    if normalize_url(product_url) not in visited:
                        queue.append((product_url, depth + 1))

            collection_links = find_collection_pages(soup, url)
            for collection_url in collection_links:
                if normalize_url(collection_url) not in visited:
                    queue.append((collection_url, depth + 1))

            time.sleep(DELAY)

        except Exception as e:
            print(f"Error processing {url}: {str(e)}")

    print(f"Scraping discovered product pages for {domain}...")
    product_urls = [url for url, depth in queue if is_product_page(url)]
    for url in product_urls:
        if len(product_data) >= MAX_PRODUCTS_PER_DOMAIN:
            break

        product = scrape_product_page(url)
        if product:
            product_data.append(product)
        time.sleep(DELAY)

    return product_data


def generate_training_example(product_name, regular_price, sale_price, description):
    if not product_name:
        return None

    if description:
        context = f"{product_name}: {description}"
    elif sale_price and regular_price:
        context = f"Special offer: {product_name} now {sale_price} (was {regular_price})"
    elif sale_price:
        context = f"Sale: {product_name} for {sale_price}"
    elif regular_price:
        context = f"Price: {product_name} at {regular_price}"
    else:
        context = product_name

    start_index = context.lower().find(product_name.lower())
    if start_index == -1:
        return None

    end_index = start_index + len(product_name)

    return {
        "text": context,
        "entities": [[start_index, end_index, "PRODUCT"]]
    }


if __name__ == "__main__":
    urls_df = pd.read_csv('URL_list.csv', header=None, names=['url'])
    all_urls = urls_df['url'].tolist()

    domain_groups = {}
    for url in all_urls:
        domain = get_domain(url)
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(url)

    all_product_data = []
    for domain, start_urls in domain_groups.items():
        print(f"\nStarting crawl for domain: {domain}")
        print(f"   Starting URLs: {len(start_urls)}")
        domain_products = crawl_domain(start_urls)
        all_product_data.extend(domain_products)
        print(f"   Found products: {len(domain_products)}")

    training_data = []
    for product in all_product_data:
        example = generate_training_example(
            product['name'],
            product['regular_price'],
            product['sale_price'],
            product['description']
        )
        if example:
            training_data.append(example)

    with open('ner_training_data.jsonl', 'w') as f:
        for entry in training_data:
            f.write(json.dumps(entry) + '\n')

    print(f"\nTotal training examples generated: {len(training_data)}")
    print("Scraping complete!")