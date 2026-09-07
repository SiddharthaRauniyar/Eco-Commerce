"""Create the predefined least-privilege Django groups."""

from django.core.management.base import BaseCommand

from apps.accounts.rbac import sync_role_groups


class Command(BaseCommand):
    help = "Create or synchronize the platform role groups and their permissions."

    def handle(self, *args, **options):
        for role, count in sync_role_groups().items():
            self.stdout.write(self.style.SUCCESS(f"{role}: {count} permissions"))
