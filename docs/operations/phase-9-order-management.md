# Phase 9: Order Management

Authenticated customers can view their own order history and details, including the current order status, payment state, delivery carrier, tracking number, immutable address snapshots, and item totals. Other customers receive a 404 rather than another customer's order data.

## Customer actions

- Reorder adds still-active, in-stock items to the current cart at current catalog prices.
- Confirmed and unfulfilled orders can be cancelled once. The reservation is returned to inventory. A paid cancellation automatically records a refund request for staff review.
- Delivered orders can receive one open return request.
- Paid orders in an eligible state can receive one open refund request.
- Invoice downloads are enabled once an order is no longer payment-pending. The first download assigns a stable `INV-YYYYMMDD-NNNNNN` number and renders a PDF from the immutable order snapshots.

Staff can keep the existing Django admin order status, carrier, and tracking fields current. Processing return/refund resolutions and provider refunds belong to the staff dashboard phase, so a customer request does not claim that money was already returned.
