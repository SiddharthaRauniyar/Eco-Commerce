# Phase 2 — Database Design and Django Models

## Scope completed

This phase establishes the complete relational foundation for the platform. It
contains the custom user model, all requested domain models, foreign-key and
many-to-many relationships, database constraints, initial migrations, and one
cross-app schema smoke test. Business workflows, views, API serializers, and
dashboard pages intentionally belong to later phases.

All primary keys use Django's `BigAutoField`. Every domain record inherits
`created_at` and `updated_at` from `TimeStampedModel`, except Django's inherited
authentication fields, which retain their standard behaviour.

## Entity relationship diagram

```mermaid
erDiagram
    CUSTOM_USER ||--|| USER_PROFILE : has
    CUSTOM_USER ||--o{ ADDRESS : owns
    CATEGORY ||--o{ CATEGORY : parents
    CATEGORY ||--o{ PRODUCT : groups
    PRODUCT ||--o{ PRODUCT_IMAGE : has
    PRODUCT ||--o{ PRODUCT_VARIANT : offers
    PRODUCT ||--o{ PRODUCT_ATTRIBUTE : describes
    CUSTOM_USER o|--o{ CART : owns
    CART ||--o{ CART_ITEM : contains
    PRODUCT ||--o{ CART_ITEM : selected
    PRODUCT_VARIANT o|--o{ CART_ITEM : selected
    CUSTOM_USER ||--|| WISHLIST : owns
    WISHLIST }o--o{ PRODUCT : saves
    CUSTOM_USER }o--o{ COUPON : redeems
    CUSTOM_USER o|--o{ ORDER : places
    ADDRESS o|--o{ ORDER : snapshots_from
    COUPON o|--o{ ORDER : applied_to
    ORDER ||--o{ ORDER_ITEM : contains
    PRODUCT o|--o{ ORDER_ITEM : referenced_by
    PRODUCT_VARIANT o|--o{ ORDER_ITEM : referenced_by
    ORDER ||--o{ PAYMENT : has
    CUSTOM_USER ||--o{ REVIEW : writes
    PRODUCT ||--o{ REVIEW : receives
    CUSTOM_USER ||--o{ NOTIFICATION : receives
    CUSTOM_USER ||--o{ SUPPORT_TICKET : opens
    ORDER o|--o{ SUPPORT_TICKET : concerns
    CUSTOM_USER ||--o{ BLOG : authors
    CUSTOM_USER o|--o{ ACTIVITY_LOG : acts_in
    CUSTOM_USER o|--o{ AUDIT_LOG : acts_in
    CUSTOM_USER o|--o{ SECURITY_EVENT : concerns
    CUSTOM_USER o|--o{ LOGIN_ATTEMPT : attempts
    SECURITY_EVENT o|--o{ VULNERABILITY_REPORT : informs
    CUSTOM_USER o|--o{ VULNERABILITY_REPORT : verifies

    CUSTOM_USER {
        bigint id PK
        string email UK
        boolean is_email_verified
        string password
    }
    USER_PROFILE {
        bigint id PK
        bigint user_id FK_UK
        boolean mfa_enabled
        string mfa_secret_encrypted
    }
    ADDRESS {
        bigint id PK
        bigint user_id FK
        string country_code
        boolean is_default_shipping
    }
    CATEGORY {
        bigint id PK
        bigint parent_id FK
        string slug UK
    }
    PRODUCT {
        bigint id PK
        bigint category_id FK
        string sku UK
        decimal base_price
        string status
    }
    PRODUCT_IMAGE {
        bigint id PK
        bigint product_id FK
        string image
    }
    PRODUCT_VARIANT {
        bigint id PK
        bigint product_id FK
        string sku UK
        json attributes
    }
    PRODUCT_ATTRIBUTE {
        bigint id PK
        bigint product_id FK
        string name
        string value
    }
    CART {
        bigint id PK
        bigint user_id FK
        string session_key UK
    }
    CART_ITEM {
        bigint id PK
        bigint cart_id FK
        bigint product_id FK
        bigint variant_id FK
        int quantity
    }
    WISHLIST {
        bigint id PK
        bigint user_id FK_UK
    }
    COUPON {
        bigint id PK
        string code UK
        decimal amount
    }
    ORDER {
        bigint id PK
        string order_number UK
        bigint user_id FK
        bigint coupon_id FK
        decimal grand_total
        string status
    }
    ORDER_ITEM {
        bigint id PK
        bigint order_id FK
        bigint product_id FK
        bigint variant_id FK
        decimal unit_price
    }
    PAYMENT {
        bigint id PK
        bigint order_id FK
        string idempotency_key UK
        string provider
    }
    REVIEW {
        bigint id PK
        bigint product_id FK
        bigint user_id FK
        int rating
    }
    NOTIFICATION {
        bigint id PK
        bigint user_id FK
        string channel
    }
    SUPPORT_TICKET {
        bigint id PK
        bigint requester_id FK
        bigint order_id FK
        string status
    }
    BLOG {
        bigint id PK
        bigint author_id FK
        string slug UK
        string status
    }
    ACTIVITY_LOG {
        bigint id PK
        bigint actor_id FK
        string action
    }
    AUDIT_LOG {
        bigint id PK
        bigint actor_id FK
        string target_type
    }
    SECURITY_EVENT {
        bigint id PK
        bigint user_id FK
        string severity
    }
    LOGIN_ATTEMPT {
        bigint id PK
        bigint user_id FK
        boolean successful
    }
    VULNERABILITY_REPORT {
        bigint id PK
        bigint security_event_id FK
        bigint reported_by_id FK
        string status
    }
```

## Schema by ownership

### Identity and customer data

| Model | Key fields | Relationships and constraints |
| --- | --- | --- |
| `CustomUser` | `email`, names, standard Django password/permission fields, `is_email_verified` | Email is unique and is `USERNAME_FIELD`; one profile; many addresses, carts, orders, reviews, and security records. |
| `UserProfile` | phone, avatar, marketing choices, MFA state and encrypted MFA secret | One-to-one with `CustomUser`. The MFA secret field stores only encrypted application data. |
| `Address` | labelled recipient, address lines, country, phone, default flags | Many addresses per user. Orders can preserve the source address relationship and a JSON checkout snapshot. |

### Catalog and merchandising data

| Model | Key fields | Relationships and constraints |
| --- | --- | --- |
| `Category` | name, unique slug, parent, active flag, position | Self-referential hierarchy. A protected parent prevents accidental deletion of active catalog taxonomy. |
| `Product` | category, unique `slug` and `sku`, descriptions, price, currency, stock, status, metadata | Belongs to one category; has images, variants, attributes, cart lines, order lines, wishlists, and reviews. Indexed by status and category. |
| `ProductImage` | file reference, accessibility alt text, position, primary flag | Many gallery assets per product. Upload validation is implemented at the file-upload boundary in the relevant phase. |
| `ProductVariant` | product, unique SKU, optional price override, stock, JSON attributes | Many purchasable variants per product. |
| `ProductAttribute` | product, name, value, position | The `(product, name)` pair is unique to prevent duplicate specifications. |

### Shopping, discount, and commerce data

| Model | Key fields | Relationships and constraints |
| --- | --- | --- |
| `Cart` | optional user, optional unique session key, currency, active flag | Supports customer and anonymous carts. A service later enforces that an active cart has one owner form. |
| `CartItem` | cart, product, optional variant, quantity, saved-for-later flag | Product lines without a variant are unique per cart; variant lines are unique per cart. Quantity has a minimum validator of one. |
| `Wishlist` | user | One wishlist per user; its many-to-many product relation is stored in Django's join table. |
| `Coupon` | unique code, type, amount, validity window, usage limits, active flag | Many users can redeem a coupon; an order can retain the applied coupon. Redemption counting and eligibility are service responsibilities. |
| `Order` | unique order number, customer or guest email, address references/snapshots, totals, status, tracking, invoice number | Customer is nullable for guest checkout. Coupon and live address links are nullable to preserve order history; JSON snapshots are authoritative for completed orders. Indexed by user/status and guest email/status. |
| `OrderItem` | product/variant reference, product name/SKU snapshot, unit price, quantity, line total | Many immutable commerce-line snapshots per order. Product/variant deletion preserves the line by setting its live reference to null. |
| `Payment` | order, provider, status, amount, external ID, unique idempotency key, provider result metadata | An order can have several attempts. Raw event metadata excludes card numbers, CVVs, and provider secrets. |

### Engagement and publishing data

| Model | Key fields | Relationships and constraints |
| --- | --- | --- |
| `Review` | product, user, one-to-five rating, content, verification/moderation state | One review per product/customer pair. Approval and purchase verification are explicit, not inferred from client input. |
| `Notification` | recipient, channel, title/body, action URL, read/delivered state | Per-user delivery record; indexed for notification-center reads. |
| `SupportTicket` | requester, optional order, optional assignee, subject/message, priority/status | Keeps customer ownership and relevant order context separate from staff assignment. |
| `Blog` | protected author, unique slug, body, status, SEO fields, publish time | A blog author cannot be removed while retaining articles; staff reassigns ownership instead. |

### Security and safe verification data

| Model | Key fields | Relationships and constraints |
| --- | --- | --- |
| `ActivityLog` | optional actor, action, target reference, request and network metadata | Captures account activity, including events whose actor was later removed. |
| `AuditLog` | optional actor, action, target, before/after data, request and IP metadata | Services treat audit records as append-only. The data model keeps prior and subsequent safe field snapshots for privileged changes. |
| `SecurityEvent` | optional user, type, severity, description, IP, evidence, resolution metadata | Indexed for open severity queues and event investigation. |
| `LoginAttempt` | optional known user, supplied email, IP, agent, success/failure reason | Records failed attempts even when no account exists for the supplied email. |
| `VulnerabilityReport` | defensive control, status, summary, recommendation, evidence, verifier, optional security event | Stores only non-exploiting verification outcomes and remediation advice. |

## Data integrity decisions

1. **Money:** all stored monetary values are `DecimalField(max_digits=12,
   decimal_places=2)`. Currency accompanies price and order totals. A future
   multi-currency phase will retain the same columns and add conversion rules,
   not floating-point values.
2. **Order history:** orders copy checkout addresses, product names, SKUs, and
   unit prices. Later catalog changes therefore cannot rewrite historical
   invoices or reports.
3. **Deletion:** customer-owned profiles, addresses, carts, and wishlists
   cascade with the user. Commercial snapshots and audit/security facts use
   `SET_NULL` or `PROTECT` where preservation is required.
4. **Identifiers:** public-facing order numbers, product/category/blog slugs,
   SKUs, coupon codes, invoice numbers, and payment idempotency keys have
   explicit uniqueness guarantees.
5. **Search and performance:** initial indexes cover catalog state, active carts,
   order queues, notification reads, login/security events, ticket queues, and
   publication state. PostgreSQL full-text search indexes are deferred until
   the catalog search phase, when actual query fields and languages are known.
6. **JSON fields:** JSON is limited to provider-safe payment metadata, security
   evidence, flexible product metadata, and immutable address snapshots. Fields
   that require joins, filtering, or integrity constraints remain relational.

## Migration map

Initial migrations were generated for the model-owning apps:

```text
accounts, categories, products, cart, wishlist, coupons, orders, payments,
reviews, notifications, support, security, vulnerability_testing, blog
```

`core` is intentionally migration-free because it supplies only an abstract
timestamp base class. Future apps (`analytics`, `admin_dashboard`, and `api`)
will be created in their implementation phases because they currently own no
database state.

## Phase 2 exit criteria

- Custom user model exists before any initial migration.
- Every model requested in the brief is present and placed in its owning app.
- Entity relationships, unique constraints, deletion policy, and initial
  indexes are documented.
- Initial migrations apply to a clean database.
- A cross-app test proves product-to-order snapshot linkage.
