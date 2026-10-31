from django.db import models


class Merchant(models.Model):
    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"
        MARATHI = "mr", "Marathi"

    merchant_id = models.CharField(max_length=20, unique=True, db_index=True)
    business_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    preferred_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.merchant_id} ({self.business_name})"
