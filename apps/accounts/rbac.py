"""Role definitions backed by Django groups and built-in model permissions."""

from django.contrib.auth.models import Group, Permission

ROLE_PERMISSIONS = {
    "Customer": (),
    "Support Agent": (
        "support.view_supportticket",
        "support.change_supportticket",
        "orders.view_order",
    ),
    "Catalog Manager": (
        "categories.*",
        "products.*",
        "reviews.view_review",
        "reviews.change_review",
    ),
    "Order Manager": (
        "orders.*",
        "payments.view_payment",
        "payments.change_payment",
        "coupons.view_coupon",
    ),
    "Marketing Manager": ("coupons.*", "blog.*", "notifications.*"),
    "Analyst": ("orders.view_order", "products.view_product", "reviews.view_review"),
    "Security Analyst": ("security.*", "vulnerability_testing.*"),
    "Administrator": ("*",),
}


def _permissions_for_rules(rules: tuple[str, ...]):
    """Resolve compact app-label/codename rules to real Django permissions."""

    if "*" in rules:
        return Permission.objects.all()

    selected_ids: set[int] = set()
    for rule in rules:
        app_label, codename = rule.split(".", 1)
        queryset = Permission.objects.filter(content_type__app_label=app_label)
        if codename != "*":
            queryset = queryset.filter(codename=codename)
        selected_ids.update(queryset.values_list("id", flat=True))
    return Permission.objects.filter(id__in=selected_ids)


def sync_role_groups() -> dict[str, int]:
    """Create every platform role and synchronize its granted model permissions."""

    counts: dict[str, int] = {}
    for role, rules in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        permissions = _permissions_for_rules(rules)
        group.permissions.set(permissions)
        counts[role] = permissions.count()
    return counts
