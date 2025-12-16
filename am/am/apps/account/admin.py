# Refactored: Register all models to the default Django admin site with standard ModelAdmin
from django.contrib import admin

from .models import (
    Account,
    AccountContact,
    Charge,
    DailyBillingRecord,
    PaymentMethod,
    Subscription,
    SubscriptionHosts,
    SubscriptionUser,
    UserProfile,
)


admin.site.register(Account)
admin.site.register(AccountContact)
admin.site.register(Charge)
admin.site.register(DailyBillingRecord)
admin.site.register(PaymentMethod)
admin.site.register(UserProfile)
admin.site.register(Subscription)
admin.site.register(SubscriptionHosts)
admin.site.register(SubscriptionUser)
