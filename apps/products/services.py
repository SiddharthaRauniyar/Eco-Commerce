"""Transactional product and inventory workflows shared by staff and future orders."""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.products.models import InventoryAdjustment, Product, ProductVariant
from apps.security.models import AuditLog


@transaction.atomic
def adjust_inventory(
    *,
    delta: int,
    reason: str,
    actor=None,
    note: str = "",
    product: Product | None = None,
    variant: ProductVariant | None = None,
) -> InventoryAdjustment:
    """Apply one auditable stock change without allowing stock to go below zero."""

    if bool(product) == bool(variant):
        raise ValidationError("Choose exactly one product or product variant.")
    if delta == 0:
        raise ValidationError("Stock adjustment must not be zero.")

    if product is not None:
        target = Product.objects.select_for_update().get(pk=product.pk)
        target_field = "product"
    else:
        target = ProductVariant.objects.select_for_update().get(pk=variant.pk)
        target_field = "variant"

    previous_quantity = target.stock_quantity
    new_quantity = previous_quantity + delta
    if new_quantity < 0:
        raise ValidationError("This adjustment would make stock negative.")

    target.stock_quantity = new_quantity
    target.save(update_fields=("stock_quantity", "updated_at"))
    adjustment = InventoryAdjustment.objects.create(
        **{target_field: target}, delta=delta, reason=reason, actor=actor, note=note
    )
    AuditLog.objects.create(
        actor=actor,
        action="inventory.adjusted",
        target_type=f"{target._meta.app_label}.{target.__class__.__name__}",
        target_id=str(target.pk),
        before={"stock_quantity": previous_quantity},
        after={"stock_quantity": new_quantity, "delta": delta, "reason": reason},
    )
    return adjustment
