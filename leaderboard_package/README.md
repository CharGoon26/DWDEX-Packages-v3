# BallsDex v3 — Leaderboard Package

A custom package for **BallsDex v3** that adds `/leaderboard` slash commands.

## Commands

| Command | Description |
|---|---|
| `/leaderboard completion` | Global leaderboard — unique balls collected vs total dex size |
| `/leaderboard total` | Global leaderboard — total cards collected (duplicates count) |
| `/leaderboard server` | Server-only completion leaderboard (members of the current server only) |

All commands accept an optional `limit` argument (1–25, default 10).

## Installation

### Development (editable)

1. Place this folder in `extra/leaderboard_package`
2. Add to `config/extra.toml`:

```toml
[[ballsdex.packages]]
location = "/code/extra/leaderboard_package"   # Docker path; leave empty for non-Docker
path = "leaderboard_pkg"
enabled = true
editable = true
```

3. Rebuild with `docker compose build` (Docker) or `uv pip install -e extra/leaderboard_package` (non-Docker)

### Production (from git)

```toml
[[ballsdex.packages]]
location = "git+https://github.com/YOUR_USERNAME/leaderboard_package.git"
path = "leaderboard_pkg"
enabled = true
```

## Notes

- The package **only reads** the database — it writes nothing.
- `/leaderboard server` requires the bot to have the **Server Members Intent** enabled so it can resolve member lists. It will attempt to chunk the guild if not already cached.
- `Ball.enabled=True` is used to filter out disabled/hidden balls from the total count.
