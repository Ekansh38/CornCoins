# Generated by Django 5.1.6 on 2025-02-11 12:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bank', '0002_rename_balance_user_balance_credits'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='User',
            new_name='Account',
        ),
    ]
