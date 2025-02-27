from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils.timezone import now
from cryptography.fernet import Fernet
import random


class MarketPriceHistory(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=20, decimal_places=10)
    
    def __str__(self):
        return f"{self.price} - {self.timestamp}"


class Account(models.Model):
    name = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)  # Increased length for hashed password
    balance_credits = models.FloatField(default=0.0)
    corn_coins = models.FloatField(default=0.0)
    is_business = models.BooleanField(default=False)  

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

    def __str__(self):
        return f"{self.name}"


class Order(models.Model):
    ORDER_TYPES = [("BUY", "Buy"), ("SELL", "Sell")]

    user = models.ForeignKey(
        Account, on_delete=models.CASCADE
    )  # If the user is deleted so is the order
    order_type = models.CharField(max_length=4, choices=ORDER_TYPES)
    amount = models.FloatField()
    price = models.FloatField()
    status = models.CharField(max_length=10, default="OPEN")  # OPEN, MATCHED, CANCELED
    created_at = models.DateTimeField(auto_now_add=True)


cipher = Fernet(b"t8CJ46L6jhReAzpD0D4F7L6slYSlofO8okyfhBeYif8=")


class Market(models.Model):
    market_price = models.FloatField(default=120.0)
    transactions = models.ManyToManyField("Transaction", blank=True)
    current_supply = models.FloatField(default=0.0)
    max_supply = models.FloatField(default=9999.0)
    mining_reward = models.FloatField(default=50.0)
    mining_code = models.CharField(
        max_length=255, blank=True
    )  # Stores encrypted 3-digit code

    def generate_new_code(self):
        """Generates a random 3-digit code (allows leading zeros) and encrypts it"""
        new_code = str(random.randint(0, 999)).zfill(3)
        encrypted_code = cipher.encrypt(new_code.encode()).decode()
        self.mining_code = encrypted_code
        self.save()

    def verify_code(self, input_code):
        """Decrypts and checks if the input code matches the stored mining code"""
        try:
            decrypted_code = cipher.decrypt(self.mining_code.encode()).decode()
            return input_code == decrypted_code
        except:
            return False  # If decryption fails

    def __str__(self):
        return f"Market | Last Price: {self.market_price} | Supply: {self.current_supply}/{self.max_supply}"


class Transaction(models.Model):
    buyer = models.ForeignKey(Account, related_name="buyer", on_delete=models.CASCADE)
    seller = models.ForeignKey(Account, related_name="seller", on_delete=models.CASCADE)
    amount = models.FloatField()
    price = models.FloatField()
    timestamp = models.DateTimeField(default=now)
    market_price_at_trade = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.buyer.name} bought {self.amount} CC from {self.seller.name} at ${self.price}"


class NewsArticle(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to="news_images/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class DirectMessage(models.Model):
    """
    Represents a direct message between two users.
    """
    sender = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)  
    is_bank_transfer = models.BooleanField(default=False)

    def __str__(self):
        return f"DM from {self.sender.name} to {self.receiver.name}: {self.content[:30]}"


class GlobalChatMessage(models.Model):
    """
    Represents a message in the global chat that all users can see.
    """
    sender = models.ForeignKey(Account, on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Global Message from {self.sender.name}: {self.content[:30]}"





class MarketplaceListing(models.Model):
    LISTING_TYPES = [
        ("item", "Item for Sale"),
        ("job", "Job Offer"),
    ]

    seller = models.ForeignKey("Account", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to="market_images/", null=True, blank=True)
    created_at = models.DateTimeField(default=now)
    is_active = models.BooleanField(default=True)  # Mark as sold/completed

    def close_listing(self):
        """Marks the listing as inactive (closed)."""
        self.is_active = False
        self.save()

    def __str__(self):
        return f"{self.title} - {self.seller.name}"
