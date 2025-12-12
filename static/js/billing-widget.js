/**
 * Billing Platform Widget - Embeddable subscription widgets
 * 
 * Usage:
 * 
 * // Initialize
 * BillingWidget.init({
 *   apiKey: 'pk_live_xxx',
 *   apiUrl: 'https://api.yourbilling.com/api/v1/widget'
 * });
 * 
 * // Pricing Table
 * BillingWidget.create({
 *   container: '#pricing',
 *   widget: 'pricing-table',
 *   theme: {
 *     primaryColor: '#4F46E5',
 *     borderRadius: '8px'
 *   },
 *   onSubscribe: (planId) => console.log('Subscribe:', planId)
 * });
 * 
 * // Checkout Button
 * BillingWidget.create({
 *   container: '#checkout-btn',
 *   widget: 'checkout-button',
 *   planId: 123,
 *   customerEmail: 'user@example.com',
 *   successUrl: 'https://yoursite.com/success',
 *   cancelUrl: 'https://yoursite.com/cancel'
 * });
 * 
 * // Customer Portal
 * BillingWidget.create({
 *   container: '#portal',
 *   widget: 'customer-portal',
 *   customerEmail: 'user@example.com'
 * });
 */

(function(window) {
  'use strict';

  // Widget configuration
  let config = {
    apiKey: null,
    apiUrl: 'https://api.yourbilling.com/api/v1/widget',
    debug: false
  };

  // API client
  const api = {
    async get(endpoint, params = {}) {
      const url = new URL(`${config.apiUrl}${endpoint}`);
      url.searchParams.append('api_key', config.apiKey);
      Object.keys(params).forEach(key => {
        url.searchParams.append(key, params[key]);
      });

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
      }

      return response.json();
    },

    async post(endpoint, data = {}) {
      const response = await fetch(`${config.apiUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ ...data, api_key: config.apiKey })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
      }

      return response.json();
    }
  };

  // Utility functions
  const utils = {
    log(...args) {
      if (config.debug) {
        console.log('[BillingWidget]', ...args);
      }
    },

    formatPrice(cents, currency = 'USD') {
      const symbol = currency === 'USD' ? '$' : currency;
      return `${symbol}${(cents / 100).toFixed(2)}`;
    },

    createElement(tag, attrs = {}, children = []) {
      const el = document.createElement(tag);
      Object.keys(attrs).forEach(key => {
        if (key === 'className') {
          el.className = attrs[key];
        } else if (key === 'style' && typeof attrs[key] === 'object') {
          Object.assign(el.style, attrs[key]);
        } else if (key.startsWith('on')) {
          el.addEventListener(key.substring(2).toLowerCase(), attrs[key]);
        } else {
          el.setAttribute(key, attrs[key]);
        }
      });
      children.forEach(child => {
        if (typeof child === 'string') {
          el.appendChild(document.createTextNode(child));
        } else if (child) {
          el.appendChild(child);
        }
      });
      return el;
    },

    injectStyles(css) {
      const style = document.createElement('style');
      style.textContent = css;
      document.head.appendChild(style);
    }
  };

  // Inject default styles
  utils.injectStyles(`
    .billing-widget {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
      line-height: 1.5;
      color: #333;
    }
    .billing-widget * {
      box-sizing: border-box;
    }
    .billing-pricing-table {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 24px;
      padding: 24px 0;
    }
    .billing-plan-card {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 32px;
      background: white;
      transition: box-shadow 0.2s, transform 0.2s;
      position: relative;
    }
    .billing-plan-card:hover {
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
      transform: translateY(-2px);
    }
    .billing-plan-featured {
      border-color: var(--primary-color, #4F46E5);
      border-width: 2px;
    }
    .billing-plan-badge {
      position: absolute;
      top: -12px;
      left: 50%;
      transform: translateX(-50%);
      background: var(--primary-color, #4F46E5);
      color: white;
      padding: 4px 16px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .billing-plan-name {
      font-size: 24px;
      font-weight: 700;
      margin: 0 0 8px 0;
    }
    .billing-plan-description {
      color: #6b7280;
      margin: 0 0 24px 0;
      font-size: 14px;
    }
    .billing-plan-price {
      font-size: 48px;
      font-weight: 700;
      margin: 0 0 4px 0;
      color: var(--primary-color, #4F46E5);
    }
    .billing-plan-interval {
      color: #6b7280;
      margin: 0 0 24px 0;
      font-size: 14px;
    }
    .billing-plan-features {
      list-style: none;
      padding: 0;
      margin: 0 0 32px 0;
    }
    .billing-plan-feature {
      padding: 12px 0;
      border-bottom: 1px solid #f3f4f6;
      font-size: 14px;
    }
    .billing-plan-feature:last-child {
      border-bottom: none;
    }
    .billing-btn {
      width: 100%;
      padding: 12px 24px;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .billing-btn-primary {
      background: var(--primary-color, #4F46E5);
      color: white;
    }
    .billing-btn-primary:hover {
      opacity: 0.9;
      transform: translateY(-1px);
    }
    .billing-btn-secondary {
      background: white;
      color: var(--primary-color, #4F46E5);
      border: 2px solid var(--primary-color, #4F46E5);
    }
    .billing-btn-secondary:hover {
      background: #f9fafb;
    }
    .billing-loading {
      text-align: center;
      padding: 48px 24px;
      color: #6b7280;
    }
    .billing-error {
      background: #fef2f2;
      border: 1px solid #fca5a5;
      border-radius: 8px;
      padding: 16px;
      color: #b91c1c;
      margin: 16px 0;
    }
    .billing-portal {
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 32px;
      max-width: 600px;
    }
    .billing-portal-header {
      margin: 0 0 24px 0;
    }
    .billing-portal-title {
      font-size: 24px;
      font-weight: 700;
      margin: 0 0 8px 0;
    }
    .billing-portal-subtitle {
      color: #6b7280;
      margin: 0;
      font-size: 14px;
    }
    .billing-subscription-card {
      background: #f9fafb;
      border-radius: 8px;
      padding: 24px;
      margin: 24px 0;
    }
    .billing-subscription-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .billing-subscription-plan {
      font-size: 18px;
      font-weight: 600;
    }
    .billing-subscription-status {
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
    }
    .billing-status-active {
      background: #d1fae5;
      color: #065f46;
    }
    .billing-status-trialing {
      background: #dbeafe;
      color: #1e40af;
    }
    .billing-subscription-details {
      margin: 16px 0;
      font-size: 14px;
      color: #6b7280;
    }
    .billing-portal-actions {
      display: flex;
      gap: 12px;
      margin-top: 24px;
    }
  `);

  // Widget creators
  const widgets = {
    /**
     * Create pricing table widget
     */
    async pricingTable(container, options = {}) {
      const wrapper = utils.createElement('div', { className: 'billing-widget' });
      container.appendChild(wrapper);

      // Apply custom theme
      if (options.theme) {
        Object.keys(options.theme).forEach(key => {
          const cssVar = `--${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
          wrapper.style.setProperty(cssVar, options.theme[key]);
        });
      }

      // Show loading
      wrapper.innerHTML = '<div class="billing-loading">Loading pricing...</div>';

      try {
        // Fetch plans
        const data = await api.get('/plans');
        utils.log('Plans loaded:', data);

        // Clear loading
        wrapper.innerHTML = '';

        // Create pricing grid
        const grid = utils.createElement('div', { className: 'billing-pricing-table' });

        data.plans.forEach(plan => {
          const card = utils.createElement('div', {
            className: `billing-plan-card ${plan.is_featured ? 'billing-plan-featured' : ''}`
          });

          // Featured badge
          if (plan.is_featured) {
            card.appendChild(
              utils.createElement('div', { className: 'billing-plan-badge' }, ['Most Popular'])
            );
          }

          // Plan name
          card.appendChild(
            utils.createElement('h3', { className: 'billing-plan-name' }, [plan.name])
          );

          // Description
          if (plan.description) {
            card.appendChild(
              utils.createElement('p', { className: 'billing-plan-description' }, [plan.description])
            );
          }

          // Price
          card.appendChild(
            utils.createElement('div', { className: 'billing-plan-price' }, [
              utils.formatPrice(plan.price_cents, plan.currency)
            ])
          );

          // Billing interval
          card.appendChild(
            utils.createElement('div', { className: 'billing-plan-interval' }, [
              `per ${plan.billing_interval}`
            ])
          );

          // Features
          if (plan.features && plan.features.length > 0) {
            const featuresList = utils.createElement('ul', { className: 'billing-plan-features' });
            plan.features.forEach(feature => {
              featuresList.appendChild(
                utils.createElement('li', { className: 'billing-plan-feature' }, [feature])
              );
            });
            card.appendChild(featuresList);
          }

          // Subscribe button
          const button = utils.createElement('button', {
            className: `billing-btn ${plan.is_featured ? 'billing-btn-primary' : 'billing-btn-secondary'}`,
            onClick: () => {
              if (options.onSubscribe) {
                options.onSubscribe(plan.id, plan);
              }
            }
          }, [plan.trial_days > 0 ? `Start ${plan.trial_days}-Day Trial` : 'Subscribe']);

          card.appendChild(button);
          grid.appendChild(card);
        });

        wrapper.appendChild(grid);

      } catch (error) {
        utils.log('Error loading plans:', error);
        wrapper.innerHTML = `<div class="billing-error">Failed to load pricing: ${error.message}</div>`;
      }
    },

    /**
     * Create checkout button widget
     */
    async checkoutButton(container, options = {}) {
      const {
        planId,
        customerEmail,
        customerName,
        customerPhone,
        successUrl,
        cancelUrl,
        paymentProvider = 'stripe',
        buttonText = 'Subscribe Now',
        metadata = {}
      } = options;

      if (!planId || !customerEmail || !successUrl || !cancelUrl) {
        container.innerHTML = '<div class="billing-error">Missing required options: planId, customerEmail, successUrl, cancelUrl</div>';
        return;
      }

      const wrapper = utils.createElement('div', { className: 'billing-widget' });
      const button = utils.createElement('button', {
        className: 'billing-btn billing-btn-primary',
        onClick: async () => {
          button.disabled = true;
          button.textContent = 'Creating checkout...';

          try {
            const data = await api.post('/checkout-session', {
              plan_id: planId,
              customer_email: customerEmail,
              customer_name: customerName,
              customer_phone: customerPhone,
              success_url: successUrl,
              cancel_url: cancelUrl,
              payment_provider: paymentProvider,
              metadata: metadata
            });

            utils.log('Checkout session created:', data);

            // Redirect to checkout
            window.location.href = data.checkout_url;

          } catch (error) {
            utils.log('Error creating checkout:', error);
            button.disabled = false;
            button.textContent = buttonText;
            
            const errorDiv = utils.createElement('div', {
              className: 'billing-error'
            }, [`Checkout failed: ${error.message}`]);
            wrapper.appendChild(errorDiv);

            setTimeout(() => errorDiv.remove(), 5000);
          }
        }
      }, [buttonText]);

      wrapper.appendChild(button);
      container.appendChild(wrapper);
    },

    /**
     * Create customer portal widget
     */
    async customerPortal(container, options = {}) {
      const { customerEmail } = options;

      if (!customerEmail) {
        container.innerHTML = '<div class="billing-error">Missing required option: customerEmail</div>';
        return;
      }

      const wrapper = utils.createElement('div', { className: 'billing-widget' });
      container.appendChild(wrapper);

      // Show loading
      wrapper.innerHTML = '<div class="billing-loading">Loading subscription...</div>';

      try {
        const data = await api.get('/customer/subscription', { customer_email: customerEmail });
        utils.log('Subscription loaded:', data);

        wrapper.innerHTML = '';

        const portal = utils.createElement('div', { className: 'billing-portal' });

        // Header
        const header = utils.createElement('div', { className: 'billing-portal-header' });
        header.appendChild(
          utils.createElement('h2', { className: 'billing-portal-title' }, ['My Subscription'])
        );
        header.appendChild(
          utils.createElement('p', { className: 'billing-portal-subtitle' }, [
            `${data.customer.name || data.customer.email}`
          ])
        );
        portal.appendChild(header);

        if (data.has_subscription) {
          const sub = data.subscription;

          // Subscription card
          const card = utils.createElement('div', { className: 'billing-subscription-card' });

          // Header with plan and status
          const cardHeader = utils.createElement('div', { className: 'billing-subscription-header' });
          cardHeader.appendChild(
            utils.createElement('div', { className: 'billing-subscription-plan' }, [sub.plan.name])
          );
          cardHeader.appendChild(
            utils.createElement('span', {
              className: `billing-subscription-status billing-status-${sub.status}`
            }, [sub.status])
          );
          card.appendChild(cardHeader);

          // Details
          const details = utils.createElement('div', { className: 'billing-subscription-details' });
          details.innerHTML = `
            <div><strong>Price:</strong> ${utils.formatPrice(sub.plan.price * 100)} / ${sub.plan.billing_interval}</div>
            ${sub.current_period_end ? `<div><strong>Next billing:</strong> ${new Date(sub.current_period_end).toLocaleDateString()}</div>` : ''}
            ${sub.cancel_at_period_end ? '<div style="color: #dc2626;"><strong>Cancels at period end</strong></div>' : ''}
          `;
          card.appendChild(details);

          portal.appendChild(card);

          // Actions
          if (!sub.cancel_at_period_end) {
            const actions = utils.createElement('div', { className: 'billing-portal-actions' });

            // Cancel button
            const cancelBtn = utils.createElement('button', {
              className: 'billing-btn billing-btn-secondary',
              onClick: async () => {
                if (!confirm('Are you sure you want to cancel your subscription?')) return;

                cancelBtn.disabled = true;
                cancelBtn.textContent = 'Canceling...';

                try {
                  await api.post('/customer/subscription/cancel', {
                    customer_email: customerEmail,
                    immediate: false
                  });

                  alert('Your subscription will be canceled at the end of the billing period.');
                  location.reload();
                } catch (error) {
                  alert(`Failed to cancel: ${error.message}`);
                  cancelBtn.disabled = false;
                  cancelBtn.textContent = 'Cancel Subscription';
                }
              }
            }, ['Cancel Subscription']);

            actions.appendChild(cancelBtn);
            portal.appendChild(actions);
          }

        } else {
          portal.innerHTML += '<p>No active subscription found.</p>';
        }

        wrapper.appendChild(portal);

      } catch (error) {
        utils.log('Error loading portal:', error);
        wrapper.innerHTML = `<div class="billing-error">Failed to load subscription: ${error.message}</div>`;
      }
    }
  };

  // Main BillingWidget object
  window.BillingWidget = {
    /**
     * Initialize the widget library
     */
    init(options = {}) {
      if (!options.apiKey) {
        throw new Error('BillingWidget: apiKey is required');
      }

      config.apiKey = options.apiKey;
      if (options.apiUrl) config.apiUrl = options.apiUrl;
      if (options.debug) config.debug = options.debug;

      utils.log('Initialized with config:', config);
    },

    /**
     * Create a widget
     */
    async create(options = {}) {
      const { container, widget } = options;

      if (!container) {
        throw new Error('BillingWidget: container is required');
      }
      if (!widget) {
        throw new Error('BillingWidget: widget type is required');
      }
      if (!config.apiKey) {
        throw new Error('BillingWidget: Must call init() first');
      }

      const el = typeof container === 'string' 
        ? document.querySelector(container)
        : container;

      if (!el) {
        throw new Error(`BillingWidget: Container not found: ${container}`);
      }

      // Create widget based on type
      switch (widget) {
        case 'pricing-table':
          return widgets.pricingTable(el, options);
        case 'checkout-button':
          return widgets.checkoutButton(el, options);
        case 'customer-portal':
          return widgets.customerPortal(el, options);
        default:
          throw new Error(`BillingWidget: Unknown widget type: ${widget}`);
      }
    }
  };

})(window);
