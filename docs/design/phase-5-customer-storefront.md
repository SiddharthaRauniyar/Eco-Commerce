# Phase 5 — Customer Website Pages

## Delivered pages

| Route | Page | Behaviour |
| --- | --- | --- |
| `/` | Homepage | Hero, featured products, categories, promotional/editorial feature, trending products, new arrivals, best sellers, testimonial statement, journal preview, and account-led newsletter invitation. |
| `/shop/` | Catalog | Public active products only; search by name, description, or SKU; category filter; newest, name, and price sorting; pagination. |
| `/shop/category/<slug>/` | Category catalog | Stable, shareable category URL that applies the same catalog controls. |
| `/shop/<slug>/` | Product detail | Product description, gallery-safe primary-media presentation, variations, specifications, category breadcrumb, and related products. |

The storefront deliberately does not expose drafts, archived products, inactive
categories, cart buttons, checkout, payment controls, review submission, or
wishlists. Those require their respective service workflows and are implemented
in later phases rather than producing misleading UI now.

## Public query design

`apps/products/selectors.py` contains the one public catalog query used by
catalog pages and product detail. It selects the category and prefetches the
gallery, variants, and attributes required by the templates, preventing
per-product relationship queries in the grid.

Homepage sections reuse active catalog data:

- **Featured:** products flagged by catalog staff.
- **Trending:** most recently updated active products; this is an explicit
  initial definition until analytics data exists.
- **New arrivals:** most recently created active products.
- **Best sellers:** delivered-order line quantities only, with newer products
  first when sales quantities are tied.

## Interface additions

The Phase 4 design system now includes storefront composition, product cards,
category cards, editorial and newsletter bands, a responsive catalog control
bar, pagination, breadcrumbs, and product-detail specification lists. It stays
server-rendered and fast: product media uses native `loading="lazy"`, while
filtering and sorting use native GET controls so catalog URLs are shareable and
work without JavaScript.

Keyboard focus, semantic headings, image alt text, responsive grids, and
reduced-motion settings are inherited from the shared design system.

## Verification

The test suite now contains ten passing tests. Phase 5 adds coverage that:

- the homepage only shows active catalog products;
- catalog search hides drafts;
- category URLs scope catalog results correctly; and
- active product detail pages render public product information.

The Django system check, migration-drift check, Python compilation, and Git
whitespace checks also pass.

## Deferred to the appropriate phase

- Cart and save-for-later: Phase 7
- Wishlist: Phase 7
- Review submission/moderation pages: Phase 9 and Phase 10
- Newsletter subscription delivery: customer engagement implementation
- Live chat and push notifications: customer engagement implementation
- Product recommendation scoring and analytics-driven trends: Phase 11
