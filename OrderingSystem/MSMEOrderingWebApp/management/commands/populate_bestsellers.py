from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from MSMEOrderingWebApp.models import ProductCategory, Products
import requests
from io import BytesIO
import os

class Command(BaseCommand):
    help = 'Populate database with best seller products for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to populate best seller products...'))
        
        # Create categories
        categories_data = [
            'Electronics',
            'Fashion & Accessories', 
            'Home & Garden',
            'Sports & Outdoors',
            'Beauty & Personal Care',
            'Books & Media',
            'Toys & Games',
            'Food & Beverages'
        ]
        
        categories = {}
        for cat_name in categories_data:
            category, created = ProductCategory.objects.get_or_create(name=cat_name)
            categories[cat_name] = category
            if created:
                self.stdout.write(f'Created category: {cat_name}')
        
        # Best seller products data with realistic information
        best_seller_products = [
            {
                'name': 'Wireless Bluetooth Headphones',
                'category': 'Electronics',
                'variations': [
                    {'name': 'Premium Edition', 'price': 2999.00, 'stocks': 50, 'sold_count': 245},
                    {'name': 'Standard Edition', 'price': 1899.00, 'stocks': 75, 'sold_count': 189},
                    {'name': 'Budget Edition', 'price': 999.00, 'stocks': 100, 'sold_count': 156}
                ],
                'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400&h=400&fit=crop'
            },
            {
                'name': 'Smart Fitness Watch',
                'category': 'Electronics',
                'variations': [
                    {'name': 'Pro Series', 'price': 4599.00, 'stocks': 30, 'sold_count': 198},
                    {'name': 'Sport Edition', 'price': 2899.00, 'stocks': 60, 'sold_count': 167},
                    {'name': 'Basic Model', 'price': 1599.00, 'stocks': 90, 'sold_count': 134}
                ],
                'image_url': 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400&h=400&fit=crop'
            },
            {
                'name': 'Organic Cotton T-Shirt',
                'category': 'Fashion & Accessories',
                'variations': [
                    {'name': 'Premium Cotton', 'price': 899.00, 'stocks': 200, 'sold_count': 312},
                    {'name': 'Regular Cotton', 'price': 599.00, 'stocks': 300, 'sold_count': 289},
                    {'name': 'Eco-Friendly', 'price': 799.00, 'stocks': 150, 'sold_count': 201}
                ],
                'image_url': 'https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=400&h=400&fit=crop'
            },
            {
                'name': 'Stainless Steel Water Bottle',
                'category': 'Home & Garden',
                'variations': [
                    {'name': '1L Capacity', 'price': 799.00, 'stocks': 120, 'sold_count': 278},
                    {'name': '750ml Capacity', 'price': 649.00, 'stocks': 180, 'sold_count': 245},
                    {'name': '500ml Capacity', 'price': 499.00, 'stocks': 250, 'sold_count': 198}
                ],
                'image_url': 'https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=400&h=400&fit=crop'
            },
            {
                'name': 'Yoga Mat Premium',
                'category': 'Sports & Outdoors',
                'variations': [
                    {'name': 'Extra Thick', 'price': 1299.00, 'stocks': 80, 'sold_count': 189},
                    {'name': 'Standard Thickness', 'price': 899.00, 'stocks': 150, 'sold_count': 234},
                    {'name': 'Travel Size', 'price': 649.00, 'stocks': 200, 'sold_count': 167}
                ],
                'image_url': 'https://images.unsplash.com/photo-1544367567-0f2fcb009e0b?w=400&h=400&fit=crop'
            },
            {
                'name': 'Natural Face Cream',
                'category': 'Beauty & Personal Care',
                'variations': [
                    {'name': 'Anti-Aging Formula', 'price': 1599.00, 'stocks': 60, 'sold_count': 223},
                    {'name': 'Moisturizing', 'price': 999.00, 'stocks': 120, 'sold_count': 198},
                    {'name': 'Sensitive Skin', 'price': 1199.00, 'stocks': 90, 'sold_count': 156}
                ],
                'image_url': 'https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400&h=400&fit=crop'
            },
            {
                'name': 'Bestselling Novel Collection',
                'category': 'Books & Media',
                'variations': [
                    {'name': 'Hardcover Edition', 'price': 899.00, 'stocks': 100, 'sold_count': 267},
                    {'name': 'Paperback', 'price': 599.00, 'stocks': 200, 'sold_count': 312},
                    {'name': 'Digital Copy', 'price': 399.00, 'stocks': 500, 'sold_count': 189}
                ],
                'image_url': 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=400&h=400&fit=crop'
            },
            {
                'name': 'Educational Building Blocks',
                'category': 'Toys & Games',
                'variations': [
                    {'name': '100 Pieces Set', 'price': 1299.00, 'stocks': 80, 'sold_count': 234},
                    {'name': '50 Pieces Set', 'price': 799.00, 'stocks': 150, 'sold_count': 198},
                    {'name': 'Starter Pack', 'price': 499.00, 'stocks': 300, 'sold_count': 167}
                ],
                'image_url': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&h=400&fit=crop'
            },
            {
                'name': 'Gourmet Coffee Beans',
                'category': 'Food & Beverages',
                'variations': [
                    {'name': 'Premium Arabica', 'price': 899.00, 'stocks': 100, 'sold_count': 289},
                    {'name': 'Medium Roast', 'price': 699.00, 'stocks': 150, 'sold_count': 245},
                    {'name': 'Dark Roast', 'price': 799.00, 'stocks': 120, 'sold_count': 201}
                ],
                'image_url': 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=400&h=400&fit=crop'
            },
            {
                'name': 'Portable Bluetooth Speaker',
                'category': 'Electronics',
                'variations': [
                    {'name': 'Waterproof Pro', 'price': 2499.00, 'stocks': 40, 'sold_count': 178},
                    {'name': 'Standard Model', 'price': 1599.00, 'stocks': 80, 'sold_count': 234},
                    {'name': 'Mini Speaker', 'price': 899.00, 'stocks': 150, 'sold_count': 189}
                ],
                'image_url': 'https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?w=400&h=400&fit=crop'
            },
            {
                'name': 'Designer Handbag',
                'category': 'Fashion & Accessories',
                'variations': [
                    {'name': 'Leather Tote', 'price': 3999.00, 'stocks': 25, 'sold_count': 156},
                    {'name': 'Crossbody Bag', 'price': 2499.00, 'stocks': 50, 'sold_count': 198},
                    {'name': 'Clutch', 'price': 1799.00, 'stocks': 75, 'sold_count': 134}
                ],
                'image_url': 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?w=400&h=400&fit=crop'
            },
            {
                'name': 'Smart LED Light Bulb',
                'category': 'Home & Garden',
                'variations': [
                    {'name': 'Color Changing', 'price': 899.00, 'stocks': 100, 'sold_count': 223},
                    {'name': 'White Light', 'price': 599.00, 'stocks': 200, 'sold_count': 289},
                    {'name': 'Warm Light', 'price': 649.00, 'stocks': 180, 'sold_count': 201}
                ],
                'image_url': 'https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=400&h=400&fit=crop'
            }
        ]
        
        # Create products
        products_created = 0
        for product_data in best_seller_products:
            category = categories[product_data['category']]
            
            for variation in product_data['variations']:
                # Check if product already exists
                existing_product = Products.objects.filter(
                    name=product_data['name'],
                    variation_name=variation['name']
                ).first()
                
                if not existing_product:
                    product = Products.objects.create(
                        category=category,
                        name=product_data['name'],
                        variation_name=variation['name'],
                        price=variation['price'],
                        stocks=variation['stocks'],
                        sold_count=variation['sold_count'],
                        available=True,
                        track_stocks=True
                    )
                    
                    # Try to download and save image
                    try:
                        response = requests.get(product_data['image_url'], timeout=10)
                        if response.status_code == 200:
                            image_content = ContentFile(response.content)
                            product.image.save(
                                f"{product_data['name'].replace(' ', '_')}_{variation['name'].replace(' ', '_')}.jpg",
                                image_content,
                                save=True
                            )
                            self.stdout.write(f'Added image for: {product_data["name"]} - {variation["name"]}')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Could not download image for {product_data["name"]}: {str(e)}'))
                    
                    products_created += 1
                    self.stdout.write(f'Created: {product_data["name"]} - {variation["name"]} (₱{variation["price"]:.2f})')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {products_created} products!'))
        self.stdout.write(self.style.SUCCESS('Best seller products have been populated in the database.'))
