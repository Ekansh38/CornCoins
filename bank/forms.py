from django import forms
from .models import Account
from .models import NewsArticle


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = ["title", "description", "image"]



from .models import MarketplaceListing

class MarketplaceListingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceListing
        fields = ["title", "description", "listing_type", "price", "image"]
        widgets = {
            "listing_type": forms.Select(choices=MarketplaceListing.LISTING_TYPES),
        }



class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["profile_picture"]
