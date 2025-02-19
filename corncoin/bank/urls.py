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
]
