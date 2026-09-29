"""
Playwright parser: opens brain.com.ua, searches for "Apple iPhone 15 128GB Black",
opens the first search result, collects product info, prints it and saves it into the Product model
"""

import os
from pprint import pprint

from playwright.sync_api import sync_playwright, Error, TimeoutError as PlaywrightTimeout

from load_django import *
from parser_app.models import Product

BASE_URL = 'https://brain.com.ua/ukr/'
SEARCH_QUERY = 'Apple iPhone 15 128GB Black'

# Persistent profile keeps cookies between runs, so the site's security check
# (if it shows up) has to be passed by hand only once
PROFILE_DIR = os.environ.get('PLAYWRIGHT_PROFILE_DIR', os.path.expanduser('~/.cache/brain-parsers/playwright_profile'))
SEARCH_BUTTON_XPATH = "//input[contains(@class, 'search-button-first-form')]"


def to_int(text):
    """'35 499 ₴' -> 35499"""
    digits = ''.join(char for char in text if char.isdigit())
    return int(digits) if digits else None


def clean(text):
    return ' '.join(text.split())


def get_spec_value(specs_block, title):
    # Find the title span and take the value from the next span (position independent)
    value = specs_block.locator(f'xpath=.//span[text()="{title}"]/following-sibling::span')
    if value.count() == 0:
        return None
    return clean(value.first.text_content())


def wait_for_security_check(page):
    # Cloudflare page has no site header - if it is shown, wait until a human passes it
    if page.locator(f'xpath={SEARCH_BUTTON_XPATH}').count() == 0:
        print('Security check is shown - pass it manually in the opened browser window (waiting up to 3 min)')
        page.locator(f'xpath={SEARCH_BUTTON_XPATH}').first.wait_for(state='attached', timeout=180_000)
        page.wait_for_timeout(2000)


def search_product(page, query):
    page.goto(BASE_URL, wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    wait_for_security_check(page)

    search_input = page.locator(f'xpath={SEARCH_BUTTON_XPATH}/preceding-sibling::input[@type="search"]')
    search_input.wait_for(state='visible')
    search_input.fill(query)
    page.wait_for_timeout(1000)

    page.locator(f'xpath={SEARCH_BUTTON_XPATH}').click()

    # Wait for the search results page
    page.wait_for_url('**/search/**')
    page.wait_for_timeout(2000)
    wait_for_security_check(page)

    first_result = page.locator("xpath=(//div[contains(@class, 'br-pp-img-grid')]/a)[1]")
    first_result.wait_for(state='visible')
    first_result.scroll_into_view_if_needed()
    first_result.click()

    # Wait for the product page
    page.locator("xpath=//h1[contains(@class, 'main-title')]").wait_for()
    page.wait_for_load_state('domcontentloaded')
    page.wait_for_timeout(2000)


def open_all_specs(page):
    button = page.locator("xpath=//button[span[text()='Всі характеристики']]")
    if button.count() == 0:
        print('There is no "All characteristics" button')
        return
    try:
        button.first.scroll_into_view_if_needed()
        button.first.click()
        page.wait_for_timeout(1000)
    except PlaywrightTimeout:
        print('Could not click "All characteristics" button')


def get_product_data(page):
    product = {}

    name = page.locator("xpath=//h1[contains(@class, 'main-title')]")
    product['name'] = clean(name.first.text_content()) if name.count() else None

    code = page.locator("xpath=//span[@class='br-pr-code-val']")
    product['product_code'] = clean(code.first.text_content()) if code.count() else None

    # All characteristics live in one container - find it once and reuse
    specs_block = page.locator("xpath=//div[@class='br-pr-chr']").first

    product['manufacturer'] = get_spec_value(specs_block, 'Виробник')
    product['color'] = get_spec_value(specs_block, 'Колір')
    product['memory'] = get_spec_value(specs_block, "Вбудована пам'ять")

    # Price: if the old price block exists, the product is on sale
    price_block = page.locator("xpath=//div[contains(@class, 'main-price-block')]").first
    new_price = price_block.locator("xpath=./div[@class='br-pr-np']//span")
    old_price = price_block.locator("xpath=./div[@class='br-pr-op']//span")
    new_price = to_int(new_price.first.text_content()) if new_price.count() else None
    if old_price.count():
        product['price'] = to_int(old_price.first.text_content())
        product['sale_price'] = new_price
    else:
        product['price'] = new_price
        product['sale_price'] = None

    reviews = page.locator("xpath=//a[contains(@class, 'reviews-count')]/span")
    product['reviews_count'] = to_int(reviews.first.text_content()) if reviews.count() else None

    product['screen_diagonal'] = get_spec_value(specs_block, 'Діагональ екрану')
    product['screen_resolution'] = get_spec_value(specs_block, 'Роздільна здатність екрану')

    photos = [img.get_attribute('src') for img in page.locator("xpath=//img[contains(@class, 'br-main-img')]").all()]
    product['photos'] = list(dict.fromkeys(photo for photo in photos if photo)) or None

    specifications = {}
    for row in specs_block.locator("xpath=.//div[@class='br-pr-chr-item']/div/div[span]").all():
        spans = row.locator('xpath=./span')
        if spans.count() < 2:
            continue
        specifications[clean(spans.nth(0).text_content())] = clean(spans.nth(1).text_content())
    product['specifications'] = specifications or None

    product['parser'] = 'playwright'
    product['link'] = page.url

    return product


def main():
    with sync_playwright() as p:
        # One browser (persistent context) for the whole run
        try:
            context = p.chromium.launch_persistent_context(
                PROFILE_DIR,
                channel='chrome',
                headless=False,
                viewport={'width': 1400, 'height': 900},
                locale='uk-UA',
                timezone_id='Europe/Kyiv',
            )
        except Error as error:
            print(f'Unable to launch browser - {error}')
            return

        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(15_000)

        try:
            search_product(page, SEARCH_QUERY)
            open_all_specs(page)
            product = get_product_data(page)
        except PlaywrightTimeout as error:
            print(f'Page did not load in time: {error}')
            context.close()
            return

        context.close()

    pprint(product, sort_dicts=False)

    obj, created = Product.objects.get_or_create(**product)
    print(f'Saved to DB: id={obj.id}, created={created}')


if __name__ == '__main__':
    main()
