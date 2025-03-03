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
        fields = ["title", "description", "image", "video", "price", "price_cc"]
        widgets = {
            "listing_type": forms.Select(choices=MarketplaceListing.LISTING_TYPES),
        }


    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.is_active = True  
        if commit:
            listing.save()
        return listing



class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["profile_picture"]
