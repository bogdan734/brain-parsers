"""
Checks that load_django works: writes a test record into the Product model
"""

from load_django import *
from parser_app.models import Product

product, created = Product.objects.get_or_create(
    name='Test product',
    product_code='TEST-0001',
    parser='check',
)
print(f'Created: {created}, id: {product.id}')
