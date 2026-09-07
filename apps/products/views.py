"""Read-only customer catalog views; purchasing actions arrive in Phase 7."""

from django.http import Http404
from django.views.generic import DetailView, ListView

from apps.cart.forms import AddToCartForm
from apps.categories.models import Category
from apps.products.models import Product
from apps.products.selectors import SORTS, public_products


class CatalogView(ListView):
    template_name = "products/catalog.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        self.query = self.request.GET.get("q", "").strip()
        self.category_slug = self.request.GET.get("category", "").strip()
        self.sort = self.request.GET.get("sort", "newest")
        return public_products(query=self.query, category_slug=self.category_slug, sort=self.sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "categories": Category.objects.filter(is_active=True).order_by("position", "name"),
                "selected_category": self.category_slug,
                "query": self.query,
                "selected_sort": self.sort if self.sort in SORTS else "newest",
            }
        )
        return context


class ProductDetailView(DetailView):
    template_name = "products/detail.html"
    context_object_name = "product"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return public_products(include_variants=True, include_attributes=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context["cart_form"] = AddToCartForm(product)
        context["related_products"] = public_products(category_slug=product.category.slug).exclude(pk=product.pk)[:4]
        return context


class CategoryCatalogView(CatalogView):
    """Stable category URL that reuses the same filtering and pagination page."""

    def get_queryset(self):
        self.query = self.request.GET.get("q", "").strip()
        self.category_slug = self.kwargs["slug"]
        self.sort = self.request.GET.get("sort", "newest")
        if not Category.objects.filter(slug=self.category_slug, is_active=True).exists():
            raise Http404
        return public_products(query=self.query, category_slug=self.category_slug, sort=self.sort)
