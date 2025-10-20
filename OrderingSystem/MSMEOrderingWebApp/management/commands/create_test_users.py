from django.core.management.base import BaseCommand
from MSMEOrderingWebApp.models import User

class Command(BaseCommand):
    help = 'Create test customer accounts'

    def handle(self, *args, **options):
        customers = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'contact_number': '09123456789',
                'email': 'john@customer.com',
                'address': '123 Main Street',
                'city': 'Manila',
                'province': 'Metro Manila',
                'zipcode': '1000',
                'password': 'Customer123!'
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith', 
                'contact_number': '09234567890',
                'email': 'jane@customer.com',
                'address': '456 Oak Avenue',
                'city': 'Quezon City',
                'province': 'Metro Manila',
                'zipcode': '1100',
                'password': 'Customer123!'
            },
            {
                'first_name': 'Mike',
                'last_name': 'Johnson',
                'contact_number': '09345678901', 
                'email': 'mike@customer.com',
                'address': '789 Pine Street',
                'city': 'Makati',
                'province': 'Metro Manila',
                'zipcode': '1200',
                'password': 'Customer123!'
            }
        ]
        
        created_count = 0
        for customer_data in customers:
            if not User.objects.filter(email=customer_data['email']).exists():
                user = User.objects.create(
                    first_name=customer_data['first_name'],
                    last_name=customer_data['last_name'],
                    contact_number=customer_data['contact_number'],
                    email=customer_data['email'],
                    address=customer_data['address'],
                    city=customer_data['city'],
                    province=customer_data['province'],
                    zipcode=customer_data['zipcode'],
                    password=customer_data['password'],
                    status='verified',
                    access='enabled',
                    role='user'
                )
                self.stdout.write(f'✅ Created: {user.first_name} {user.last_name} ({user.email})')
                created_count += 1
            else:
                self.stdout.write(f'⚠️ Already exists: {customer_data["email"]}')
        
        self.stdout.write(f'\n🎉 Created {created_count} new customers!')
        
        # List all customers
        all_customers = User.objects.all()
        self.stdout.write(f'\n📋 Total customers: {all_customers.count()}')
        for customer in all_customers:
            self.stdout.write(f'- {customer.first_name} {customer.last_name} ({customer.email})')
