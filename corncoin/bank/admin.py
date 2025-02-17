from django.contrib import admin
from .models import Account, Order, Market

class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "account_number", "balance_credits", "corn_coins")

class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "order_type", "amount", "price", "status", "created_at")
    list_filter = ("order_type", "status")


class MarketAdmin(admin.ModelAdmin):
    list_display = ("last_price", "get_transactions")  # ✅ Use a custom method
    filter_horizontal = ("transactions",)  # ✅ Allows ManyToManyField editing in admin

    def get_transactions(self, obj):
        """
        ✅ Returns a formatted list of transactions (limited to 3 for admin display).
        """
        transactions = obj.transactions.all().order_by("-timestamp")[:3]  # Show last 3 trades
        return ", ".join([f"{t.buyer.name} -> {t.seller.name}: {t.amount} CC @ ${t.price}" for t in transactions])

    get_transactions.short_description = "Recent Transactions"  # ✅ Sets column name in admin

admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Market, MarketAdmin)
