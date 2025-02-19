from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Account, Order, Market, Transaction
from django.db.models import Q
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import logout
from django.contrib.auth.hashers import check_password
from django.http import JsonResponse
from datetime import timedelta
from django.utils.timezone import now


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
    # Weighted average of last 3 trades
    market, created = Market.objects.get_or_create(id=1)
    non_coinbase_transactions = market.transactions.filter(
        ~Q(buyer__name="Corn Coins Inc")
    )
    last_three_trades = non_coinbase_transactions.order_by("-timestamp")[:3]

    print(last_three_trades)

    # Weighted average of last 3 trades
    total_amount = sum(t.amount for t in last_three_trades)
    weighted_prices = [t.price * t.amount for t in last_three_trades]
    sum_weighted_prices = sum(weighted_prices)
    new_price = sum_weighted_prices / total_amount

    market.market_price = new_price

    market.save()
    print(f"📈 Market Price Updated: ${new_price:.2f}")


def get_market_price():
    market = Market.objects.first()
    if not market:
        market = Market.objects.create(market_price=120.0)
    return market.market_price


from .models import Order, Account, Transaction, Market


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
    market_price = market.market_price if market else 5.0

    # Format order data with proper user names
    buy_orders_data = [
        {"user": order.user.name, "amount": order.amount, "price": order.price}
        for order in buy_orders
    ]
    sell_orders_data = [
        {"user": order.user.name, "amount": order.amount, "price": order.price}
        for order in sell_orders
    ]

    return JsonResponse(
        {
            "market_price": market_price,
            "buy_orders": buy_orders_data,
            "sell_orders": sell_orders_data,
        }
    )


from django.db import transaction


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

                # Execute trade
                try:
                    with transaction.atomic():
                        # Transfer Corn Coins & money
                        buyer.balance_credits -= total_cost
                        seller.balance_credits += total_cost

                        buyer.corn_coins += trade_amount
                        seller.corn_coins -= trade_amount

                        buyer.save()
                        seller.save()

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

                        # Update Orders (Handle Partial Matches)
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


@csrf_exempt  # Remove this in production (use CSRF tokens)
def place_order(request):
    """
    Handles buy/sell orders and validates the request data.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)  # Read JSON data
            print("🔍 Received Data:", data)  # Debugging
        except json.JSONDecodeError:
            return JsonResponse({"error": "❌ Invalid JSON format"}, status=400)

        # Extract values safely
        order_type = data.get("order_type")  # Read order type from frontend
        amount = data.get("amount")
        price = data.get("price")

        # Check if not negative and can afford

        user_credits = Account.objects.get(
            id=request.session["account_id"]
        ).balance_credits
        user_corn_coins = Account.objects.get(
            id=request.session["account_id"]
        ).corn_coins

        if order_type == "BUY":
            total_price = amount * price
            if user_credits < total_price:
                return JsonResponse(
                    {"error": "❌ Insufficient funds to place buy order"}, status=400
                )
        elif order_type == "SELL":
            if user_corn_coins < amount:
                return JsonResponse(
                    {"error": "❌ Insufficient corn coins to place sell order"},
                    status=400,
                )

        if amount < 0 or price < 0:
            return JsonResponse({"error": "❌ Negative values not allowed"}, status=400)

        if not order_type or not amount or not price:
            return JsonResponse({"error": "❌ Missing required fields"}, status=400)

        if order_type not in ["BUY", "SELL"]:  # Validate order type
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
        order = Order.objects.create(
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

    transactions = market.transactions.order_by("-timestamp")[:20] if market else []

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
    if request.method == "POST":
        username = request.POST.get("name")
        password = request.POST.get("password")

        if Account.objects.filter(name=username).exists():
            return JsonResponse({"error": "Username already taken."}, status=400)

        # Create user
        new_user = Account.objects.create(name=username, password=password)
        return JsonResponse({"message": "Account created successfully!"})

    return render(request, "bank/signup.html")


@csrf_exempt
def mine(request):
    market, created = Market.objects.get_or_create()
    if "account_id" not in request.session:
        return JsonResponse(
            {"error": "Unauthorized access. Please log in."}, status=401
        )

    if request.method == "POST":
        if not market.mining_code:  # If no mining code exists, generate a new one
            market.generate_new_code()

        try:
            data = json.loads(request.body)  # ✅ Read JSON request
            entered_code = data.get("code")
            print(entered_code)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request format"}, status=400)

        if not entered_code:
            return JsonResponse({"error": "No code entered"}, status=400)

        # Get the market instance
        market = Market.objects.first()
        if not market or not market.mining_code:
            return JsonResponse({"error": "Mining system not ready"}, status=400)

        # Check if the entered code matches
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

            corn_coins_inc, created = Account.objects.get_or_create(
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
    transactions = Transaction.objects.filter(price__gt=0).order_by("timestamp")

    # Prepare data for the graph
    data = {
        "timestamps": [t.timestamp.strftime("%Y-%m-%d %H:00") for t in transactions],
        "prices": [t.price for t in transactions],
    }

    # If it's an AJAX request, return JSON
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

            return JsonResponse(
                {"success": f"Sent {amount} {currency_type} to {receiver.name}!"}
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON request format"}, status=400)

    return render(request, "bank/bank_transfer.html")
