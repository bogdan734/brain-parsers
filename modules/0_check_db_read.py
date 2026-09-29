"""
Checks that load_django works: reads test records from the Product model and prints them
"""

from load_django import *
from parser_app.models import Product

for product in Product.objects.filter(parser='check').order_by('id'):
    print(product.id, product.name, product.product_code, product.created_at)
