from django.contrib import admin
from .models import Account, Order, Market, NewsArticle, DirectMessage, GlobalChatMessage, MarketPriceHistory,MarketplaceListing


class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "balance_credits", "corn_coins", "is_business", "id")


class OrderAdmin(admin.ModelAdmin):
    list_display = ("user", "order_type", "amount", "price", "status", "created_at")
    list_filter = ("order_type", "status")


class MarketAdmin(admin.ModelAdmin):
    list_display = (
        "market_price",
        "get_transactions",
        "current_supply",
        "max_supply",
        "mining_reward",
    )  # ✅ Use a custom method
    filter_horizontal = ("transactions",)  # ✅ Allows ManyToManyField editing in admin

    def get_transactions(self, obj):
        """
        ✅ Returns a formatted list of transactions (limited to 3 for admin display).
        """
        transactions = obj.transactions.all().order_by("-timestamp")[
            :3
        ]  # Show last 3 trades
        return ", ".join(
            [
                f"{t.buyer.name} -> {t.seller.name}: {t.amount} CC @ ${t.price}"
                for t in transactions
            ]
        )

    get_transactions.short_description = (
        "Recent Transactions"  # ✅ Sets column name in admin
    )

class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "description", "timestamp")  # ✅ Show in admin panel


class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "content", "timestamp", "is_bank_transfer")
    search_fields = ("sender__name", "receiver__name", "content")
    list_filter = ("timestamp", "is_bank_transfer")

class GlobalChatAdmin(admin.ModelAdmin):
    list_display = ("sender", "content", "timestamp")
    search_fields = ("user__name", "content")
    list_filter = ("timestamp",)


admin.site.register(Account, AccountAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Market, MarketAdmin)
admin.site.register(NewsArticle, NewsArticleAdmin)
admin.site.register(DirectMessage, DirectMessageAdmin)
admin.site.register(GlobalChatMessage, GlobalChatAdmin)
admin.site.register(MarketPriceHistory)
admin.site.register(MarketplaceListing)
