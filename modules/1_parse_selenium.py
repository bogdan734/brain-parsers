"""
Selenium parser: opens brain.com.ua, searches for "Apple iPhone 15 128GB Black",
opens the first search result, collects product info, prints it and saves it into the Product model
"""

import os
from pprint import pprint
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from load_django import *
from parser_app.models import Product

BASE_URL = 'https://brain.com.ua/ukr/'
SEARCH_QUERY = 'Apple iPhone 15 128GB Black'

# Chrome profile keeps cookies between runs, so the site's security check
# (if it shows up) has to be passed by hand only once
# (kept outside Desktop/Documents - macOS blocks Chrome from those folders without a permission prompt)
PROFILE_DIR = os.environ.get('CHROME_PROFILE_DIR', os.path.expanduser('~/.cache/brain-parsers/chrome_profile'))
FIRST_RESULT_XPATH = "(//div[contains(@class, 'br-pp-img-grid')]/a)[1]"


def to_int(text):
    """'35 499 ₴' -> 35499"""
    digits = ''.join(char for char in text if char.isdigit())
    return int(digits) if digits else None


def clean(element):
    # textContent works for elements hidden behind "show more" too, .text does not
    return ' '.join(element.get_attribute('textContent').split())


def get_spec_value(specs_block, title):
    # Find the title span and take the value from the next span (position independent)
    return clean(specs_block.find_element(By.XPATH, f'.//span[text()="{title}"]/following-sibling::span'))


def get_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument(f'--user-data-dir={PROFILE_DIR}')
    return webdriver.Chrome(options=options)


def wait_for_security_check(driver):
    # Cloudflare page has no site header - if it is shown, wait until a human passes it
    if not driver.find_elements(By.XPATH, "//input[contains(@class, 'search-button-first-form')]"):
        print('Security check is shown - pass it manually in the opened browser window (waiting up to 3 min)')
        WebDriverWait(driver, 180).until(EC.presence_of_element_located(
            (By.XPATH, "//input[contains(@class, 'search-button-first-form')]")
        ))
        sleep(2)


def search_product(driver, wait, query):
    driver.get(BASE_URL)
    sleep(2)
    wait_for_security_check(driver)

    search_input = wait.until(EC.visibility_of_element_located(
        (By.XPATH, "//input[contains(@class, 'search-button-first-form')]/preceding-sibling::input[@type='search']")
    ))
    search_input.clear()
    search_input.send_keys(query)
    sleep(1)

    search_button = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//input[contains(@class, 'search-button-first-form')]")
    ))
    search_button.click()

    # Wait for the search results page
    wait.until(EC.url_contains('/search/'))
    sleep(2)
    wait_for_security_check(driver)
    first_result = wait.until(EC.element_to_be_clickable((By.XPATH, FIRST_RESULT_XPATH)))
    driver.execute_script('arguments[0].scrollIntoView({block: "center"});', first_result)
    sleep(1)
    first_result.click()

    # Wait for the product page
    wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(@class, 'main-title')]")))
    sleep(2)


def open_all_specs(driver):
    try:
        button = driver.find_element(By.XPATH, "//button[span[text()='Всі характеристики']]")
        driver.execute_script('arguments[0].scrollIntoView({block: "center"});', button)
        sleep(1)
        driver.execute_script('arguments[0].click();', button)
        sleep(1)
    except NoSuchElementException:
        print('There is no "All characteristics" button')


def get_product_data(driver):
    product = {}

    try:
        product['name'] = clean(driver.find_element(By.XPATH, "//h1[contains(@class, 'main-title')]"))
    except NoSuchElementException:
        product['name'] = None

    try:
        product['product_code'] = clean(driver.find_element(By.XPATH, "//span[@class='br-pr-code-val']"))
    except NoSuchElementException:
        product['product_code'] = None

    # All characteristics live in one container - find it once and reuse
    try:
        specs_block = driver.find_element(By.XPATH, "//div[@class='br-pr-chr']")
    except NoSuchElementException:
        specs_block = None

    try:
        product['manufacturer'] = get_spec_value(specs_block, 'Виробник')
    except (NoSuchElementException, AttributeError):
        product['manufacturer'] = None

    try:
        product['color'] = get_spec_value(specs_block, 'Колір')
    except (NoSuchElementException, AttributeError):
        product['color'] = None

    try:
        product['memory'] = get_spec_value(specs_block, "Вбудована пам'ять")
    except (NoSuchElementException, AttributeError):
        product['memory'] = None

    # Price: if the old price block exists, the product is on sale
    try:
        price_block = driver.find_element(By.XPATH, "//div[contains(@class, 'main-price-block')]")
        new_price = to_int(clean(price_block.find_element(By.XPATH, "./div[@class='br-pr-np']//span")))
        old_price = price_block.find_elements(By.XPATH, "./div[@class='br-pr-op']//span")
        if old_price:
            product['price'] = to_int(clean(old_price[0]))
            product['sale_price'] = new_price
        else:
            product['price'] = new_price
            product['sale_price'] = None
    except NoSuchElementException:
        product['price'] = None
        product['sale_price'] = None

    try:
        product['reviews_count'] = to_int(clean(driver.find_element(By.XPATH, "//a[contains(@class, 'reviews-count')]/span")))
    except NoSuchElementException:
        product['reviews_count'] = None

    try:
        product['screen_diagonal'] = get_spec_value(specs_block, 'Діагональ екрану')
    except (NoSuchElementException, AttributeError):
        product['screen_diagonal'] = None

    try:
        product['screen_resolution'] = get_spec_value(specs_block, 'Роздільна здатність екрану')
    except (NoSuchElementException, AttributeError):
        product['screen_resolution'] = None

    photos = [img.get_attribute('src') for img in driver.find_elements(By.XPATH, "//img[contains(@class, 'br-main-img')]")]
    product['photos'] = list(dict.fromkeys(photo for photo in photos if photo)) or None

    try:
        specifications = {}
        for row in specs_block.find_elements(By.XPATH, ".//div[@class='br-pr-chr-item']/div/div[span]"):
            spans = row.find_elements(By.XPATH, './span')
            if len(spans) < 2:
                continue
            specifications[clean(spans[0])] = clean(spans[1])
        product['specifications'] = specifications or None
    except AttributeError:
        product['specifications'] = None

    product['parser'] = 'selenium'
    product['link'] = driver.current_url

    return product


def main():
    driver = get_driver()
    wait = WebDriverWait(driver, 15)

    try:
        search_product(driver, wait, SEARCH_QUERY)
        open_all_specs(driver)
        product = get_product_data(driver)
    except TimeoutException as error:
        print(f'Page did not load in time: {error}')
        driver.quit()
        return

    driver.quit()

    pprint(product, sort_dicts=False)

    obj, created = Product.objects.get_or_create(**product)
    print(f'Saved to DB: id={obj.id}, created={created}')


if __name__ == '__main__':
    main()
