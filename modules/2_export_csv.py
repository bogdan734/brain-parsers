"""
Exports all products from the Product model into results/products.csv
"""

import csv
import json
import os

from load_django import *
from parser_app.models import Product

RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'results'))
CSV_PATH = os.path.join(RESULTS_DIR, 'products.csv')

FIELDS = [
    'id', 'name', 'product_code', 'manufacturer', 'color', 'memory', 'price', 'sale_price',
    'reviews_count', 'screen_diagonal', 'screen_resolution', 'photos', 'specifications',
    'parser', 'link', 'created_at',
]

os.makedirs(RESULTS_DIR, exist_ok=True)

products = Product.objects.exclude(parser='check').order_by('id')

# utf-8-sig so Excel opens Cyrillic correctly
with open(CSV_PATH, 'w', newline='', encoding='utf-8-sig') as file:
    writer = csv.DictWriter(file, fieldnames=FIELDS)
    writer.writeheader()
    for product in products:
        row = {field: getattr(product, field) for field in FIELDS}
        row['photos'] = ' | '.join(product.photos) if product.photos else None
        row['specifications'] = json.dumps(product.specifications, ensure_ascii=False) if product.specifications else None
        writer.writerow(row)

print(f'Exported {products.count()} products to {CSV_PATH}')
