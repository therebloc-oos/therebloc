from django.core.management.base import BaseCommand
from MSMEOrderingWebApp.models import User

class Command(BaseCommand):
    help = 'Create customer accounts for testing'

    def handle(self, *args, **options):
        # Create customer accounts
        customers = [
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'contact_number': '09123456789',
                'email': 'customer@example.com',
                'address': '123 Main Street',
                'city': 'Manila',
                'province': 'Metro Manila',
                'zipcode': '1000',
                'password': 'Customer123!',
            },
            {
                'first_name': 'Jane',
                'last_name': 'Smith',
                'contact_number': '09234567890',
                'email': 'jane.smith@example.com',
                'address': '456 Oak Avenue',
                'city': 'Quezon City',
                'province': 'Metro Manila',
                'zipcode': '1100',
                'password': 'Jane123!',
            },
            {
                'first_name': 'Mike',
                'last_name': 'Johnson',
                'contact_number': '09345678901',
                'email': 'mike.johnson@example.com',
                'address': '789 Pine Street',
                'city': 'Makati',
                'province': 'Metro Manila',
                'zipcode': '1200',
                'password': 'Mike123!',
            },
            {
                'first_name': 'Sarah',
                'last_name': 'Wilson',
                'contact_number': '09456789012',
                'email': 'sarah.wilson@example.com',
                'address': '321 Elm Street',
                'city': 'Pasig',
                'province': 'Metro Manila',
                'zipcode': '1600',
                'password': 'Sarah123!',
            },
            {
                'first_name': 'David',
                'last_name': 'Brown',
                'contact_number': '09567890123',
                'email': 'david.brown@example.com',
                'address': '654 Maple Drive',
                'city': 'Taguig',
                'province': 'Metro Manila',
                'zipcode': '1630',
                'password': 'David123!',
            }
        ]

        created_count = 0
        for customer_data in customers:
            # Check if user already exists
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
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created customer: {user.first_name} {user.last_name} ({user.email})')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Customer already exists: {customer_data["email"]}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Successfully created {created_count} customer accounts!')
        )

        # List all customers
        self.stdout.write('\n📋 All Customer Accounts:')
        self.stdout.write('=' * 60)
        
        for i, user in enumerate(User.objects.all(), 1):
            self.stdout.write(f'\n{i}. {user.first_name} {user.last_name}')
            self.stdout.write(f'   Email: {user.email}')
            self.stdout.write(f'   Password: {user.password}')
            self.stdout.write(f'   Status: {user.status}')
            self.stdout.write('-' * 40)
