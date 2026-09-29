from django.contrib.postgres.fields import ArrayField
from django.db import models


class Product(models.Model):
    # Main info
    name = models.CharField(max_length=255, null=True)
    product_code = models.CharField(max_length=50, null=True)
    manufacturer = models.CharField(max_length=100, null=True)
    color = models.CharField(max_length=100, null=True)
    memory = models.CharField(max_length=50, null=True)
    price = models.IntegerField(null=True)
    sale_price = models.IntegerField(null=True)
    reviews_count = models.IntegerField(null=True)
    screen_diagonal = models.CharField(max_length=50, null=True)
    screen_resolution = models.CharField(max_length=50, null=True)

    # Lists and nested data
    photos = ArrayField(models.URLField(max_length=500, null=True), null=True, blank=True)
    specifications = models.JSONField(null=True, blank=True)

    # Service fields
    parser = models.CharField(max_length=20, null=True)  # bs4 / selenium / playwright
    link = models.URLField(max_length=500, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f'{self.name} ({self.parser})'

    class Meta:
        verbose_name = 'Product'
