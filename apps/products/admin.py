"""Django-admin catalog management with an append-only stock ledger."""

from django.contrib import admin
from django.db.models import F
from django.utils.html import format_html

from apps.products.models import InventoryAdjustment, Product, ProductAttribute, ProductImage, ProductVariant
from apps.products.services import adjust_inventory


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ("thumbnail",)
    fields = ("thumbnail", "image", "alt_text", "position", "is_primary")

    @admin.display(description="Preview")
    def thumbnail(self, image):
        if not image or not image.image:
            return "—"
        return format_html('<img src="{}" alt="" class="admin-thumbnail">', image.image.url)


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    readonly_fields = ("stock_quantity",)
    show_change_link = True


class InventoryTargetAdmin(admin.ModelAdmin):
    """Allow exact stock edits while preserving the immutable stock ledger."""

    def save_model(self, request, obj, form, change):
        requested_quantity = obj.stock_quantity
        current_quantity = type(obj).objects.only("stock_quantity").get(pk=obj.pk).stock_quantity if change else 0
        obj.stock_quantity = current_quantity
        super().save_model(request, obj, form, change)
        if requested_quantity != current_quantity:
            adjust_inventory(
                **({"product": obj} if isinstance(obj, Product) else {"variant": obj}),
                delta=requested_quantity - current_quantity,
                reason=InventoryAdjustment.Reason.CORRECTION if change else InventoryAdjustment.Reason.RECEIVED,
                note=f"Set stock to {requested_quantity} in Django admin.",
                actor=request.user,
            )
            obj.stock_quantity = requested_quantity


class LowStockFilter(admin.SimpleListFilter):
    title = "stock health"
    parameter_name = "stock_health"

    def lookups(self, request, model_admin):
        return (("low", "At or below reorder level"), ("available", "Above reorder level"))

    def queryset(self, request, queryset):
        if self.value() == "low":
            return queryset.filter(stock_quantity__lte=F("reorder_level"))
        if self.value() == "available":
            return queryset.filter(stock_quantity__gt=F("reorder_level"))
        return queryset


@admin.register(Product)
class ProductAdmin(InventoryTargetAdmin):
    list_display = ("name", "sku", "category", "base_price", "stock_quantity", "reorder_level", "status", "is_featured")
    list_filter = ("status", "is_featured", "category", LowStockFilter)
    list_editable = ("stock_quantity", "reorder_level", "status", "is_featured")
    search_fields = ("name", "sku", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("category",)
    list_per_page = 25
    inlines = (ProductImageInline, ProductAttributeInline, ProductVariantInline)


@admin.register(ProductVariant)
class ProductVariantAdmin(InventoryTargetAdmin):
    list_display = ("name", "product", "sku", "price_override", "stock_quantity", "reorder_level", "is_active")
    list_filter = ("is_active", "product__category", LowStockFilter)
    search_fields = ("name", "sku", "product__name")
    list_editable = ("stock_quantity", "reorder_level", "is_active")
    list_select_related = ("product",)


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    """Stock may only move through the service, never by editing a ledger row."""

    list_display = ("stock_target", "delta", "reason", "actor", "created_at")
    list_filter = ("reason", "created_at")
    search_fields = ("product__name", "product__sku", "variant__name", "variant__sku", "note")
    fields = ("product", "variant", "delta", "reason", "note")
    readonly_fields = ("product", "variant", "delta", "reason", "note", "actor", "created_at")
    date_hierarchy = "created_at"
    list_select_related = ("product", "variant", "actor")

    @admin.display(description="Stock target")
    def stock_target(self, adjustment):
        return adjustment.variant or adjustment.product

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields if obj else ()

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        adjustment = adjust_inventory(
            product=obj.product,
            variant=obj.variant,
            delta=obj.delta,
            reason=obj.reason,
            note=obj.note,
            actor=request.user,
        )
        # Admin records the addition against the immutable ledger row created
        # by the service, instead of saving the unvalidated draft a second time.
        obj.pk = adjustment.pk
        obj._state.adding = False
        obj._state.db = adjustment._state.db
