# Phase 6 — Product and Inventory Management

## Completed management capabilities

Product and catalog managers use Django admin for the operational surface that
already provides secure authentication, CSRF protection, validation,
permissions, and staff audit integration. This avoids duplicating a second
product CMS before the enterprise dashboard phase.

| Area | Capability |
| --- | --- |
| Categories | Hierarchies, URL slugs, descriptions, position, and public visibility. |
| Products | Category assignment, SKU, price, currency, publication state, featured flag, descriptions, flexible metadata, and reorder level. |
| Media and specification | Inline product image gallery with alt text, product attributes, and variants. |
| Variants | SKU, optional price override, attribute metadata, active state, stock, and reorder level. |
| Inventory | Immutable stock adjustment ledger with reason, optional note, actor, timestamp, and an audit event. |
| Stock health | Product and variant admin lists show stock and reorder levels, with an “at or below reorder level” filter. |

## Inventory rules

Direct edits to `stock_quantity` are read-only in product and variant admin.
Staff add an `InventoryAdjustment` row instead, which calls the transactional
`adjust_inventory` service.

The service:

1. Locks the product or variant row with `select_for_update()`.
2. Rejects zero deltas, conflicting product/variant targets, and any movement
   that would create negative stock.
3. Updates the current stock quantity and creates one immutable adjustment row
   in the same transaction.
4. Writes an `AuditLog` before/after stock record with the staff actor.

Supported adjustment reasons are received stock, correction, damaged/lost,
customer return, order reservation, and reservation release. The final two are
defined now so Phase 7 checkout uses the exact same ledger instead of inventing
a second stock path.

## Administration workflow

1. Create or update a category and product in `/admin/`.
2. Add gallery images, specifications, or variants from the product page.
3. Set the product/variant reorder level.
4. Open **Inventory adjustments**, choose exactly one product or variant,
   enter a non-zero delta and reason, then save.
5. Use the stock-health filter to review low stock. Ledger rows are view-only
   after creation and cannot be deleted from admin.

The role seed from Phase 3 grants `Catalog Manager` the `products.*` and
`categories.*` permissions required for this workflow. Administrators retain
their standard complete access.

## Files added or modified

- `apps/products/models.py` — reorder levels and `InventoryAdjustment`
- `apps/products/services.py` — transactional stock adjustment workflow
- `apps/products/admin.py` — catalog and inventory admin configuration
- `apps/categories/admin.py` — taxonomy admin configuration
- `apps/products/migrations/0002_product_reorder_level_productvariant_reorder_level_and_more.py`
- `apps/products/tests.py` — ledger and stock-protection tests

## Verification

The full test suite runs 13 tests successfully. The three new inventory tests
verify stock receipt/audit creation, rejection of negative stock, and variant
stock movements. Django system checks, migration application, compilation, and
migration-drift checks pass.

## Deferred deliberately

- Stock reservation/release during checkout: Phase 7
- Warehouse locations, purchase orders, suppliers, and multi-warehouse stock:
  add only when the operating model needs them
- Staff dashboard analytics and charts: Phase 10 and Phase 11
