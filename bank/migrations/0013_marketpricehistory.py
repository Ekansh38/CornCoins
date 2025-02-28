# Generated by Django 5.1.6 on 2025-02-22 08:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bank', '0012_rename_last_price_market_market_price'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketPriceHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('price', models.DecimalField(decimal_places=10, max_digits=20)),
            ],
        ),
    ]
