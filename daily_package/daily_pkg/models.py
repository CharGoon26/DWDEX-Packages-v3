from django.db import models
from bd_models.models import Player


class DailyClaim(models.Model):
    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="daily_claim")
    last_claimed = models.DateField()

    class Meta:
        db_table = "dailyclaim"
        managed = True
