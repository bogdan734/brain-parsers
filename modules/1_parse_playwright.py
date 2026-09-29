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
# (if it shows up) has to be passed by hand only once. Same profile as the Selenium parser.
# Kept outside Desktop/Documents - macOS blocks Chrome from those folders without a permission prompt
PROFILE_DIR = os.environ.get('CHROME_PROFILE_DIR', os.path.expanduser('~/.cache/brain-parsers/chrome_profile'))
SECURITY_CHECK_TIMEOUT = int(os.environ.get('SECURITY_CHECK_TIMEOUT', 180))  # seconds
# Optional: attach to an already running Chrome started with --remote-debugging-port (e.g. 127.0.0.1:9222)
DEBUGGER_ADDRESS = os.environ.get('CHROME_DEBUGGER_ADDRESS')
SEARCH_BUTTON_XPATH = "//input[contains(@class, 'search-button-first-form')]"
POPUP_SEARCH_BUTTON_XPATH = "//input[@class='qsr-submit']"


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
        print(f'Security check is shown - pass it manually in the opened browser window '
              f'(waiting up to {SECURITY_CHECK_TIMEOUT // 60} min)')
        page.locator(f'xpath={SEARCH_BUTTON_XPATH}').first.wait_for(state='attached', timeout=SECURITY_CHECK_TIMEOUT * 1000)
        page.wait_for_timeout(2000)


def search_product(page, query):
    page.goto(BASE_URL, wait_until='domcontentloaded')
    page.wait_for_timeout(2000)
    wait_for_security_check(page)

    search_input = page.locator(f'xpath={SEARCH_BUTTON_XPATH}/preceding-sibling::input[@type="search"]')
    search_input.wait_for(state='visible')
    search_input.fill(query)
    page.wait_for_timeout(2000)

    # Typing may open the quick search popup - its own "Знайти" button then covers the header one
    popup_button = page.locator(f'xpath={POPUP_SEARCH_BUTTON_XPATH}')
    if popup_button.count() and popup_button.first.is_visible():
        popup_button.first.click()
    else:
        page.locator(f'xpath={SEARCH_BUTTON_XPATH}').click()

    # Wait for the search results page
    page.wait_for_url('**/search/**')
    page.wait_for_timeout(2000)
    wait_for_security_check(page)

    first_result = page.locator("xpath=(//div[contains(@class, 'br-pp-img-grid')]/a)[1]")
    first_result.wait_for(state='visible')
    first_result.scroll_into_view_if_needed()
    first_result.click()

    # Wait for the product page (title may be hidden in narrow layouts, so wait for presence)
    page.locator("xpath=//h1[contains(@class, 'main-title')]").wait_for(state='attached')
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
        # One browser for the whole run: either attach to a running Chrome or launch our own
        browser = None
        try:
            if DEBUGGER_ADDRESS:
                browser = p.chromium.connect_over_cdp(f'http://{DEBUGGER_ADDRESS}')
                context = browser.contexts[0]
            else:
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
            raise SystemExit(1)

        page = context.new_page()
        page.set_default_timeout(15_000)

        try:
            search_product(page, SEARCH_QUERY)
            open_all_specs(page)
            product = get_product_data(page)
        except PlaywrightTimeout:
            print(f'Page did not load in time: {page.url}')
            raise SystemExit(1)
        except Error as error:
            print(f'Browser error (window closed?): {error.message}')
            raise SystemExit(1)
        finally:
            if browser:
                # Attached Chrome stays open - close only our tab and disconnect
                page.close()
                browser.close()
            else:
                context.close()

    pprint(product, sort_dicts=False)

    obj, created = Product.objects.get_or_create(**product)
    print(f'Saved to DB: id={obj.id}, created={created}')


if __name__ == '__main__':
    main()
