"""
Start Django development server with proper error handling
"""
import os
import sys
import django
from django.core.management import execute_from_command_line

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    print("✅ Django setup successful")
    print("🚀 Starting server on http://localhost:8000")
    execute_from_command_line(['manage.py', 'runserver', '8000', '--noreload'])
except Exception as e:
    print(f"❌ Error starting server: {e}")
    sys.exit(1)
