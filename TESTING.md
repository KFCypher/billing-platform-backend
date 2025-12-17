# Testing Guide

## Test Setup Complete! ✅

Your billing platform now has a comprehensive test suite covering:

### **Test Coverage:**

1. **Widget API Tests** (`widget/tests/test_widget_api.py`)
   - Plan fetching with API key authentication
   - Subscription verification
   - Feature-based access control
   - Checkout session creation

2. **Plan Management Tests** (`tenants/tests/test_plans.py`)
   - Plan CRUD operations
   - Price validation
   - Currency handling (GHS)
   - Serializer output

3. **Subscription Tests** (`tenants/tests/test_subscriptions.py`)
   - Subscription lifecycle
   - Active/expired/trialing states
   - Customer subscription queries

4. **Platform Fee Tests** (`core/tests/test_platform_fees.py`)
   - 15% fee calculation
   - Fee breakdown
   - Currency conversions

---

## **Running Tests**

### **Run All Tests:**
```bash
cd billing-platform-backend
pytest
```

### **Run with Coverage:**
```bash
pytest --cov=. --cov-report=html --cov-report=term-missing
```

### **Run Specific Test File:**
```bash
pytest widget/tests/test_widget_api.py
```

### **Run Specific Test Class:**
```bash
pytest widget/tests/test_widget_api.py::TestSubscriptionVerification
```

### **Run Specific Test:**
```bash
pytest widget/tests/test_widget_api.py::TestSubscriptionVerification::test_verify_active_subscription
```

### **Run with Verbose Output:**
```bash
pytest -v
```

### **Run Tests Matching Pattern:**
```bash
pytest -k "subscription"  # Runs all tests with "subscription" in name
```

### **Using the Test Runner Script:**
```bash
python run_tests.py
python run_tests.py -v
python run_tests.py widget/tests/
```

---

## **Test Fixtures**

Available in `conftest.py`:

- `api_client` - DRF API client
- `test_tenant` - Test tenant with owner user
- `test_plan` - Basic subscription plan (GH₵119.88)
- `test_customer` - Test customer
- `test_subscription` - Active subscription
- `authenticated_client` - Authenticated API client with JWT token

### **Example Usage:**
```python
@pytest.mark.django_db
def test_my_feature(test_tenant, test_plan, authenticated_client):
    # Your test here
    response = authenticated_client.get('/api/v1/plans/')
    assert response.status_code == 200
```

---

## **Test Database**

Tests use a separate test database that is:
- Created automatically
- Reused between test runs (`--reuse-db`)
- Cleaned after each test
- Faster (no migrations with `--nomigrations`)

---

## **Coverage Report**

After running tests with coverage, view the HTML report:
```bash
# Open in browser
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
```

---

## **Writing New Tests**

### **1. Create Test File:**
```python
# app_name/tests/test_my_feature.py
import pytest
from django.urls import reverse

@pytest.mark.django_db
class TestMyFeature:
    def test_something(self, authenticated_client):
        url = reverse('my-endpoint')
        response = authenticated_client.get(url)
        assert response.status_code == 200
```

### **2. Use Fixtures:**
```python
def test_with_fixtures(test_tenant, test_plan, test_customer):
    # Fixtures are automatically available
    assert test_plan.tenant == test_tenant
```

### **3. Mock External APIs:**
```python
from unittest.mock import patch

@patch('requests.post')
def test_paystack_call(mock_post, test_tenant):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {'status': True}
    # Your test here
```

---

## **Common Test Patterns**

### **Test API Endpoint:**
```python
def test_list_plans(authenticated_client):
    url = reverse('tenants:tenantplan-list')
    response = authenticated_client.get(url)
    
    assert response.status_code == 200
    assert 'plans' in response.data
```

### **Test Model Creation:**
```python
def test_create_subscription(test_tenant, test_customer, test_plan):
    subscription = TenantSubscription.objects.create(
        tenant=test_tenant,
        customer=test_customer,
        plan=test_plan,
        status='active'
    )
    assert subscription.status == 'active'
```

### **Test Validation:**
```python
def test_negative_price_rejected(authenticated_client):
    url = reverse('tenants:tenantplan-list')
    data = {'name': 'Test', 'price_cents': -100}
    response = authenticated_client.post(url, data)
    
    assert response.status_code == 400
```

---

## **CI/CD Integration**

Add to your CI pipeline (GitHub Actions, GitLab CI, etc.):

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## **Test Commands Cheat Sheet**

```bash
# Run all tests
pytest

# Fast (no DB recreation)
pytest --reuse-db

# Verbose
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run last failed
pytest --lf

# Coverage
pytest --cov

# Specific app
pytest widget/tests/

# Parallel (faster)
pytest -n auto
```

---

## **Next Steps**

1. **Run the tests:**
   ```bash
   cd billing-platform-backend
   pytest -v
   ```

2. **Check coverage:**
   ```bash
   pytest --cov=. --cov-report=html
   start htmlcov/index.html
   ```

3. **Add more tests** as you build new features

4. **Set up CI/CD** to run tests automatically

---

**Your test suite is ready!** 🎉

Run `pytest` to execute all tests and verify everything works.
