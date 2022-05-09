#!/usr/bin/env python3
# Discord Bot for tracking DClone - https://github.com/Synse/discord-dclone
from datetime import timedelta
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
# Defaults to alerting at level 2 if the last 3 progress reports match
DCLONE_THRESHOLD = int(environ.get('DCLONE_THRESHOLD', 2))  # progress level to alert at (and above)
DCLONE_REPORTS = int(environ.get('DCLONE_REPORTS', 3))  # number of matching reports required before alerting (reduces trolling)

########################
# End of configuration #
########################
__version__ = '0.3'
REGION = {'1': 'Americas', '2': 'Europe', '3': 'Asia', '': 'All Regions'}
LADDER = {'1': 'Ladder', '2': 'Non-Ladder', '': 'Ladder and Non-Ladder'}
HC = {'1': 'Hardcore', '2': 'Softcore', '': 'Hardcore and Softcore'}

# DISCORD_TOKEN and DISCORD_CHANNEL_ID are required
if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
    print('Please set DISCORD_TOKEN and DISCORD_CHANNEL_ID in your environment.')
    exit(1)


class DCloneTracker():
    def __init__(self):
        # Current progress (last reported) for each mode
        self.current_progress = {
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

        # Recent reports for each mode. These are truncated to DCLONE_REPORTS and alerts are sent if
        # all recent reports for a mode agree on the progress level. This reduces trolling but adds a small delay.
        self.report_cache = {
            ('1', '1', '1'): [1],  # Americas, Ladder, Hardcore
            ('1', '1', '2'): [1],  # Americas, Ladder, Softcore
            ('1', '2', '1'): [1],  # Americas, Non-Ladder, Hardcore
            ('1', '2', '2'): [1],  # Americas, Non-Ladder, Softcore
            ('2', '1', '1'): [1],  # Europe, Ladder, Hardcore
            ('2', '1', '2'): [1],  # Europe, Ladder, Softcore
            ('2', '2', '1'): [1],  # Europe, Non-Ladder, Hardcore
            ('2', '2', '2'): [1],  # Europe, Non-Ladder, Softcore
            ('3', '1', '1'): [1],  # Asia, Ladder, Hardcore
            ('3', '1', '2'): [1],  # Asia, Ladder, Softcore
            ('3', '2', '1'): [1],  # Asia, Non-Ladder, Hardcore
            ('3', '2', '2'): [1],  # Asia, Non-Ladder, Softcore
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

    def current_progress_message(self):
        """
        Returns a formatted message for the current dclone status by mode (region, ladder, hc).
        """
        # Get the current dclone status
        # TODO: Return from current_progress instead of querying the API every time
        status = self.get_dclone_status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hc=DCLONE_HC)
        status = sorted(status, key=lambda x: (x['region'], x['ladder'], x['hc']))
        if not status:
            return

        # Build a message for the current progress of each mode
        message = 'Current DClone Progress:\n'
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hc = data.get('hc')
            progress = int(data.get('progress'))
            ago = timedelta(seconds=int(time() - int(data.get('timestamped'))))

            message += f' - **{REGION[region]} {LADDER[ladder]} {HC[hc]}** is `{progress}/6` ({ago} ago)\n'
        message += '> Data provided by diablo2.io'

        return message

    def should_update(self, mode):
        """
        For a given game mode, returns True/False if we should post an alert to Discord.

        This checks for DCLONE_REPORTS number of matching progress reports which is intended to reduce trolling.
        A larger number for DCLONE_REPORTS will alert sooner but is more sucpeitible to trolling/false reports and
        a smaller number of DCLONE_REPORTS will alert later but is less susceptible to trolling/false reports.

        Since we're checking every 60 seconds any mode with the same progress report for 60*DCLONE_REPORTS seconds
        will also be reported as a change.
        """
        reports = self.report_cache[mode][-DCLONE_REPORTS:]
        self.report_cache[mode] = reports  # truncate recent reports

        # if the last DCLONE_REPORTS reports agree on the progress level, we should update
        if all(reports[0] == x for x in reports):
            return True
        else:
            return False


class DiscordClient(discord.Client):
    """
    Connects to Discord and starts a background task that checks the diablo2.io dclone API every 60 seconds.
    When a progress change occurs that is greater than or equal to DCLONE_THRESHOLD and for more than DCLONE_REPORTS
    consecutive updates, the bot will send a message to the configured DISCORD_CHANNEL_ID.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dclone = DCloneTracker()
        print(f'Tracking DClone for {REGION[DCLONE_REGION]}, {LADDER[DCLONE_LADDER]}, {HC[DCLONE_HC]}')

    async def on_ready(self):
        print(f'Bot logged into Discord as {self.user}')
        try:
            self.check_dclone_status.start()
        except RuntimeError as e:
            print(f'Background Task Error: {e}')

    async def on_message(self, message):
        """
        This is called any time the bot receives a message. It implements the dclone chatop.
        """
        if message.content.startswith('.dclone') or message.content.startswith('!dclone'):
            print(f'Responding to dclone chatop from {message.author}')
            current_status = self.dclone.current_progress_message()

            if current_status:
                channel = self.get_channel(message.channel.id)
                await channel.send(current_status)

    @tasks.loop(seconds=60)
    async def check_dclone_status(self):
        """
        Background task that checks dclone status via the diablo2.io dclone public API every 60 seconds.

        Status changes are compared to the last known status and a message is sent to Discord if the status changed.
        """
        # print('>> Checking DClone Status...')
        status = self.dclone.get_dclone_status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hc=DCLONE_HC)
        if not status:
            return

        # loop through each region and check for progress changes
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hc = data.get('hc')
            progress = int(data.get('progress'))

            progress_was = self.dclone.current_progress.get((region, ladder, hc))
            updated_ago = int(time() - int(data.get('timestamped')))

            # add the most recent report
            self.dclone.report_cache[(region, ladder, hc)].append(progress)

            # handle progress changes
            # TODO: bundle multiple changes into one message
            if int(progress) >= DCLONE_THRESHOLD and progress > progress_was and self.dclone.should_update((region, ladder, hc)):
                print(f'{REGION[region]} {LADDER[ladder]} {HC[hc]} is now {progress}/6 (was {progress_was}/6) -- {updated_ago} seconds ago')

                # post to discord
                message = f'[{progress}/6] **{REGION[region]} {LADDER[ladder]} {HC[hc]}** DClone progressed'
                message += '\n> Data courtesy of diablo2.io'
                channel = self.get_channel(DISCORD_CHANNEL_ID)
                await channel.send(message)

                # update current status
                self.dclone.current_progress[(region, ladder, hc)] = progress
            elif progress < progress_was and self.dclone.should_update((region, ladder, hc)):
                # progress increases are interesting, but we also need to reset to 1 after dclone spawns
                # and to roll it back if the new confirmed progress is less than the current progress
                print(f'[RollBack] {REGION[region]} {LADDER[ladder]} {HC[hc]} rolling back to {progress}')

                # if we believe dclone spawned, post to discord
                if progress == 1:
                    message = f'[{progress}/6] **{REGION[region]} {LADDER[ladder]} {HC[hc]}** DClone probably spawned less than {max(1,DCLONE_REPORTS)}m ago'
                    message += '\n> Data courtesy of diablo2.io'
                    channel = self.get_channel(DISCORD_CHANNEL_ID)
                    await channel.send(message)

                # update current status
                self.dclone.current_progress[(region, ladder, hc)] = progress
            elif progress != progress_was:
                # track suspicious progress changes, these are not sent to discord
                print(f'[Suspicious] {REGION[region]} {LADDER[ladder]} {HC[hc]} reported as {progress}/6 (currently {progress_was}/6) {updated_ago}s ago')

    @check_dclone_status.before_loop
    async def before_check_dclone_status(self):
        await self.wait_until_ready()  # wait until the bot logs in

        # get the current progress from the dclone API
        status = self.dclone.get_dclone_status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hc=DCLONE_HC)

        if not status:
            print('Unable to set the current progress at startup')
            return

        # set the current status and populate the report cache with this value
        # this prevents a duplicate message from being sent when the bot starts
        # we are assuming the report at startup is correct (not a troll/false report)
        # but this should be fine most of the time
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hc = data.get('hc')
            progress = int(data.get('progress'))

            # set current progress and report
            self.dclone.current_progress[(region, ladder, hc)] = progress
            if progress != 1:
                print(f'Progress for {REGION[region]} {LADDER[ladder]} {HC[hc]} starting at {progress}/6')

            # populate the report cache with DCLONE_REPORTS number of reports at this progress
            for x in range(0, DCLONE_REPORTS):
                self.dclone.report_cache[(region, ladder, hc)].append(progress)


client = DiscordClient(intents=discord.Intents.default())
client.run(DISCORD_TOKEN)
