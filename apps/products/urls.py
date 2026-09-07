"""Public customer catalog routes."""

from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("", views.CatalogView.as_view(), name="catalog"),
    path("category/<slug:slug>/", views.CategoryCatalogView.as_view(), name="category"),
    path("<slug:slug>/", views.ProductDetailView.as_view(), name="detail"),
]
