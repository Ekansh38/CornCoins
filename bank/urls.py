from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
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
    path("order-book/", full_order_book, name="full_order_book"),
    path("transactions/", all_transactions, name="all_transactions"),
    path("news/", news_view, name="news"),
    path("news/<int:news_id>/", news_detail, name="news_detail"),

    path("news/add/", add_news, name="add_news"),  # Page to upload articles

    path("dm/", dm_home, name="dm_home"),
    path("dm/start/", start_dm, name="start_dm"),
    path("dm/send/", send_dm, name="send_dm"),
    path("dm/unread/", unread_messages, name="unread_messages"),  

    path("dm/history/<int:user_id>/", get_dm_history, name="get_dm_history"),
    path("global/send/", send_global_message, name="send_global"),
    path("messages/update/", get_new_messages, name="get_new_messages"),

    path("marketplace/", marketplace_home, name="marketplace_home"),
    path("marketplace/create/", create_listing, name="add_listing"),
    path("marketplace/contact/<int:listing_id>/", contact_seller, name="contact_seller"),
    path("marketplace/close/<int:listing_id>/", close_listing, name="close_listing"),
    path("marketplace/<int:listing_id>/", listing_detail_view, name="listing_detail"),

    path("profile/update/", update_profile, name="update_profile"),
    path("profile/", profile, name="profile"),
    path("get-profile/<int:user_id>/", get_user_profile, name="get_user_profile"),

    path("accounts/", accounts_list, name="accounts"),
    path("accounts/search/", search_accounts, name="search_accounts"),
    path("map/", map, name="map"),
    path("momos-menu/", momos_menu, name="momos_menu"),

    path("marketplace/edit/<int:listing_id>/", edit_listing, name="edit_listing"),
    path("slot-machine/", slot_machine_view, name="slot_machine"),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
