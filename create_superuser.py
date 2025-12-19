#!/usr/bin/env python
"""
Create a superuser for production deployment.
Run this script once after deployment to create an admin user.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Change these values to your desired admin credentials
username = 'kelvin'
#email = 'admin@billingplatform.com'
password = 'Admin123@#'  # Change this to a strong password

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'✅ Superuser "{username}" created successfully!')
else:
    print(f'⚠️ Superuser "{username}" already exists.')
