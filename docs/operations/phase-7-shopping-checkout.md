# Phase 7 — Shopping, Checkout, and Customer Lists

## Completed customer flows

| Flow | Route | Behaviour |
| --- | --- | --- |
| Cart | `/cart/` | Anonymous and account carts, quantity updates, removal, save-for-later, server-side prices and totals. |
| Add to cart | `/cart/add/<product-id>/` | Requires an active product, validates an active variant where needed, and never accepts a client-supplied price. |
| Coupon | `/cart/coupon/` | Validates code, active period, minimum order, global usage, and per-user usage before attaching it to the cart. |
| Wishlist | `/wishlist/` | Authenticated-only saved product list; guests are directed to sign in. |
| Checkout | `/cart/checkout/` | Guest or signed-in cash-on-delivery checkout with address snapshots, standard/express shipping, configurable tax, stock reservation, and order confirmation. |
| Confirmation | `/orders/confirmation/<order-number>/` | Available only to the order owner or the guest checkout session that created the order. |

## Cart and pricing rules

- A cart holds one currency. The first product sets the currency; a different
  currency is rejected instead of silently producing invalid totals.
- Cart prices are always calculated from `Product.base_price` or an active
  `ProductVariant.price_override` on the server.
- A cart does not reserve inventory. Add/update validates currently available
  stock; final checkout reserves it atomically.
- Saved-for-later lines are kept out of coupon eligibility, totals, and
  checkout.
- Fixed coupons use the store currency. Percentage coupons work independently
  of the currency. Multi-currency conversion rules are deferred until the
  business enables multi-currency sales.

## Checkout behaviour

The implemented payment method is **cash on delivery**. It completes the
shopping and checkout flow without fabricating a card processor. Stripe and
PayPal provider authorization/webhooks are Phase 8 work.

On a successful checkout, one transaction:

1. locks the active cart and cart lines;
2. recalculates the cart, coupon, shipping, and tax totals server-side;
3. creates immutable product, price, and shipping/billing snapshots on an
   `Order`;
4. reserves each item through the Phase 6 `InventoryAdjustment` ledger;
5. creates a pending cash-on-delivery `Payment` record;
6. marks the cart inactive and exposes the confirmation only to its rightful
   customer or guest session.

The checkout token is stored in the session and is used as the unique payment
idempotency key. A repeated service call with the same key returns the existing
order instead of creating another charge, order, or stock reservation.

`CHECKOUT_TAX_RATE` defaults to `0.00` and is read from the deployment
environment. Set a jurisdictionally reviewed decimal rate in the production
environment; tax engine integrations are not guessed in application code.

## Files created or modified

- `apps/cart/models.py` and migration `0002_cart_coupon.py`
- `apps/cart/services.py`, `forms.py`, `views.py`, `urls.py`, and tests
- `apps/wishlist/urls.py`
- `apps/orders/views.py` and `urls.py`
- product detail, base navigation, cart, wishlist, checkout, and order
  confirmation templates
- `config/settings/base.py` and `config/urls.py`
- `static/css/app.css`

## Verification

The test suite now contains 17 passing tests. New Phase 7 checks cover:

- cart quantity and coupon total calculation;
- guest cash-on-delivery checkout, order/payment creation, and stock ledger
  reservation;
- checkout service idempotency;
- guest confirmation authorization;
- wishlist sign-in requirement; and
- checkout-token expiry rejection before an order is created.

Django checks, migration-drift checks, compilation, and whitespace checks are
also run before handoff.

## Deferred to the appropriate phase

- Stripe and PayPal processing, signatures, and webhooks: Phase 8
- Order-history, tracking, cancellation, returns, refunds, and invoices: Phase 9
- Staff order operations: Phase 10
