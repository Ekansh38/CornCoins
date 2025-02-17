from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils.timezone import now
import random

class Account(models.Model):
    name = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # Increased length for hashed password
    account_number = models.CharField(max_length=12, unique=True, editable=True)
    balance_credits = models.FloatField(default=100.0)
    corn_coins = models.FloatField(default=0.0)

    def save(self, *args, **kwargs):
        # Hash password before saving (if it's not already hashed)
        if not self.password.startswith("pbkdf2_sha256$"):  
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_password(self, raw_password):
        """
        Validates the given password against the stored hashed password.
        """
        return check_password(raw_password, self.password)

    def generate_account_number(self):
        return "".join([str(random.randint(0, 9)) for _ in range(12)])

    def __str__(self):
        return f"{self.name} - {self.account_number}"


class Order(models.Model):
    ORDER_TYPES = [("BUY", "Buy"), ("SELL", "Sell")]

    user = models.ForeignKey(Account, on_delete=models.CASCADE) # If the user is deleted so is the order
    order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
    amount = models.FloatField()
    price = models.FloatField()
    status = models.CharField(max_length=10, default="OPEN")  # OPEN, MATCHED, CANCELED
    created_at = models.DateTimeField(auto_now_add=True)

class Market(models.Model):
    last_price = models.FloatField(default=120.0) 
    transactions = models.ManyToManyField("Transaction", blank=True)  # ✅ Store all trades


class Transaction(models.Model):
    buyer = models.ForeignKey(Account, related_name="buyer", on_delete=models.CASCADE)
    seller = models.ForeignKey(Account, related_name="seller", on_delete=models.CASCADE)
    amount = models.FloatField()
    price = models.FloatField()
    timestamp = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.buyer.name} bought {self.amount} CC from {self.seller.name} at ${self.price}"
