# Mobile Money Setup Guide

## Quick Start

This guide will help you set up MTN Mobile Money payments for your billing platform.

## 1. Environment Variables

Add these to your `.env` file:

```bash
# Mobile Money Configuration
MOMO_CALLBACK_HOST=https://yourdomain.com

# Optional: Default encryption key for API keys
MOMO_ENCRYPTION_KEY=generate-a-secret-key-here
```

## 2. Register for MTN MoMo API

### Sandbox (Testing)

1. **Register at MTN Developer Portal**
   - Visit: https://momodeveloper.mtn.com/
   - Create account
   - Subscribe to Collections API

2. **Get Credentials**
   - Go to Profile → Subscriptions
   - Copy your `Primary Key` (this is your API key)
   - Generate `API User` (sandbox only)

3. **Configure in Platform**
   ```bash
   curl -X POST http://localhost:8000/api/v1/tenants/momo/config \
     -H "Authorization: Bearer YOUR_TENANT_JWT" \
     -H "Content-Type: application/json" \
     -d '{
       "merchant_id": "your-api-user-id",
       "api_key": "your-primary-key",
       "provider": "mtn",
       "sandbox": true,
       "country_code": "GH"
     }'
   ```

### Production

1. **Contact MTN MoMo Sales**
   - Email: momo@mtn.com.gh (Ghana)
   - Request production access
   - Complete KYC documentation

2. **Get Production Credentials**
   - Merchant ID
   - Production API Key

3. **Register Callback URL**
   - URL: `https://yourdomain.com/api/webhooks/momo`
   - Method: POST
   - Content-Type: application/json

4. **Configure in Platform**
   ```bash
   curl -X POST http://localhost:8000/api/v1/tenants/momo/config \
     -H "Authorization: Bearer YOUR_TENANT_JWT" \
     -H "Content-Type: application/json" \
     -d '{
       "merchant_id": "your-production-merchant-id",
       "api_key": "your-production-api-key",
       "provider": "mtn",
       "sandbox": false,
       "country_code": "GH"
     }'
   ```

## 3. Test Your Integration

### Test Configuration

```bash
curl -X POST http://localhost:8000/api/v1/tenants/momo/test \
  -H "Authorization: Bearer YOUR_TENANT_JWT"
```

Expected response:
```json
{
  "success": true,
  "message": "Connection successful",
  "balance": "1000.00",
  "currency": "GHS",
  "provider": "mtn",
  "sandbox": true
}
```

### Test Payment

```bash
# 1. Create a test customer first
curl -X POST http://localhost:8000/api/v1/customers/create/ \
  -H "Authorization: Bearer YOUR_TENANT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "name": "Test Customer",
    "phone": "0244123456"
  }'

# 2. Create a test plan
curl -X POST http://localhost:8000/api/v1/plans/ \
  -H "Authorization: Bearer YOUR_TENANT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Plan",
    "price_cents": 5000,
    "currency": "GHS",
    "interval": "month",
    "is_active": true
  }'

# 3. Initiate payment
curl -X POST http://localhost:8000/api/v1/payments/momo/initiate \
  -H "X-API-Key: YOUR_TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "plan_id": 1,
    "phone_number": "0244123456",
    "currency": "GHS"
  }'

# 4. Check payment status
curl -X GET http://localhost:8000/api/v1/payments/momo/1/status \
  -H "X-API-Key: YOUR_TENANT_API_KEY"
```

## 4. Frontend Integration

### React Example

```jsx
import React, { useState } from 'react';
import { apiClient } from './lib/api-client';

function MoMoPayment({ customerId, planId, amount }) {
  const [loading, setLoading] = useState(false);
  const [paymentId, setPaymentId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [phoneNumber, setPhoneNumber] = useState('');

  const initiatePayment = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/payments/momo/initiate', {
        customer_id: customerId,
        plan_id: planId,
        phone_number: phoneNumber
      });

      const { payment_id, instructions } = response.data;
      setPaymentId(payment_id);
      setStatus('pending');
      alert(instructions);

      // Start polling
      pollPaymentStatus(payment_id);
    } catch (error) {
      console.error('Payment initiation failed:', error);
      alert('Failed to initiate payment');
    } finally {
      setLoading(false);
    }
  };

  const pollPaymentStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const response = await apiClient.get(`/payments/momo/${id}/status`);
        const { status: paymentStatus } = response.data;

        if (paymentStatus === 'succeeded') {
          setStatus('succeeded');
          clearInterval(interval);
          alert('Payment successful!');
          window.location.href = '/dashboard';
        } else if (paymentStatus === 'failed') {
          setStatus('failed');
          clearInterval(interval);
          alert('Payment failed');
        }
      } catch (error) {
        console.error('Status check failed:', error);
      }
    }, 5000);

    // Stop polling after 5 minutes
    setTimeout(() => clearInterval(interval), 300000);
  };

  return (
    <div className="momo-payment">
      <h3>Pay with Mobile Money</h3>
      <p>Amount: GHS {amount}</p>
      
      <input
        type="tel"
        value={phoneNumber}
        onChange={(e) => setPhoneNumber(e.target.value)}
        placeholder="Phone number (e.g., 0244123456)"
        disabled={loading || status === 'pending'}
      />

      <button
        onClick={initiatePayment}
        disabled={loading || status === 'pending' || !phoneNumber}
      >
        {loading ? 'Processing...' : status === 'pending' ? 'Waiting for approval...' : 'Pay Now'}
      </button>

      {status === 'pending' && (
        <div className="alert alert-info">
          <p>Please check your phone for the payment prompt.</p>
          <p>Enter your Mobile Money PIN to complete the payment.</p>
        </div>
      )}

      {status === 'succeeded' && (
        <div className="alert alert-success">
          Payment successful! Redirecting...
        </div>
      )}

      {status === 'failed' && (
        <div className="alert alert-danger">
          Payment failed. Please try again.
        </div>
      )}
    </div>
  );
}

export default MoMoPayment;
```

### Webhook Listener (Optional)

Instead of polling, listen for webhook events:

```jsx
import { useEffect } from 'react';
import { io } from 'socket.io-client';

function usePaymentWebhook(paymentId, onSuccess, onFailure) {
  useEffect(() => {
    if (!paymentId) return;

    // Connect to your WebSocket server
    const socket = io('wss://your-websocket-server.com', {
      query: { payment_id: paymentId }
    });

    socket.on('payment.succeeded', (data) => {
      if (data.payment_id === paymentId) {
        onSuccess(data);
      }
    });

    socket.on('payment.failed', (data) => {
      if (data.payment_id === paymentId) {
        onFailure(data);
      }
    });

    return () => socket.disconnect();
  }, [paymentId, onSuccess, onFailure]);
}
```

## 5. Webhook Handling

Your backend needs to handle webhook events from the platform:

```python
# tenant_app/webhooks.py
import hmac
import hashlib
from flask import request, jsonify

@app.route('/webhooks', methods=['POST'])
def handle_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    body = request.get_data()
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return jsonify({'error': 'Invalid signature'}), 403
    
    # Parse event
    event = request.json
    event_type = event.get('event_type')
    data = event.get('data')
    
    if event_type == 'payment.succeeded':
        # Update subscription in your database
        payment_id = data['payment_id']
        customer_id = data['customer_id']
        subscription_id = data['subscription_id']
        
        # Your business logic here
        activate_user_subscription(customer_id, subscription_id)
        send_confirmation_email(customer_id)
        
        return jsonify({'success': True}), 200
    
    elif event_type == 'payment.failed':
        # Handle failed payment
        customer_id = data['customer_id']
        failure_message = data['failure_message']
        
        # Notify customer
        send_payment_failed_email(customer_id, failure_message)
        
        return jsonify({'success': True}), 200
    
    return jsonify({'error': 'Unknown event type'}), 400
```

## 6. Common Issues

### Issue: "MOMO_NOT_ENABLED"

**Solution:** Configure MoMo credentials first:
```bash
POST /api/v1/tenants/momo/config
```

### Issue: "INVALID_PHONE_NUMBER"

**Solution:** Use correct format:
- ✅ `0244123456` (local format)
- ✅ `233244123456` (international)
- ❌ `+233244123456` (with +)
- ❌ `244123456` (missing leading 0 or country code)

### Issue: Payment stuck in "pending"

**Causes:**
1. Customer hasn't approved on phone
2. Callback not configured
3. Network issues

**Solution:**
- Ask customer to check their phone
- Verify callback URL is registered
- Check platform logs for callback receipt

### Issue: "INVALID_CREDENTIALS"

**Solution:**
- Verify API key from MTN portal
- Check merchant ID is correct
- Ensure you're using correct environment (sandbox vs production)

## 7. Production Checklist

Before going live:

- [ ] Obtain production credentials from MTN
- [ ] Update configuration with production keys
- [ ] Set `sandbox: false` in configuration
- [ ] Register production callback URL
- [ ] Test with real phone number
- [ ] Verify callback delivery
- [ ] Check webhook to your app works
- [ ] Enable HTTPS on callback endpoint
- [ ] Set up monitoring and alerts
- [ ] Document customer support process

## 8. Support Contacts

### MTN MoMo Support

**Ghana:**
- Email: momo@mtn.com.gh
- Phone: +233 244 300 000
- Developer Portal: https://momodeveloper.mtn.com/

**Uganda:**
- Email: mobilemoney@mtn.co.ug
- Developer Portal: https://momodeveloper.mtn.co.ug/

### Platform Support

- Documentation: `/MOBILE_MONEY_INTEGRATION.md`
- GitHub Issues: Create an issue
- Email: support@yourplatform.com

---

## Next Steps

1. ✅ Complete setup
2. ✅ Test in sandbox
3. ✅ Integrate frontend
4. ✅ Test end-to-end flow
5. ✅ Apply for production access
6. ✅ Go live!

Happy coding! 🚀
