"""Root URL configuration. Feature routes are added in their implementation phases."""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

admin.site.site_header = "Secure Commerce Operations"
admin.site.site_title = "Secure Commerce Admin"
admin.site.index_title = "Operations overview"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.api.urls")),
    path("operations/", include("apps.admin_dashboard.urls")),
    path("reports/", include("apps.analytics.urls")),
    path("security/assurance/", include("apps.vulnerability_testing.urls")),
    path("security/", include("apps.security.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("cart/", include("apps.cart.urls")),
    path("payments/", include("apps.payments.urls")),
    path("wishlist/", include("apps.wishlist.urls")),
    path("orders/", include("apps.orders.urls")),
    path("shop/", include("apps.products.urls")),
    path("", include("apps.core.urls")),
]

# Django serves uploaded development media only while DEBUG is enabled. Nginx
# takes this responsibility in production so app workers never serve uploads.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
