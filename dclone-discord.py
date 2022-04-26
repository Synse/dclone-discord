#!/usr/bin/env python3
# Discord Bot for tracking DClone - https://github.com/Synse/discord-dclone
from discord.ext import tasks
from os import environ
from requests import get
from time import time
import discord

#####################
# Bot Configuration #
#####################
# Setting environment variables is preferred, but you can also edit the variables below.

# Discord
DISCORD_TOKEN = environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(environ.get('DISCORD_CHANNEL_ID'))

# DClone tracker API
# Defaults to All Regions, Non-Ladder, Softcore
DCLONE_REGION = environ.get('DCLONE_REGION', '')  # 1 for Americas, 2 for Europe, 3 for Asia, blank for all
DCLONE_LADDER = environ.get('DCLONE_LADDER', '2')  # 1 for Ladder, 2 for Non-Ladder, blank for all
DCLONE_HC = environ.get('DCLONE_HC', '2')  # 1 for Hardcore, 2 for Softcore, blank for all

# Bot specific
# Defaults to alerting at level 2 if the progress has been at this level for at least 120 seconds
DCLONE_THRESHOLD = int(environ.get('DCLONE_THRESHOLD', 2))  # progress level to alert at (and above)
DCLONE_DELAY = int(environ.get('DCLONE_DELAY', 120))  # delay reports by this many seconds to reduce trolling

########################
# End of configuration #
########################
__version__ = '0.1'
REGION = {'1': 'Americas', '2': 'Europe', '3': 'Asia', '': 'All Regions'}
LADDER = {'1': 'Ladder', '2': 'Non-Ladder', '': 'Hardcore and Softcore'}
HC = {'1': 'Hardcore', '2': 'Softcore', '': 'Ladder and Non-Ladder'}

# DISCORD_TOKEN and DISCORD_CHANNEL_ID are required
if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
    print('Please set DISCORD_TOKEN and DISCORD_CHANNEL_ID in your environment.')
    exit(1)


class DCloneTracker():
    def __init__(self):
        # Progress is tracked by the tuple (region, ladder, hc) and assumed to be 1 when the bot starts
        # TODO: update this cache before the first run to reduce noise on bot restarts
        self.progress_cache = {
            ('1', '1', '1'): 1,  # Americas, Ladder, Hardcore
            ('1', '1', '2'): 1,  # Americas, Ladder, Softcore
            ('1', '2', '1'): 1,  # Americas, Non-Ladder, Hardcore
            ('1', '2', '2'): 1,  # Americas, Non-Ladder, Softcore
            ('2', '1', '1'): 1,  # Europe, Ladder, Hardcore
            ('2', '1', '2'): 1,  # Europe, Ladder, Softcore
            ('2', '2', '1'): 1,  # Europe, Non-Ladder, Hardcore
            ('2', '2', '2'): 1,  # Europe, Non-Ladder, Softcore
            ('3', '1', '1'): 1,  # Asia, Ladder, Hardcore
            ('3', '1', '2'): 1,  # Asia, Ladder, Softcore
            ('3', '2', '1'): 1,  # Asia, Non-Ladder, Hardcore
            ('3', '2', '2'): 1,  # Asia, Non-Ladder, Softcore
        }

    def get_dclone_status(self, region='', ladder='', hc=''):
        """
        Get the current dclone status from the diablo2.io dclone public API.

        Docs: https://diablo2.io/post2417121.html
        """
        try:
            url = 'https://diablo2.io/dclone_api.php'
            params = {'region': region, 'ladder': ladder, 'hc': hc}
            headers = {'User-Agent': f'dclone-discord/{__version__}'}
            response = get(url, params=params, headers=headers)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f'DClone Tracker API Error: {e}')
            return None


class DiscordClient(discord.Client):
    """
    Connects to Discord and starts a background task that checks the diablo2.io dclone API every 60 seconds.
    When a progress change occurs that is greater than or equal to DCLONE_THRESHOLD and more than DCLONE_DELAY
    seconds old, the bot will send a message to the configured DISCORD_CHANNEL_ID.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dclone = DCloneTracker()
        print(f'Tracking DClone for {REGION[DCLONE_REGION]}, {LADDER[DCLONE_LADDER]}, {HC[DCLONE_HC]}')

    async def on_ready(self):
        print(f'Bot logged into Discord as {self.user}')
        self.check_dclone_status.start()

    # async def on_message(self, message):
    #     print('>> Message from {0.author}: {0.content}'.format(message))

    @tasks.loop(seconds=60)
    async def check_dclone_status(self):
        """
        Background task that checks dclone status via the diablo2.io dclone public API every 60 seconds.

        Status changes are compared to the last known status and a message is sent to Discord if the status changed.
        """
        # print('>> Checking DClone Status...')
        status = self.dclone.get_dclone_status()
        if not status:
            return

        # loop through each region and check for progress changes
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hc = data.get('hc')
            progress = int(data.get('progress'))

            progress_was = self.dclone.progress_cache.get((region, ladder, hc))
            updated_ago = int(time() - int(data.get('timestamped')))

            # handle progress changes
            if int(progress) >= DCLONE_THRESHOLD and progress > progress_was and updated_ago >= DCLONE_DELAY:
                print(f'{REGION[region]} {LADDER[ladder]} {HC[hc]} is now {progress}/6 (was {progress_was}/6) -- {updated_ago} seconds ago')

                # post to discord
                message = f'[{progress}/6] **{REGION[region]} {LADDER[ladder]} {HC[hc]}** DClone progressed'
                message += '\n> Data courtesy of diablo2.io'
                channel = self.get_channel(DISCORD_CHANNEL_ID)
                await channel.send(message)

                # update our cache (last status change)
                self.dclone.progress_cache[(region, ladder, hc)] = progress
            elif progress < progress_was and progress == 1 and updated_ago >= DCLONE_DELAY:
                # we need to reset to 1 after a spawn; this will cause duplicate messages if someone
                # incorrectly sets progress to 1 and it stays for more than DCLONE_DELAY seconds
                print(f'{REGION[region]} {LADDER[ladder]} {HC[hc]} resetting to 1 after assumed spawn')
                self.dclone.progress_cache[(region, ladder, hc)] = progress
            elif progress != progress_was:
                # report suspicious progress changes, these are not sent to discord
                print(f'[Suspicious] {REGION[region]} {LADDER[ladder]} {HC[hc]} reported as {progress}/6 (was {progress_was}/6) -- {updated_ago} seconds ago')

    @check_dclone_status.before_loop
    async def before_check_dclone_status(self):
        await self.wait_until_ready()  # wait until the bot logs in


client = DiscordClient(intents=discord.Intents.default())
client.run(DISCORD_TOKEN)
