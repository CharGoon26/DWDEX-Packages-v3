from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from typing import TYPE_CHECKING

import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord.ext import commands

from bd_models.models import Ball, BallInstance, Player

from ..models import DailyClaim

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger(__name__)

SHINY_RATE = 0.00048828125  # 1/2048


def _pick_ball() -> Ball:
    """Pick a random enabled ball weighted by rarity."""
    balls = list(Ball.objects.filter(enabled=True))
    if not balls:
        raise ValueError("No enabled balls.")
    weights = [b.rarity for b in balls]
    return random.choices(balls, weights=weights, k=1)[0]


class Daily(commands.Cog):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    @app_commands.command(name="daily", description="Claim your free daily card!")
    async def daily(self, interaction: discord.Interaction["BallsDexBot"]):
        await interaction.response.defer()

        today = date.today()
        player, _ = await Player.objects.aget_or_create(discord_id=interaction.user.id)

        # Check cooldown
        try:
            claim = await DailyClaim.objects.aget(player=player)
            if claim.last_claimed >= today:
                reset_time = discord.utils.utcnow().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                await interaction.followup.send(
                    f"❌ You already claimed your daily card!\n"
                    f"Next claim available {discord.utils.format_dt(reset_time, 'R')}.",
                    ephemeral=True,
                )
                return
            claim.last_claimed = today
            await sync_to_async(claim.save)()
        except DailyClaim.DoesNotExist:
            await DailyClaim.objects.acreate(player=player, last_claimed=today)

        # Pick ball and determine shiny
        try:
            ball = await sync_to_async(_pick_ball)()
        except ValueError:
            await interaction.followup.send(
                "❌ No cards available right now!", ephemeral=True
            )
            return

        is_shiny = random.random() < SHINY_RATE
        attack_bonus = random.randint(-20, 20)
        health_bonus = random.randint(-20, 20)

        await BallInstance.objects.acreate(
            ball=ball,
            player=player,
            shiny=is_shiny,
            attack_bonus=attack_bonus,
            health_bonus=health_bonus,
        )

        shiny_str = " ✨ **SHINY!**" if is_shiny else ""
        emoji = self.bot.get_emoji(ball.emoji_id) or ""

        embed = discord.Embed(
            title=f"🎁 Daily Card!{shiny_str}",
            description=(
                f"You received {emoji} **{ball.country}**!\n\n"
                f"*Come back tomorrow (UTC) for another!*"
            ),
            color=discord.Color.purple() if is_shiny else discord.Color.gold(),
        )

        # Attach card image if available
        image_field = ball.wild_card_shiny if is_shiny and ball.wild_card_shiny else ball.wild_card
        if image_field:
            try:
                file = discord.File(
                    await sync_to_async(lambda: image_field.path)(),
                    filename="card.png"
                )
                embed.set_image(url="attachment://card.png")
                await interaction.followup.send(embed=embed, file=file)
                return
            except Exception:
                log.warning(f"Could not load image for ball {ball.pk}", exc_info=True)

        await interaction.followup.send(embed=embed)
