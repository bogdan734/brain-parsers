from django.contrib import admin

from parser_app.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'product_code', 'price', 'sale_price', 'parser', 'created_at')
    list_filter = ('parser',)
    search_fields = ('name', 'product_code')
