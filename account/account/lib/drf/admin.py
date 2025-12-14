"""AMAuthToken admin."""

from django.contrib import admin
from .models import AMAuthToken


# Register your models here.
class AMAuthTokenAdmin(admin.ModelAdmin):
    """AMAuthToken model admin."""

    # pylint: disable=C0115
    class Meta:
        verbose_name = "CLI API Keys"

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_display = (
        "created_at",
        "account",
        "name",
        "description",
        "last_used_at",
        "is_active",
        "expiry",
    )

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self.list_display = [field.name for field in model._meta.fields]


admin.site.register(AMAuthToken, AMAuthTokenAdmin)
