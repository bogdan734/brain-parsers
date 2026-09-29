"""
Requests + BS4 parser: collects product info from a brain.com.ua product page,
prints it and saves it into the Product model
"""

from pprint import pprint

import requests
from bs4 import BeautifulSoup

from load_django import *
from parser_app.models import Product

URL = 'https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html'

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://brain.com.ua/',
}


def to_int(text):
    """'65 799 ₴' -> 65799"""
    digits = ''.join(char for char in text if char.isdigit())
    return int(digits) if digits else None


def get_spec_value(specs_block, title):
    # Find the title span and take the value from the next span (position independent)
    title_span = specs_block.find('span', string=title)
    return ' '.join(title_span.find_next_sibling('span').text.split())


response = requests.get(URL, headers=headers, timeout=30)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    product = {}

    try:
        product['name'] = soup.find('h1', class_='main-title').text.strip()
    except AttributeError:
        product['name'] = None

    try:
        product['product_code'] = soup.find('span', class_='br-pr-code-val').text.strip()
    except AttributeError:
        product['product_code'] = None

    # All characteristics live in one container - find it once and reuse
    specs_block = soup.find('div', class_='br-pr-chr')

    try:
        product['manufacturer'] = get_spec_value(specs_block, 'Виробник')
    except AttributeError:
        product['manufacturer'] = None

    try:
        product['color'] = get_spec_value(specs_block, 'Колір')
    except AttributeError:
        product['color'] = None

    try:
        product['memory'] = get_spec_value(specs_block, "Вбудована пам'ять")
    except AttributeError:
        product['memory'] = None

    # Price: if the old price block exists, the product is on sale
    price_block = soup.find('div', class_='main-price-block')

    try:
        old_price = price_block.find('div', class_='br-pr-op')
        new_price = price_block.find('div', class_='br-pr-np')
        if old_price:
            product['price'] = to_int(old_price.find('span').text)
            product['sale_price'] = to_int(new_price.find('span').text)
        else:
            product['price'] = to_int(new_price.find('span').text)
            product['sale_price'] = None
    except AttributeError:
        product['price'] = None
        product['sale_price'] = None

    try:
        product['reviews_count'] = to_int(soup.find('a', class_='reviews-count').find('span').text)
    except AttributeError:
        product['reviews_count'] = None

    try:
        product['screen_diagonal'] = get_spec_value(specs_block, 'Діагональ екрану')
    except AttributeError:
        product['screen_diagonal'] = None

    try:
        product['screen_resolution'] = get_spec_value(specs_block, 'Роздільна здатність екрану')
    except AttributeError:
        product['screen_resolution'] = None

    try:
        photos = [img.get('src') for img in soup.find_all('img', class_='br-main-img')]
        product['photos'] = list(dict.fromkeys(photos)) or None
    except AttributeError:
        product['photos'] = None

    try:
        specifications = {}
        for spec_item in specs_block.find_all('div', class_='br-pr-chr-item'):
            for row in spec_item.find('div').find_all('div', recursive=False):
                spans = row.find_all('span', recursive=False)
                if len(spans) < 2:
                    continue
                key = spans[0].text.strip()
                specifications[key] = ' '.join(spans[1].text.split())
        product['specifications'] = specifications or None
    except AttributeError:
        product['specifications'] = None

    product['parser'] = 'bs4'
    product['link'] = URL

    pprint(product, sort_dicts=False)

    obj, created = Product.objects.get_or_create(**product)
    print(f'Saved to DB: id={obj.id}, created={created}')

else:
    print(f'Error: {response.status_code}')
    raise SystemExit(1)
