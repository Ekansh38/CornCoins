from django.urls import path
from .views import *

urlpatterns = [
    path("", index, name="index"),
    path("trade/", place_order, name="place_order"),
    path("orders/", order_book, name="order_book"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("check-session/", check_session, name="check-session"),
    path("get-user/", get_user_data, name="get-user"),
    path("signup/", signup_view, name="signup"),
    path("mine/", mine, name="mine"),
    path("graph/", transaction_graph, name="transaction_graph"),
    path("bank-transfer/", bank_transfer, name="bank_transfer"),
    path("auto-mine/", auto_mine, name="auto_mine"),
    path("user-orders/", user_orders, name="user_orders"),
    path("delete-order/<int:order_id>/", delete_order, name="delete_order"),
    path("market-summary/", market_summary, name="market_summary"),
]
