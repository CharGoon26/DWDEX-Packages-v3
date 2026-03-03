from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from django.db.models import Count, Q

from bd_models.models import Ball, BallInstance, Player

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

log = logging.getLogger("ballsdex.packages.leaderboard")

# How many entries to show per leaderboard page
PAGE_SIZE = 10


async def get_total_ball_count() -> int:
    """Return the total number of unique catchable balls defined in the dex."""
    return await Ball.objects.filter(enabled=True).acount()


async def build_completion_leaderboard(
    guild: discord.Guild | None = None,
    limit: int = PAGE_SIZE,
) -> list[tuple[int, int, int]]:
    """
    Build a completion leaderboard (unique balls owned vs total).

    Parameters
    ----------
    guild:
        If provided, restrict to members of this guild.
    limit:
        Max rows to return.

    Returns
    -------
    List of (discord_id, unique_count, rank) tuples, sorted by unique_count descending.
    """
    qs = (
        BallInstance.objects
        .filter(ball__enabled=True)
        .values("player__discord_id")
        .annotate(unique_count=Count("ball_id", distinct=True))
        .order_by("-unique_count")
    )

    if guild is not None:
        member_ids = [m.id for m in guild.members]
        qs = qs.filter(player__discord_id__in=member_ids)

    results = []
    rank = 1
    async for row in qs[:limit]:
        results.append((row["player__discord_id"], row["unique_count"], rank))
        rank += 1

    return results


async def build_total_leaderboard(
    guild: discord.Guild | None = None,
    limit: int = PAGE_SIZE,
) -> list[tuple[int, int, int]]:
    """
    Build a total cards collected leaderboard (all instances, including dupes).

    Parameters
    ----------
    guild:
        If provided, restrict to members of this guild.
    limit:
        Max rows to return.

    Returns
    -------
    List of (discord_id, total_count, rank) tuples, sorted by total_count descending.
    """
    qs = (
        BallInstance.objects
        .values("player__discord_id")
        .annotate(total_count=Count("id"))
        .order_by("-total_count")
    )

    if guild is not None:
        member_ids = [m.id for m in guild.members]
        qs = qs.filter(player__discord_id__in=member_ids)

    results = []
    rank = 1
    async for row in qs[:limit]:
        results.append((row["player__discord_id"], row["total_count"], rank))
        rank += 1

    return results


def format_username(bot: "BallsDexBot", discord_id: int) -> str:
    """Resolve a discord_id to a display name, falling back to the raw ID."""
    user = bot.get_user(discord_id)
    if user:
        return f"**{discord.utils.escape_markdown(user.display_name)}**"
    return f"<@{discord_id}>"


async def render_leaderboard_embed(
    bot: "BallsDexBot",
    title: str,
    description_header: str,
    rows: list[tuple[int, int, int]],  # (discord_id, count, rank)
    total_balls: int | None,           # None means we're doing total-count mode
) -> discord.Embed:
    """Render a Discord embed for a leaderboard."""
    embed = discord.Embed(title=title, color=discord.Color.gold())
    embed.description = description_header + "\n\n"

    if not rows:
        embed.description += "*No data found.*"
        return embed

    lines = []
    for discord_id, count, rank in rows:
        name = format_username(bot, discord_id)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"`#{rank}`")
        if total_balls is not None:
            lines.append(f"{medal} {name} — **{count}/{total_balls}**")
        else:
            lines.append(f"{medal} {name} — **{count}** cards")

    embed.description += "\n".join(lines)
    return embed


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: "BallsDexBot"):
        self.bot = bot

    leaderboard_group = app_commands.Group(
        name="leaderboard",
        description="View various leaderboards for the dex.",
    )

    @leaderboard_group.command(
        name="completion",
        description="Show the top players by unique ball completion (global).",
    )
    @app_commands.describe(
        limit="Number of players to show (default 10, max 25)."
    )
    async def leaderboard_completion(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        await interaction.response.defer(thinking=True)
        try:
            total = await get_total_ball_count()
            rows = await build_completion_leaderboard(guild=None, limit=limit)
            embed = await render_leaderboard_embed(
                bot=self.bot,
                title="🏆 Global Completion Leaderboard",
                description_header=f"Top players by unique balls collected out of **{total}** total.",
                rows=rows,
                total_balls=total,
            )
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error building completion leaderboard")
            await interaction.followup.send(
                "An error occurred while fetching the leaderboard. Please try again later.",
                ephemeral=True,
            )

    @leaderboard_group.command(
        name="total",
        description="Show the top players by total cards collected (including duplicates).",
    )
    @app_commands.describe(
        limit="Number of players to show (default 10, max 25)."
    )
    async def leaderboard_total(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        await interaction.response.defer(thinking=True)
        try:
            rows = await build_total_leaderboard(guild=None, limit=limit)
            embed = await render_leaderboard_embed(
                bot=self.bot,
                title="🃏 Global Total Cards Leaderboard",
                description_header="Top players by total number of cards collected (duplicates included).",
                rows=rows,
                total_balls=None,
            )
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error building total leaderboard")
            await interaction.followup.send(
                "An error occurred while fetching the leaderboard. Please try again later.",
                ephemeral=True,
            )

    @leaderboard_group.command(
        name="server",
        description="Show the top players in this server by unique ball completion.",
    )
    @app_commands.describe(
        limit="Number of players to show (default 10, max 25)."
    )
    @app_commands.guild_only()
    async def leaderboard_server(
        self,
        interaction: discord.Interaction["BallsDexBot"],
        limit: app_commands.Range[int, 1, 25] = 10,
    ):
        await interaction.response.defer(thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send(
                "This command can only be used inside a server.", ephemeral=True
            )
            return

        # Ensure member cache is populated for accurate filtering
        if not guild.chunked:
            try:
                await guild.chunk(cache=True)
            except Exception:
                log.warning(
                    "Could not chunk guild %s (%d) for server leaderboard",
                    guild.name,
                    guild.id,
                )

        try:
            total = await get_total_ball_count()
            rows = await build_completion_leaderboard(guild=guild, limit=limit)
            embed = await render_leaderboard_embed(
                bot=self.bot,
                title=f"🏅 {discord.utils.escape_markdown(guild.name)} — Server Completion Leaderboard",
                description_header=(
                    f"Top members of this server by unique balls collected out of **{total}** total."
                ),
                rows=rows,
                total_balls=total,
            )
            await interaction.followup.send(embed=embed)
        except Exception:
            log.exception("Error building server leaderboard for guild %d", guild.id)
            await interaction.followup.send(
                "An error occurred while fetching the leaderboard. Please try again later.",
                ephemeral=True,
            )
