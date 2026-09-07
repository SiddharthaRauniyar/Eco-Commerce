# Phase 10: Admin Dashboard

The staff-only operations overview is available at `/operations/`. It uses the same `is_staff` boundary as Django admin and filters every metric and queue by the viewer's Django permissions.

The dashboard provides a concise current-state view of authorized areas:

- paid revenue, fulfillment, and return/refund queues;
- low product and variant inventory;
- customer count and pending reviews;
- active support tickets; and
- direct links into the existing protected Django admin modules for edits.

The dashboard is deliberately read-only. Django admin remains the management surface for catalog, inventory, orders, reviews, coupons, blog posts, support tickets, and payment records. Charts, historical reporting, and exports belong to Phase 11, where the date ranges and aggregation rules can be implemented without duplicating this operational view.
