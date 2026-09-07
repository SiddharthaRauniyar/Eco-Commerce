# Phase 16 — Performance optimization

## Query and rendering improvements

The public catalog selector now fetches only product images for card-based
pages. Variant and attribute relations are requested only by product detail
views and API serializers that need them. Order history uses a database item
count instead of loading every historical order line, and high-volume admin
changelists select their displayed relations in the original query.

Product cards retain native lazy loading and now use asynchronous image
decoding plus a reserved aspect ratio to reduce layout shift. The detail image
keeps eager loading because it is visible at the top of the product page.

## Redis cache

Set `REDIS_URL` to an ACL/TLS Redis URL in production. When `DJANGO_DEBUG` is
disabled, it is required: Django's built-in Redis cache then backs both the
public API cache and DRF's cross-worker throttles. Development and tests use
Django's local-memory cache without needing a Redis service.

Anonymous, unfiltered `GET` requests for `/api/v1/categories/`, the default
product list, and product detail are cached for `PUBLIC_API_CACHE_SECONDS`
(60 seconds by default). Search and filtered catalog requests are deliberately
not cached, avoiding an unbounded cache-key space. Cache keys include scheme,
host, path, and a catalog version because image URLs are absolute.

Saving or deleting a category, product, product image, variant, or attribute
bumps that version after the database transaction commits. Cache invalidation
does not run for a rolled-back change. Future bulk product updates must call
the same invalidation helper explicitly because Django signals do not fire for
`QuerySet.update()`.

No cache is applied to authentication, customer data, HTML pages with CSRF or
personalized navigation, carts, checkout, payments, staff dashboards, or
security records. Checkout remains database-authoritative even when a cached
catalog page briefly shows an availability state.

## Static assets and SEO

`STATIC_ROOT` and optional manifest-hashed static files are ready for Phase
17's `collectstatic` deployment. Set `DJANGO_USE_MANIFEST_STATICFILES=true`
when the deployment serves the generated manifest. `DJANGO_STATIC_URL` can
point to a CDN origin once its Nginx/CDN cache policy and CSP origin are
configured in the deployment phase.

Public storefront pages now supply descriptions, canonical URLs, and
indexing directives. Account, checkout, staff, and security pages default to
`noindex, nofollow`.

Image transformation, a frontend bundler, whole-page caching, and CDN
delivery are intentionally deferred: the current CSS/JS and sample media are
small, while those additions need production asset and traffic evidence.
