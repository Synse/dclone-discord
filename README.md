# dclone-discord

![](https://img.shields.io/badge/version-0.9-blue)

A Discord bot for reporting [DClone Tracker](https://diablo2.io/dclonetracker.php) progress changes and upcoming [planned walks](https://d2runewizard.com/diablo-clone-tracker#planned-walks) for Diablo 2: Resurrected. By default it will report any progress changes at or above level 2 for All Regions, Ladder and Non-Ladder, Softcore and planned walks an hour before they start.

You can also get the current progress for tracked regions and planned walks by typing `.dclone` or `!dclone` in chat.

## Usage

Requires Python 3.6+, tested on Linux.

### Installation

```
git clone https://github.com/Synse/dclone-discord.git
cd dclone-discord
pip3 install -r requirements.txt
```

### Configuration

Configuration is done via environment variables, or you can edit the variables near the top of the script.

**Required**
 - `DCLONE_DISCORD_TOKEN`: Token for connecting to Discord, create a bot account with the instructions [here](https://discordpy.readthedocs.io/en/stable/discord.html). Only the `Send Messages` permission is required.
 - `DCLONE_DISCORD_CHANNEL_ID`: The [channel id](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-) to send messages to.

**Optional**
 - `DCLONE_REGION`: `1` for Americas, `2` for Europe, `3` for Asia, blank **(Default)** for All Regions.
 - `DCLONE_LADDER`: `1` for Ladder, `2` for Non-Ladder, blank **(Default)** for both.
 - `DCLONE_HC`: `1` for Harcore, `2` for Softcore **(Default)**, blank for both.
 - `DCLONE_THRESHOLD`: Progress level to report at (and above). Default is 2.
 - `DCLONE_REPORTS`: Only report changes after this many reports agree on a change. Default is 3.

### Running

Start the bot with `python3 dclone_discord.py`.

## Disclaimer

Data courtesy of [diablo2.io](https://diablo2.io/dclonetracker.php) and [d2runewizard.com](https://d2runewizard.com/diablo-clone-tracker).
