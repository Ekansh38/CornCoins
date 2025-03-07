from .models import Account, Order, Market, Transaction, MarketPriceHistory, NewsArticle, DirectMessage, GlobalChatMessage, SlotMachineHistory, Comment
import traceback
from decimal import Decimal, ROUND_DOWN 
from django.db.models import Q
from django.contrib import messages
from .models import MarketplaceListing
from .forms import MarketplaceListingForm, ProfileUpdateForm

from .forms import NewsArticleForm
from django.db.models import Sum

from django.utils.timezone import now, timedelta
from django.contrib.auth.hashers import check_password
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
import random, json

MAX_ORDERS_PER_USER = 10

with open("/opt/CornCoins/keys.json", "r") as f:
    secrets = json.load(f)
    NEWS_PASSWORD = secrets["news"]
    cttpswrd = secrets["ctsm"]

def check_session(request):
    """
    Returns whether the user is logged in.
    """
    return JsonResponse({"logged_in": "account_id" in request.session})


@csrf_exempt
def login_view(request):
    """
    Handles user login and redirects them properly.
    """
    if request.method == "POST":
        username = request.POST.get("name")
        password = request.POST.get("password")

        account = Account.objects.filter(name=username).first()
        if account and check_password(password, account.password):
            request.session["account_id"] = account.id
            request.session.modified = True  # Ensure session is saved
            print(f"✅ Login successful! Session ID: {request.session.session_key}")
            return JsonResponse({"redirect": "/"})  # Return JSON instead of redirect()

        return JsonResponse({"error": "❌ Invalid credentials"}, status=400)

    return render(request, "bank/login.html")


def logout_view(request):
    """
    Logs the user out and redirects to login page.
    """
    request.session.flush()
    return redirect("login")


def update_market_price():
    """
    Updates the market price based on the weighted average of the last 3 transactions.
    """
    market, _ = Market.objects.get_or_create(id=1)

    # Remove all coins mined
    non_coinbase_transactions = market.transactions.exclude(
        seller__name="Corn Coins Inc"
    )

    last_three_trades = non_coinbase_transactions.order_by("-timestamp")[:3]

    # Weighted average of last 3 trades
    total_amount = sum(t.amount for t in last_three_trades)
    weighted_prices = [t.price * t.amount for t in last_three_trades]
    sum_weighted_prices = sum(weighted_prices)
    new_price = sum_weighted_prices / total_amount

    market.market_price = new_price

    market.save()
    print(f"📈 Market Price Updated: ${new_price:.2f}")

    MarketPriceHistory.objects.create(price=new_price)


def order_book(request):
    """
    Fetches all open buy and sell orders and returns them in JSON format.
    """
    buy_orders = Order.objects.filter(order_type="BUY", status="OPEN").order_by(
        "-price", "created_at"
    )
    sell_orders = Order.objects.filter(order_type="SELL", status="OPEN").order_by(
        "price", "created_at"
    )

    # Get the latest market price
    market = Market.objects.first()
    market_price = market.market_price if market else 0.0

    # Format order data with proper user names
    buy_orders_data = [
        {"user": order.user.name, "amount": order.amount, "price": order.price}
        for order in buy_orders
    ]
    sell_orders_data = [
        {"user": order.user.name, "amount": order.amount, "price": order.price}
        for order in sell_orders
    ]

    total_limit = 12
    buy_number = len(buy_orders_data)
    sell_number = len(sell_orders_data)

    if buy_number + sell_number > total_limit:
        half_limit = total_limit // 2  # Integer division to ensure it's a whole number

        if buy_number > half_limit and sell_number > half_limit:
            buy_orders_data = buy_orders_data[:half_limit]
            sell_orders_data = sell_orders_data[:half_limit]
        elif buy_number <= half_limit:
            sell_orders_data = sell_orders_data[: total_limit - buy_number]
        elif sell_number <= half_limit:
            buy_orders_data = buy_orders_data[: total_limit - sell_number]
    return JsonResponse(
        {
            "market_price": market_price,
            "buy_orders": buy_orders_data,
            "sell_orders": sell_orders_data,
        }
    )


def match_orders():
    """
    Matches buy and sell orders, executes trades, updates balances, and records transactions.
    """
    buy_orders = Order.objects.filter(order_type="BUY", status="OPEN").order_by(
        "-price", "created_at"
    )
    sell_orders = Order.objects.filter(order_type="SELL", status="OPEN").order_by(
        "price", "created_at"
    )

    corn_coins_inc, created = Account.objects.get_or_create(
        name="Corn Coins Inc",
        defaults={
            "balance_credits": 0,
            "corn_coins": 0,
            "password": "theynotliketheylikeshmokingdonkeys1234567899",
        },
    )

    market, _ = Market.objects.get_or_create()

    for buy_order in buy_orders:
        for sell_order in sell_orders:
            if buy_order.user == sell_order.user:
                continue  # Prevent self-trading

            if buy_order.price >= sell_order.price:  # Match condition
                trade_price = sell_order.price

                # Check how much the buyer can afford
                max_affordable_amount = buy_order.user.balance_credits / trade_price
                trade_amount = min(
                    buy_order.amount, sell_order.amount, max_affordable_amount
                )

                buyer = buy_order.user
                seller = sell_order.user
                total_cost = trade_amount * trade_price
                transaction_fee = total_cost * 0.025  # 2.5% fee

                # Execute trade
                try:
                    with transaction.atomic():
                        buyer.balance_credits -= total_cost
                        net_received = total_cost - transaction_fee
                        seller.balance_credits += net_received

                        buyer.corn_coins += trade_amount
                        seller.corn_coins -= trade_amount

                        buyer.save()
                        seller.save()

                        corn_coins_inc.balance_credits += transaction_fee
                        corn_coins_inc.save()

                        # Record transaction
                        transaction_record = Transaction.objects.create(
                            buyer=buyer,
                            seller=seller,
                            amount=trade_amount,
                            market_price_at_trade=market.market_price,
                            price=trade_price,
                        )

                        # Update Market Price
                        market.transactions.add(transaction_record)
                        update_market_price()

                        # Update Orders and handle partial matches
                        buy_order.amount -= trade_amount
                        sell_order.amount -= trade_amount

                        if buy_order.amount < 1:
                            buy_order.status = "MATCHED"
                            buy_order.delete()
                        else:
                            buy_order.save()

                        if sell_order.amount < 1:
                            sell_order.status = "MATCHED"
                            sell_order.delete()
                        else:
                            sell_order.save()

                        print(
                            f"✅ Matched Order: {buyer.name} bought {trade_amount} CC from {seller.name} at ${trade_price}"
                        )

                except Exception as e:
                    print(f"❌ ERROR: Failed to process trade - {e}")


@csrf_exempt
def place_order(request):
    """
    Handles buy/sell orders and validates the request data.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "❌ Invalid JSON format"}, status=400)

        # Extract values safely
        order_type = data.get("order_type")
        amount = data.get("amount")
        price = data.get("price")

        # Check if not negative and can afford

        user = Account.objects.get(id=request.session["account_id"])
        user_credits = user.balance_credits
        user_corn_coins = user.corn_coins

        open_orders_count = Order.objects.filter(user=user, status="OPEN").count()

        if open_orders_count >= MAX_ORDERS_PER_USER:
            return JsonResponse({"error": "❌ You have too many open orders!"})

        existing_buy_orders_value = Order.objects.filter(
            user=user, order_type="BUY", status="OPEN"
        ).aggregate(Sum("amount"), Sum("price"))

        existing_sell_orders_amount = Order.objects.filter(
            user=user, order_type="SELL", status="OPEN"
        ).aggregate(Sum("amount"))

        total_existing_buy_value = (existing_buy_orders_value["amount__sum"] or 0) * (
            existing_buy_orders_value["price__sum"] or 0
        )
        total_existing_sell_amount = existing_sell_orders_amount["amount__sum"] or 0

        print(total_existing_buy_value, total_existing_sell_amount)

        total_price = amount * price

        if order_type == "BUY":
            total_buying_power = user_credits - total_existing_buy_value
            if total_price > total_buying_power:
                return JsonResponse(
                    {"error": "❌ Insufficient balance for this order!"}
                )

        elif order_type == "SELL":

            total_selling_power = user_corn_coins - total_existing_sell_amount
            if amount > total_selling_power:
                return JsonResponse(
                    {"error": "❌ Insufficient corn coins to place sell order"},
                    status=400,
                )

        if amount < 0 or price < 0:
            return JsonResponse({"error": "❌ Negative values not allowed"}, status=400)

        if not order_type or not amount or not price:
            return JsonResponse({"error": "❌ Missing required fields"}, status=400)

        if order_type not in ["BUY", "SELL"]:
            return JsonResponse({"error": "❌ Invalid order type"}, status=400)

        try:
            amount = float(amount)
            price = float(price)
        except ValueError:
            return JsonResponse(
                {"error": "❌ Amount and price must be valid numbers"}, status=400
            )

        if "account_id" not in request.session:
            return JsonResponse({"error": "❌ User not logged in"}, status=400)

        user = Account.objects.filter(id=request.session["account_id"]).first()
        if not user:
            return JsonResponse({"error": "❌ User not found"}, status=400)

        # Save order with the correct order type
        Order.objects.create(
            user=user, order_type=order_type, amount=amount, price=price
        )
        match_orders()

        return JsonResponse(
            {"message": f"✅ Order placed: {order_type} {amount} CC @ ${price:.2f}"}
        )

    return JsonResponse({"error": "❌ Invalid request method"}, status=400)


def get_user_data(request):
    """
    Returns the logged-in user's data for frontend use.
    """
    if "account_id" not in request.session:
        return JsonResponse({"error": "Not logged in"}, status=400)

    account = Account.objects.get(id=request.session["account_id"])
    return JsonResponse(
        {
            "name": account.name,
            "balance_credits": account.balance_credits,
            "corn_coins": account.corn_coins,
            "profile_picture": account.profile_picture.url,
        }
    )


def index(request):
    """
    Shows the index page, but only if the user is logged in.
    Otherwise, redirects to login.
    """

    account_id = request.session.get("account_id")

    if not account_id:
        return redirect("/logout/")  # Redirect missing users to logout

    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]  # Remove invalid session
        return redirect("/logout/")  # Log out the user

    account = Account.objects.get(id=request.session["account_id"])
    market = Market.objects.first()  # Get the latest market price

    transactions = market.transactions.order_by("-timestamp") if market else []

    return render(
        request,
        "bank/index.html",
        {
            "account": account,
            "market_price": market.market_price if market else 5.0,
            "transactions": transactions,
        },
    )


def signup_view(request):
    """
    Creates a new user account.
    """
    if request.method == "POST":
        username = request.POST.get("name")
        password = request.POST.get("password")
        is_business = request.POST.get("is_business")
        if is_business == "true":
            is_business = True
        else:
            is_business = False

        if Account.objects.filter(name=username).exists():
            return JsonResponse({"error": "Username already taken."}, status=400)

        # Create user
        Account.objects.create(name=username, password=password, is_business=is_business)
        return JsonResponse({"message": "Account created successfully!"})

    return render(request, "bank/signup.html")


@csrf_exempt
def mine(request):
    """
    Provides a mining interface for users to earn Corn Coins.
    """
    market, _ = Market.objects.get_or_create()
    if "account_id" not in request.session:
        return JsonResponse(
            {"error": "Unauthorized access. Please log in."}, status=401
        )

    if request.method == "POST":
        if not market.mining_code:
            market.generate_new_code()

        try:
            data = json.loads(request.body)
            entered_code = data.get("code")
            print(entered_code)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request format"}, status=400)

        if not entered_code:
            return JsonResponse({"error": "No code entered"}, status=400)

        market = Market.objects.first()
        if not market or not market.mining_code:
            return JsonResponse({"error": "Mining system not ready"}, status=400)

        if market.verify_code(entered_code):
            # Reward user with coins
            user = Account.objects.get(id=request.session["account_id"])
            user.corn_coins += market.mining_reward
            user.save()

            # Update Market Data (reduce reward over time)
            market.current_supply += market.mining_reward
            if market.current_supply >= market.max_supply:
                return JsonResponse(
                    {"error": "Max supply reached! No more mining."}, status=400
                )

            market.generate_new_code()  # Generate new mining code
            market.mining_reward *= (
                0.5 if market.current_supply % 1000 == 0 else 1
            )  # Reduce reward every 1000 coins
            market.save()

            corn_coins_inc, _ = Account.objects.get_or_create(
                name="Corn Coins Inc",
                defaults={
                    "balance_credits": 0,
                    "corn_coins": 0,
                    "password": "theynotliketheylikeshmokingdonkeys1234567899",
                },
            )

            transaction_record = Transaction.objects.create(
                buyer=user, seller=corn_coins_inc, amount=market.mining_reward, price=0
            )
            market.transactions.add(transaction_record)
            market.save()

            return JsonResponse(
                {
                    "success": True,
                    "reward": market.mining_reward,
                    "new_supply": market.current_supply,
                    "new_reward": market.mining_reward,
                }
            )
        else:
            return JsonResponse({"error": "Incorrect mining code"}, status=400)

    return render(request, "bank/mining.html", {"market": market})


def transaction_graph(request):
    market_prices = MarketPriceHistory.objects.order_by("timestamp")[:500]

    # Extract timestamps & prices
    data = {
        "timestamps": [
            entry.timestamp.strftime("%Y-%m-%d %H:%M") for entry in market_prices
        ],
        "prices": [entry.price for entry in market_prices],
    }

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(data)

    return render(request, "bank/graph.html", {"data": data})


@csrf_exempt
def bank_transfer(request):
    account_id = request.session.get("account_id")

    if not account_id:
        return redirect("/logout/")  # Redirect missing users to logout

    try:
        sender = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]  # Remove invalid session
        return redirect("/logout/")  # Log out the user

    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Ensure JSON format
            receiver_username = data.get("receiver")
            amount = data.get("amount")
            currency_type = data.get("currency_type")

            # Ensure valid input
            if not receiver_username or not amount or not currency_type:
                return JsonResponse({"error": "All fields are required"}, status=400)

            try:
                amount = float(amount)
                if amount <= 0:
                    return JsonResponse(
                        {"error": "Amount must be greater than 0"}, status=400
                    )
            except ValueError:
                return JsonResponse({"error": "Invalid amount format"}, status=400)

            # Check if receiver exists
            try:
                receiver = Account.objects.get(name=receiver_username)
            except Account.DoesNotExist:
                return JsonResponse({"error": "Receiver not found"}, status=404)

            # Prevent self-transfers
            if receiver == sender:
                return JsonResponse(
                    {"error": "Cannot transfer to yourself"}, status=400
                )

            # Check sender balance
            if currency_type == "credits":
                if sender.balance_credits < amount:
                    return JsonResponse({"error": "Insufficient credits"}, status=400)
                sender.balance_credits -= amount
                receiver.balance_credits += amount
            elif currency_type == "corn_coins":
                if sender.corn_coins < amount:
                    return JsonResponse(
                        {"error": "Insufficient Corn Coins"}, status=400
                    )
                sender.corn_coins -= amount
                receiver.corn_coins += amount
            else:
                return JsonResponse({"error": "Invalid currency type"}, status=400)

            # Save changes
            sender.save()
            receiver.save()

            if currency_type == "corn_coins":
                currency_type = "Corn Coins"

            content = f"💰 Bank Transfer Notification: {sender.name} sent {amount} {currency_type} to you!"
            DirectMessage.objects.create(sender=sender, receiver=receiver, content=content, is_bank_transfer=True)


            return JsonResponse(
                {"success": f"Sent {amount} {currency_type} to {receiver.name}!"}
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON request format"}, status=400)

    return render(request, "bank/bank_transfer.html")


@csrf_exempt
def auto_mine(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        guess_count = int(data.get("guess_count", 0))
        if guess_count < 1:
            return JsonResponse(
                {"error": "You must buy at least 1 auto guess"}, status=400
            )
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid data format"}, status=400)

    # Ensure user is logged in
    account_id = request.session.get("account_id")
    if not account_id:
        return JsonResponse({"error": "User not authenticated"}, status=401)

    try:
        user = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]
        return JsonResponse({"error": "Invalid account"}, status=401)

    # Deduct the cost (7 credits per guess)
    total_cost = guess_count * 7
    if user.balance_credits < total_cost:
        return JsonResponse({"error": "Insufficient credits"}, status=400)

    user.balance_credits -= total_cost
    user.save()

    # Get Market Instance
    market = Market.objects.first()
    if not market or not market.mining_code:
        return JsonResponse({"error": "Mining system not ready"}, status=400)

    attempted_codes = set()
    success = False
    mined_reward = 0

    for _ in range(guess_count):
        while True:
            guess = (
                f"{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
            )
            if guess not in attempted_codes:
                attempted_codes.add(guess)
                break

        if market.verify_code(guess):
            success = True
            mined_reward = market.mining_reward
            break  # Stop auto-mining if successful

    if success:
        # Reward user
        user.corn_coins += mined_reward
        user.save()

        # Update Market Data
        market.current_supply += mined_reward
        if market.current_supply >= market.max_supply:
            return JsonResponse(
                {"error": "Max supply reached! No more mining."}, status=400
            )

        market.generate_new_code()  # Generate a new mining code
        market.mining_reward *= (
            0.5 if market.current_supply % 1000 == 0 else 1
        )  # Reduce reward every 1000 coins
        market.save()

        # Log transaction
        corn_coins_inc, created = Account.objects.get_or_create(
            name="Corn Coins Inc",
            defaults={
                "balance_credits": 0,
                "corn_coins": 0,
                "password": "theynotliketheylikeshmokingdonkeys1234567899",
            },
        )

        transaction_record = Transaction.objects.create(
            buyer=user, seller=corn_coins_inc, amount=mined_reward, price=0
        )
        market.transactions.add(transaction_record)
        market.save()

        return JsonResponse(
            {
                "success": True,
                "message": f"✅ Auto-mining succeeded! You mined {mined_reward} CC!",
                "reward": mined_reward,
                "new_supply": market.current_supply,
                "new_reward": market.mining_reward,
            }
        )

    return JsonResponse(
        {"success": False, "error": "All guesses were incorrect. Try again!"}
    )


def user_orders(request):
    """Returns a list of the user's active orders"""
    account_id = request.session.get("account_id")

    if not account_id:
        return JsonResponse({"error": "User not authenticated"}, status=403)

    user = get_object_or_404(Account, id=account_id)
    orders = Order.objects.filter(user=user).order_by("-created_at")

    order_list = [
        {
            "id": order.id,
            "amount": order.amount,
            "price": order.price,
            "order_type": order.order_type,
        }
        for order in orders
    ]

    return JsonResponse({"orders": order_list})


@csrf_exempt
def delete_order(request, order_id):
    """Deletes a user's order if they own it"""
    account_id = request.session.get("account_id")

    if not account_id:
        return JsonResponse({"error": "User not authenticated"}, status=403)

    user = get_object_or_404(Account, id=account_id)
    order = get_object_or_404(Order, id=order_id, user=user)

    order.delete()

    return JsonResponse({"success": "Order deleted successfully"})


def market_summary(request):
    # Get the last 24 hours of transactions
    last_24_hours = now() - timedelta(hours=24)
    recent_trades = Transaction.objects.filter(timestamp__gte=last_24_hours)

    # Calculate total trade volume
    total_volume = sum(trade.amount for trade in recent_trades)

    # Get lowest/highest buy/sell orders
    lowest_buy = Order.objects.filter(order_type="BUY").order_by("price").first()
    highest_buy = Order.objects.filter(order_type="BUY").order_by("-price").first()
    lowest_sell = Order.objects.filter(order_type="SELL").order_by("price").first()
    highest_sell = Order.objects.filter(order_type="SELL").order_by("-price").first()

    data = {
        "lowest_buy": lowest_buy.price if lowest_buy else "--",
        "highest_buy": highest_buy.price if highest_buy else "--",
        "lowest_sell": lowest_sell.price if lowest_sell else "--",
        "highest_sell": highest_sell.price if highest_sell else "--",
        "total_volume": total_volume,
    }

    return JsonResponse(data)


def full_order_book(request):
    """
    Renders the full order book page showing all open buy and sell orders.
    """
    buy_orders = Order.objects.filter(order_type="BUY", status="OPEN").order_by(
        "-price", "created_at"
    )
    sell_orders = Order.objects.filter(order_type="SELL", status="OPEN").order_by(
        "price", "created_at"
    )

    context = {"buy_orders": buy_orders, "sell_orders": sell_orders}
    return render(request, "bank/order_book.html", context)


def all_transactions(request):
    transactions = Transaction.objects.all().order_by("-timestamp")
    return render(request, "bank/transactions.html", {"transactions": transactions})


def news_view(request):
    """
    Displays news articles in descending order of time.
    """
    articles = NewsArticle.objects.all().order_by("-timestamp")
    return render(request, "bank/news.html", {"articles": articles})




@csrf_exempt
def add_news(request):
    """
    Handles news article submission including image uploads.
    Requires a password for access.
    """
    if request.method == "POST":
        entered_password = request.POST.get("password")  # Get entered password

        if entered_password != NEWS_PASSWORD:
            messages.error(request, "❌ Incorrect password!")
            return redirect("add_news")  # Reload the page

        form = NewsArticleForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ News article added successfully!")
            return redirect("news")  # Redirect to news page after submission

    else:
        form = NewsArticleForm()

    return render(request, "bank/add_news.html", {"form": form})


from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import json

from .models import Account, DirectMessage, GlobalChatMessage


@csrf_exempt
def send_dm(request):
    """Handles sending direct messages between users."""
    account_id = request.session.get("account_id")
    if not account_id:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        sender = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]
        return JsonResponse({"error": "Invalid account"}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            receiver_id = data.get("receiver_id")
            content = data.get("content")

            if not receiver_id or not content:
                return JsonResponse({"error": "Missing fields"}, status=400)

            receiver = get_object_or_404(Account, id=receiver_id)

            DirectMessage.objects.create(sender=sender, receiver=receiver, content=content)

            return JsonResponse({"message": "Message sent successfully!"})
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
def send_global_message(request):
    """Handles sending messages to the global chat."""
    account_id = request.session.get("account_id")
    if not account_id:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        sender = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]
        return JsonResponse({"error": "Invalid account"}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            content = data.get("content")

            if not content:
                return JsonResponse({"error": "Message cannot be empty"}, status=400)

            GlobalChatMessage.objects.create(sender=sender, content=content)

            return JsonResponse({"message": "Message sent to global chat!"})
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({"error": "Invalid request"}, status=400)


def dm_home(request):
    """Displays the DM page with existing conversations and global chat."""
    if "account_id" not in request.session:
        return redirect("/logout/")

    user = Account.objects.get(id=request.session["account_id"])

    # Get unique conversation partners
    dm_partners = Account.objects.filter(
        Q(id__in=DirectMessage.objects.filter(sender=user).values_list("receiver_id", flat=True)) |
        Q(id__in=DirectMessage.objects.filter(receiver=user).values_list("sender_id", flat=True))
    ).distinct()

    global_messages = GlobalChatMessage.objects.all().order_by("-timestamp")[:50]

    return render(
        request,
        "bank/dm.html",
        {"dm_partners": dm_partners, "global_messages": global_messages},
    )



@csrf_exempt
def get_dm_history(request, user_id):
    """Fetches DM history between the logged-in user and the selected receiver."""
    if "account_id" not in request.session:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        user = Account.objects.get(id=request.session["account_id"])
    except Account.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=403)

    receiver = get_object_or_404(Account, id=user_id)

    messages = DirectMessage.objects.filter(
        Q(sender=user, receiver=receiver) | Q(sender=receiver, receiver=user)
     ).order_by("timestamp")

    unread_messages = messages.filter(receiver=user, is_read=False)
    unread_messages.update(is_read=True)

    messages_data = [
            {
                "sender": msg.sender.name,
                "content": msg.content.replace("\n", "\\n"),  # ✅ Encode newlines safely

                "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M"),
                "is_bank_transfer": msg.is_bank_transfer,
                "sender_id": msg.sender.id,
                "id": msg.id,
            }
            for msg in messages
        ]

    return JsonResponse({"messages": messages_data})



def get_new_messages(request):
    """Fetches new messages for AJAX refreshing."""
    if "account_id" not in request.session:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    user = Account.objects.get(id=request.session["account_id"])

    dms = DirectMessage.objects.filter(receiver=user).order_by("-timestamp")[:20]
    global_messages = GlobalChatMessage.objects.all().order_by("-timestamp")[:20]

    return JsonResponse({
        "dms": [{"sender": dm.sender.name, "content": dm.content} for dm in dms],
        "global": [{"sender": gm.sender.name, "content": gm.content} for gm in global_messages],
    })









@csrf_exempt
def start_dm(request):
    """
    Allows a logged-in user to start a DM by entering a username.
    If a DM does not exist, it creates an empty message to initialize the chat.
    """
    account_id = request.session.get("account_id")

    if not account_id:
        return redirect("/logout/")  # Redirect missing users to logout

    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]  # Remove invalid session
        return redirect("/logout/")  # Log out the user

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            username = data.get("username", "").strip()
        except json.JSONDecodeError:
            return JsonResponse({"error": "❌ Invalid request format"}, status=400)

        if not username:
            return JsonResponse({"error": "❌ Please enter a username"}, status=400)

        # ✅ Find receiver account
        try:
            receiver = Account.objects.get(name=username)
        except Account.DoesNotExist:
            return JsonResponse({"error": "❌ User not found"}, status=404)

        # ✅ Prevent self-chat
        if receiver == account:
            return JsonResponse({"error": "❌ You cannot DM yourself!"}, status=400)

        # ✅ Check if a DM already exists
        existing_dm = DirectMessage.objects.filter(
            sender=account, receiver=receiver
        ).exists() or DirectMessage.objects.filter(
            sender=receiver, receiver=account
        ).exists()

        if not existing_dm:
            # ✅ Create an empty message to initialize the chat
            DirectMessage.objects.create(
                sender=account,
                receiver=receiver,
                content=" ",  # Empty message to start the conversation
            )

        return JsonResponse({"success": "✅ Chat started!", "receiver_id": receiver.id})

    return render(request, "bank/start_dm.html")




def unread_messages(request):
    """
    Fetches the number of unread messages for the logged-in user and includes sender IDs.
    """
    account_id = request.session.get("account_id")
    if not account_id:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    user = get_object_or_404(Account, id=account_id)

    unread = DirectMessage.objects.filter(receiver=user, is_read=False).values("sender").distinct()

    unread_senders = [
        {"id": item["sender"], "name": Account.objects.get(id=item["sender"]).name}
        for item in unread
    ]

    return JsonResponse({"unread_count": len(unread_senders), "unread_senders": unread_senders})








def marketplace_home(request):
    """
    Displays marketplace listings with filtering options.
    """
    listings = MarketplaceListing.objects.filter(is_active=True).order_by("-created_at")


    # 🔍 Get Filters from URL Parameters
    query = request.GET.get("q", "").strip()
    listing_type = request.GET.get("listing_type", "").strip()
    min_price = request.GET.get("min_price", "")
    max_price = request.GET.get("max_price", "")
    min_price_cc = request.GET.get("min_price_cc", "")
    max_price_cc = request.GET.get("max_price_cc", "")

    # 🔎 Apply Text Search
    if query:
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query))

    # 🛍 Filter by Listing Type
    if listing_type:
        listings = listings.filter(listing_type=listing_type)

    if min_price:
        listings = listings.filter(price__gte=min_price)
    if max_price:
        listings = listings.filter(price__lte=max_price)

    # 🌽 Filter by Corn Coin Price
    if min_price_cc:
        listings = listings.filter(price_cc__gte=min_price_cc)
    if max_price_cc:
        listings = listings.filter(price_cc__lte=max_price_cc)

    return render(request, "marketplace/home.html", {"listings": listings})



@csrf_exempt
def create_listing(request):
    if "account_id" not in request.session:
        return JsonResponse({"error": "You must be logged in"}, status=403)

    user = get_object_or_404(Account, id=request.session["account_id"])
    if request.method == "POST":

        title = request.POST.get("title")
        description = request.POST.get("description")
        listing_type = request.POST.get("listing_type")
        price = request.POST.get("price")
        price_cc = request.POST.get("price_cc")

        image = request.FILES.get("image")
        video = request.FILES.get("video")



        if not title or not description or not listing_type:
            return JsonResponse({"error": "Missing required fields"}, status=400)

        listing = MarketplaceListing(
            seller=user,
            title=title,
            description=description,
            listing_type=listing_type,
            price=float(price) if price else None,
            price_cc=int(price_cc) if price_cc else None,
            image=image,
            video=video,
            is_active=True  # Automatically activate listing
        )
        listing.save()

        return JsonResponse({"success": True, "listing_id": listing.id})
    else:
        return render(request, "marketplace/add_listing.html")



def contact_seller(request, listing_id):
    """
    Starts a DM with the seller when 'Contact Seller' is clicked.
    """
    if "account_id" not in request.session:
        return redirect("/logout/")

    buyer = get_object_or_404(Account, id=request.session["account_id"])
    listing = get_object_or_404(MarketplaceListing, id=listing_id)

    # Create a blank DM if no chat exists
    DirectMessage.objects.create(
        sender=buyer,
        receiver=listing.seller,
        content="(This is an automated message to start a chat about your listing.)"
    )

    return redirect(f"/dm/?open_chat={listing.seller.id}")


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import MarketplaceListing, Account
import logging

logger = logging.getLogger(__name__)  # ✅ Add logging for debugging

@csrf_exempt
def close_listing(request, listing_id):
    """Allows the seller to close their listing."""
    if "account_id" not in request.session:
        return JsonResponse({"error": "Not logged in"}, status=403)

    user = get_object_or_404(Account, id=request.session["account_id"])
    listing = get_object_or_404(MarketplaceListing, id=listing_id)

    logger.info(f"User {user.name} ({user.id}) is trying to close listing {listing.id}.")

    if listing.seller != user:
        logger.warning(f"❌ Unauthorized close attempt by {user.name} on listing {listing.id}.")
        return JsonResponse({"error": "Unauthorized"}, status=403)

    try:
        listing.is_active = False  # ✅ Mark the listing as closed
        listing.save()
        logger.info(f"✅ Listing {listing.id} closed successfully.")
        return JsonResponse({"message": "Listing closed successfully!"})

    except Exception as e:
        logger.error(f"❌ Error closing listing: {str(e)}")
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)



def listing_detail_view(request, listing_id):
    """Shows a detailed page for a marketplace listing."""
    listing = get_object_or_404(MarketplaceListing, id=listing_id)

    return render(request, "marketplace/listing_detail.html", {"listing": listing})






def update_profile(request):
    if "account_id" not in request.session:
        return JsonResponse({"error": "Not logged in"}, status=403)

    user = get_object_or_404(Account, id=request.session["account_id"])


    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect("index")

    else:
        form = ProfileUpdateForm(instance=user)

    return render(request, "bank/update_profile.html", {"form": form})


def profile(request):
    """Displays the user's profile"""

    if "account_id" not in request.session:
        return JsonResponse({"error": "Not logged in"}, status=403)

    user = get_object_or_404(Account, id=request.session["account_id"])
    user = get_object_or_404(Account, id=request.session.get("account_id"))
    return render(request, "bank/profile.html", {"user": user})



def get_user_profile(request, user_id):
    """Returns JSON data for the user's profile picture and name."""
    user = get_object_or_404(Account, id=user_id)
    
    return JsonResponse({
        "name": user.name,
        "profile_picture": user.profile_picture.url if user.profile_picture else "/static/default_profile.jpg"
    })





def accounts_list(request):
    """Renders the /accounts/ page with all users."""
    accounts = Account.objects.all()
    return render(request, "bank/accounts.html", {"accounts": accounts})


def search_accounts(request):
    """Returns filtered accounts based on search input."""
    query = request.GET.get("q", "").strip().lower()

    accounts = Account.objects.filter(name__icontains=query) if query else Account.objects.all()

    data = [
        {
            "name": account.name,
            "profile_picture": account.profile_picture.url if account.profile_picture else "/media/default_profile.jpg"
        }
        for account in accounts
    ]

    return JsonResponse({"accounts": data})


def map(request):
    return render(request, "bank/map.html")



def momos_menu(request):
    momo = get_object_or_404(Account, name="Momo")
    return render(request, "momos_menu.html", {"momo_id": momo.id})



def edit_listing(request, listing_id):

    account_id = request.session.get("account_id")

    if not account_id:
        return redirect("/logout/")  

    try:
        user = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]  
        return redirect("/logout/") 

    listing = get_object_or_404(MarketplaceListing, id=listing_id)

    if listing.seller != user:
        return redirect("marketplace_home")

    if request.method == "POST":
        form = MarketplaceListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            form.save()
            return redirect("listing_detail", listing_id=listing.id)
    else:
        form = MarketplaceListingForm(instance=listing)

    return render(request, "marketplace/edit_listing.html", {"form": form, "listing": listing})

import random
from decimal import Decimal, ROUND_DOWN

def arcade(request):
    account_id = request.session.get("account_id")

    if not account_id:
        return redirect("/logout/")

    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        del request.session["account_id"]
        return redirect("/logout/")

    try:
        treasury = Account.objects.get(name="Corntopia Arcade")
    except Account.DoesNotExist:
        return JsonResponse({"message": "CT Slot Machine account not found!"}, status=500)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            bet_amount = Decimal(str(data.get("bet_amount", "0.00"))).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            currency = data.get("currency")

            if bet_amount <= 0:
                return JsonResponse({"message": "Invalid bet amount!"}, status=400)

            account.balance_credits = Decimal(str(account.balance_credits)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            account.corn_coins = Decimal(str(account.corn_coins)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            treasury.balance_credits = Decimal(str(treasury.balance_credits)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            treasury.corn_coins = Decimal(str(treasury.corn_coins)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


            # Ensure the user has enough balance
            if currency == "credits":
                if bet_amount > account.balance_credits:
                    return JsonResponse({"message": "Not enough Credits!"}, status=400)
                account.balance_credits -= bet_amount
                treasury.balance_credits += bet_amount  # Treasury gains money when user loses
            elif currency == "corn_coins":
                if bet_amount > account.corn_coins:
                    return JsonResponse({"message": "Not enough Corn Coins!"}, status=400)
                account.corn_coins -= bet_amount
                treasury.corn_coins += bet_amount  # Treasury gains money when user loses
            else:
                return JsonResponse({"message": "Invalid currency selection!"}, status=400)

            # ✅ Backend Generates the Slot Machine Results
            symbols = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣", "🌽", "🍉"]
            reels = [random.choice(symbols) for _ in range(3)]  # Generate random reels

            if reels[0] == "7️⃣" and reels[1] == "7️⃣" and reels[2] == "7️⃣":
                winnings = bet_amount * Decimal("10")
                result = "MEGA JACKPOT! (x10) 🎉"
            
            elif reels[0] == reels[1] == reels[2]:
                winnings = bet_amount * Decimal("5")
                result = "Jackpot! (x5) 🎉"

            elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
                winnings = bet_amount * Decimal("2")
                result = "Small Win! (x2)"

            else:
                winnings = Decimal("0")
                result = "Better Luck Next Time! 😢"

            # Round winnings for precision
            winnings = winnings.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            show_winning = winnings - bet_amount  # Net win or loss

            # Apply winnings and adjust treasury
            if winnings > 0:
                if currency == "credits":
                    if treasury.balance_credits >= winnings:
                        account.balance_credits += winnings
                        treasury.balance_credits -= winnings
                    else:
                        return JsonResponse({"message": "Business is out of Credits!"}, status=500)
                else:
                    if treasury.corn_coins >= winnings:
                        account.corn_coins += winnings
                        treasury.corn_coins -= winnings
                    else:
                        return JsonResponse({"message": "Business is out of Corn Coins!"}, status=500)

            if currency == "credits" and bet_amount > Decimal("500"):
                return JsonResponse({"message": "Max bet for Credits is 500!"}, status=400)
            if currency == "corn_coins" and bet_amount > Decimal("15"):
                return JsonResponse({"message": "Max bet for Corn Coins is 15!"}, status=400)

            # Save balances
            account.save()
            treasury.save()

            # Save game history
            SlotMachineHistory.objects.create(
                user=account,
                bet_amount=bet_amount,
                result=result,
                winnings=winnings
            )

            if show_winning > 0:
                return JsonResponse({
                    "message": f"{result} You won {show_winning:.2f} {currency.replace('_', ' ').title()}!",
                    "reels": reels, 
                    "new_credits": str(account.balance_credits.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
                    "new_corn_coins": str(account.corn_coins.quantize(Decimal("0.01"), rounding=ROUND_DOWN))
                })
            else:
                show_winning = show_winning * -1
                return JsonResponse({
                    "message": f"{result} You lost {show_winning:.2f} {currency.replace('_', ' ').title()}!",
                    "reels": reels, 
                    "new_credits": str(account.balance_credits.quantize(Decimal("0.01"), rounding=ROUND_DOWN)),
                    "new_corn_coins": str(account.corn_coins.quantize(Decimal("0.01"), rounding=ROUND_DOWN))
                })

        except Exception as e:
            error_details = traceback.format_exc()
            return JsonResponse({
                "message": "Something went wrong!",
                "error": str(e),
                "details": error_details
            }, status=500)

    return render(request, "bank/slot_machine.html", {"balance": account})



def news_detail(request, news_id):
    article = get_object_or_404(NewsArticle, id=news_id)
    comments = article.comments.all().order_by("-timestamp")  # Fetch comments

    if request.method == "POST":
        account_id = request.session.get("account_id")
        if not account_id:
            return redirect("/logout/")
        account = Account.objects.get(id=account_id)

        text = request.POST.get("comment_text").strip()
        if text:
            Comment.objects.create(article=article, user=account, text=text)
            messages.success(request, "Comment added successfully!")
            return redirect("news_detail", news_id=news_id)

    return render(request, "bank/news_detail.html", {"article": article, "comments": comments})




def arcade_warning(request):
    return render(request, "bank/arcade_warning.html")




from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Poll, Choice, Vote
from bank.models import Account

def get_user_account(request):
    """Fetch the currently logged-in user's account"""
    account_id = request.session.get("account_id")
    if not account_id:
        return None
    return get_object_or_404(Account, id=account_id)

def poll_list(request):
    polls = Poll.objects.all().order_by("-created_at")
    return render(request, "polls/poll_list.html", {"polls": polls})

def poll_detail(request, poll_id):
    poll = get_object_or_404(Poll, id=poll_id)
    return render(request, "polls/poll_detail.html", {"poll": poll})

def create_poll(request):
    account = get_user_account(request)
    if not account:
        return redirect("/logout/")

    if request.method == "POST":
        question = request.POST.get("question")
        choices = request.POST.getlist("choices")  # Get multiple choices
        
        if not question or len(choices) < 2:
            messages.error(request, "A poll must have a question and at least two choices.")
            return redirect("create_poll")

        poll = Poll.objects.create(question=question, created_by=account)

        for choice_text in choices:
            if choice_text.strip():
                Choice.objects.create(poll=poll, text=choice_text.strip())

        messages.success(request, "Poll created successfully!")
        return redirect("poll_list")

    return render(request, "polls/create_poll.html")

def vote_poll(request, poll_id):
    account = get_user_account(request)
    if not account:
        return redirect("/logout/")

    poll = get_object_or_404(Poll, id=poll_id)
    choice_id = request.POST.get("choice")

    if Vote.objects.filter(poll=poll, user=account).exists():
        messages.error(request, "You have already voted on this poll.")
        return redirect("poll_detail", poll_id=poll.id)

    choice = get_object_or_404(Choice, id=choice_id, poll=poll)
    choice.votes += 1
    choice.save()

    Vote.objects.create(poll=poll, user=account, choice=choice)

    messages.success(request, "Your vote has been recorded!")
    return redirect("poll_detail", poll_id=poll.id)




def get_user_account(request):
    """Fetch the currently logged-in user's account"""
    account_id = request.session.get("account_id")
    if not account_id:
        return None
    return get_object_or_404(Account, id=account_id)

def delete_poll(request, poll_id):
    account = get_user_account(request)
    if not account:
        return redirect("/logout/")

    poll = get_object_or_404(Poll, id=poll_id)

    if poll.created_by != account:
        messages.error(request, "You are not allowed to delete this poll.")
        return redirect("poll_list")

    poll.delete()
    messages.success(request, "Poll deleted successfully!")
    return redirect("poll_list")
