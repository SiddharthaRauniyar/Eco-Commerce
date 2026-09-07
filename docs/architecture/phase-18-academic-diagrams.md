# Phase 18 — Academic Diagrams

These diagrams describe the implemented modular Django monolith. Mermaid-capable
Markdown renderers can display them directly. The Gantt view is a delivery
sequence template, not a record of elapsed project time.

## Use-case diagram

```mermaid
flowchart LR
    guest[Guest] --> browse[Browse catalog and search]
    guest --> register[Register and verify email]
    customer[Customer] --> browse
    customer --> cart[Manage cart, coupon, and checkout]
    customer --> account[Manage profile, addresses, MFA, wishlist]
    customer --> orders[View, cancel, return, reorder, and download invoice]
    staff[Staff member] --> operations[Manage catalog, inventory, orders, reviews, and support]
    staff --> reports[View authorized reports and exports]
    analyst[Security analyst] --> monitoring[Review and resolve security events]
    analyst --> assurance[Run safe defensive-control checks]
    provider[Payment provider] --> webhook[Send verified payment webhook]
    webhook --> payments[Update payment and order state]
```

## Representative class diagram

The full database relationship map is the [Phase 2 ER diagram](phase-2-database-design.md#entity-relationship-diagram).

```mermaid
classDiagram
    class CustomUser
    class UserProfile
    class Address
    class Category
    class Product
    class ProductVariant
    class Cart
    class CartItem
    class Order
    class OrderItem
    class Payment
    class Coupon
    class SecurityEvent
    class AuditLog

    CustomUser "1" --> "0..1" UserProfile
    CustomUser "1" --> "0..*" Address
    CustomUser "1" --> "0..*" Cart
    CustomUser "1" --> "0..*" Order
    Category "1" --> "0..*" Product
    Product "1" --> "0..*" ProductVariant
    Cart "1" --> "0..*" CartItem
    CartItem "*" --> "1" Product
    Order "1" --> "0..*" OrderItem
    OrderItem "*" --> "1" Product
    Order "1" --> "0..*" Payment
    Coupon "0..1" --> "0..*" Order
    CustomUser "0..1" --> "0..*" SecurityEvent
    CustomUser "0..1" --> "0..*" AuditLog
```

## Checkout sequence diagram

```mermaid
sequenceDiagram
    actor Customer
    participant Web as Django storefront
    participant Cart as Cart service
    participant DB as PostgreSQL
    participant Payment as Payment provider

    Customer->>Web: Submit checkout with idempotency token
    Web->>Cart: Validate cart, coupon, address, shipping
    Cart->>DB: Lock cart and inventory rows
    DB-->>Cart: Reserved stock and pending order
    alt Cash on delivery
        Cart-->>Web: Confirm order
    else Online payment
        Cart->>Payment: Create provider checkout
        Payment-->>Customer: Hosted payment page
        Payment->>Web: Signed webhook
        Web->>DB: Verify, lock, and complete payment once
    end
    Web-->>Customer: Confirmation and invoice access
```

## Checkout activity diagram

```mermaid
flowchart TD
    start([Start]) --> cart{Active cart has items?}
    cart -- No --> correct[Show cart guidance]
    cart -- Yes --> validate[Validate address, shipping, coupon, and stock]
    validate --> valid{Valid?}
    valid -- No --> correct
    valid -- Yes --> reserve[Create idempotent order and reserve inventory]
    reserve --> method{Payment method}
    method -- COD --> confirm[Mark order confirmed]
    method -- Stripe / PayPal --> pending[Create pending payment]
    pending --> webhook{Verified paid webhook?}
    webhook -- Yes --> paid[Mark payment and order paid]
    webhook -- No / expired --> release[Release inventory and reopen cart]
    confirm --> finish([Confirmation])
    paid --> finish
    release --> correct
```

## Database ownership diagram

```mermaid
flowchart TB
    identity[Identity: users, profiles, addresses]
    catalog[Catalog: categories, products, variants, images]
    commerce[Commerce: carts, coupons, orders, order items, payments]
    engagement[Engagement: reviews, notifications, support, blog]
    security[Security: login attempts, activity, audit, events, assurance reports]

    identity --> commerce
    catalog --> commerce
    commerce --> engagement
    identity --> security
    commerce --> security
```

## Gantt-style delivery sequence

```mermaid
gantt
    title Secure Commerce delivery sequence (planning template)
    dateFormat  YYYY-MM-DD
    axisFormat  %b
    section Foundation
    Architecture and database             :done, p1, 2026-01-01, 2d
    Authentication and design system      :done, p2, after p1, 2d
    section Commerce
    Storefront through order management   :done, p3, after p2, 5d
    Operations and analytics              :done, p4, after p3, 2d
    section Assurance
    Security through API                  :done, p5, after p4, 5d
    Performance and deployment            :done, p6, after p5, 2d
    Testing and documentation             :done, p7, after p6, 1d
```
