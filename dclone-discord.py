#!/usr/bin/env python3
"""
A Discord Bot for tracking DClone spawns in Diablo 2: Resurrected - https://github.com/Synse/discord-dclone
Copyright (C) 2022 @Synse

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from os import environ
from time import time
from requests import get
from discord.ext import tasks
import discord

#####################
# Bot Configuration #
#####################
# Setting environment variables is preferred, but you can also edit the variables below.

# Discord (Required)
DISCORD_TOKEN = environ.get('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(environ.get('DISCORD_CHANNEL_ID'))

# DClone tracker API (Optional)
# Defaults to All Regions, Ladder and Non-Ladder, Softcore
DCLONE_REGION = environ.get('DCLONE_REGION', '')  # 1 for Americas, 2 for Europe, 3 for Asia, blank for all
DCLONE_LADDER = environ.get('DCLONE_LADDER', '')  # 1 for Ladder, 2 for Non-Ladder, blank for all
DCLONE_HC = environ.get('DCLONE_HC', '2')  # 1 for Hardcore, 2 for Softcore, blank for all

# Bot specific (Optional)
# Defaults to alerting at level 2 if the last 3 progress reports match
DCLONE_THRESHOLD = int(environ.get('DCLONE_THRESHOLD', 2))  # progress level to alert at (and above)
DCLONE_REPORTS = int(environ.get('DCLONE_REPORTS', 3))  # number of matching reports required before alerting (reduces trolling)

########################
# End of configuration #
########################
__version__ = '0.5'
REGION = {'1': ':flag_us: Americas', '2': ':flag_eu: Europe', '3': ':flag_kr: Asia', '': 'All Regions'}
LADDER = {'1': ':ladder: Ladder', '2': ':crossed_swords: Non-Ladder', '': 'Ladder and Non-Ladder'}
HC = {'1': ':skull_crossbones: Hardcore', '2': ':mage: Softcore', '': 'Hardcore and Softcore'}

# DISCORD_TOKEN and DISCORD_CHANNEL_ID are required
if not DISCORD_TOKEN or not DISCORD_CHANNEL_ID:
    print('Please set DISCORD_TOKEN and DISCORD_CHANNEL_ID in your environment.')
    exit(1)


class Diablo2IOClient():
    """
    Interacts with the diablo2.io dclone API. Tracks the current progress and recent reports for each mode.
    """
    def __init__(self):
        # Current progress (last alerted) for each mode
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
        # all recent reports for a mode agree on the progress level. This reduces trolling/false reports
        # but also increases the delay between a report and an alert.
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

    def status(self, region='', ladder='', hardcore=''):
        """
        Get the currently reported dclone status from the diablo2.io dclone API.

        API documentation: https://diablo2.io/post2417121.html

        :param region: region to get status for (1 for Americas, 2 for Europe, 3 for Asia, blank for all)
        :param ladder: ladder or non-ladder (1 for Ladder, 2 for Non-Ladder, blank for all)
        :param hardcore: hardcore or softcore (1 for Hardcore, 2 for Softcore, blank for all)
        :return: current dclone status as json
        """
        try:
            url = 'https://diablo2.io/dclone_api.php'
            params = {'region': region, 'ladder': ladder, 'hc': hardcore}
            headers = {'User-Agent': f'dclone-discord/{__version__}'}
            response = get(url, params=params, headers=headers, timeout=10)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f'[Diablo2IOClient.status] API Error: {e}')
            return None

    def progress_message(self):
        """
        Returns a formatted message of the current dclone status by mode (region, ladder, hc).
        """
        # Get the currently reported dclone status
        # TODO: Return from current_progress instead of querying the API every time?
        status = self.status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hardcore=DCLONE_HC)
        if not status:
            return '[Diablo2IOClient.progress_message] API error, please try again later.'

        # Sort the status by mode (region, ladder, hc)
        status = sorted(status, key=lambda x: (x['region'], x['ladder'], x['hc']))

        # Build the message
        message = 'Current DClone Progress:\n'
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hardcore = data.get('hc')
            progress = int(data.get('progress'))
            timestamped = int(data.get('timestamped'))

            message += f' - **{REGION[region]} {LADDER[ladder]} {HC[hardcore]}** is `{progress}/6` <t:{timestamped}:R>\n'
        message += '> Data provided by diablo2.io'

        return message

    def should_update(self, mode):
        """
        For a given game mode, returns True/False if we should post an alert to Discord.

        This checks for DCLONE_REPORTS number of matching progress reports which is intended to reduce trolling/false reports.
        A larger number for DCLONE_REPORTS will alert sooner (less delay) but is more susceptible to trolling/false reports and
        a smaller number of DCLONE_REPORTS will alert later (more delay) but is less susceptible to trolling/false reports.

        Since we're checking every 60 seconds any mode with the same progress report for 60*DCLONE_REPORTS seconds
        will also be reported as a change.

        :param mode: game mode (region, ladder, hc)
        :return: True/False if we should post an alert to Discord
        """
        reports = self.report_cache[mode][-DCLONE_REPORTS:]
        self.report_cache[mode] = reports  # truncate recent reports

        # if the last DCLONE_REPORTS reports agree on the progress level, we should update
        if all(reports[0] == x for x in reports):
            return True

        return False


class DiscordClient(discord.Client):
    """
    Connects to Discord and starts a background task that checks the diablo2.io dclone API every 60 seconds.
    When a progress change occurs that is greater than or equal to DCLONE_THRESHOLD and for more than DCLONE_REPORTS
    consecutive updates, the bot will send a message to the configured DISCORD_CHANNEL_ID.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.dclone = Diablo2IOClient()
        print(f'Tracking DClone for {REGION[DCLONE_REGION]}, {LADDER[DCLONE_LADDER]}, {HC[DCLONE_HC]}')

    async def on_ready(self):
        """
        Runs when the bot is connected to Discord and ready to receive messages. This starts our background task.
        """
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
            current_status = self.dclone.progress_message()

            channel = self.get_channel(message.channel.id)
            await channel.send(current_status)

    @tasks.loop(seconds=60)
    async def check_dclone_status(self):
        """
        Background task that checks dclone status via the diablo2.io dclone public API every 60 seconds.

        Status changes are compared to the last known status and a message is sent to Discord if the status changed.
        """
        # print('>> Checking DClone Status...')
        status = self.dclone.status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hardcore=DCLONE_HC)
        if not status:
            return

        # loop through each region and check for progress changes
        for data in status:
            region = data.get('region')
            ladder = data.get('ladder')
            hardcore = data.get('hc')
            progress = int(data.get('progress'))
            reporter_id = data.get('reporter_id')

            progress_was = self.dclone.current_progress.get((region, ladder, hardcore))
            updated_ago = int(time() - int(data.get('timestamped')))

            # add the most recent report
            self.dclone.report_cache[(region, ladder, hardcore)].append(progress)

            # handle progress changes
            # TODO: bundle multiple changes into one message
            if int(progress) >= DCLONE_THRESHOLD and progress > progress_was and self.dclone.should_update((region, ladder, hardcore)):
                print(f'{REGION[region]} {LADDER[ladder]} {HC[hardcore]} is now {progress}/6 (was {progress_was}/6) ' +
                      f'-- {updated_ago} seconds ago (reporter_id: {reporter_id})')

                # post to discord
                message = f'[{progress}/6] **{REGION[region]} {LADDER[ladder]} {HC[hardcore]}** DClone progressed (reporter_id: {reporter_id})'
                message += '\n> Data courtesy of diablo2.io'

                channel = self.get_channel(DISCORD_CHANNEL_ID)
                await channel.send(message)

                # update current status
                self.dclone.current_progress[(region, ladder, hardcore)] = progress
            elif progress < progress_was and self.dclone.should_update((region, ladder, hardcore)):
                # progress increases are interesting, but we also need to reset to 1 after dclone spawns
                # and to roll it back if the new confirmed progress is less than the current progress
                print(f'[RollBack] {REGION[region]} {LADDER[ladder]} {HC[hardcore]} rolling back to {progress} (reporter_id: {reporter_id})')

                # if we believe dclone spawned, post to discord
                if progress == 1:
                    message = ':japanese_ogre: :japanese_ogre: :japanese_ogre: '
                    message += f'[{progress}/6] **{REGION[region]} {LADDER[ladder]} {HC[hardcore]}** DClone may have spawned (reporter_id: {reporter_id})'
                    message += '\n> Data courtesy of diablo2.io'

                    channel = self.get_channel(DISCORD_CHANNEL_ID)
                    await channel.send(message)

                # update current status
                self.dclone.current_progress[(region, ladder, hardcore)] = progress
            elif progress != progress_was:
                # track suspicious progress changes, these are not sent to discord
                print(f'[Suspicious] {REGION[region]} {LADDER[ladder]} {HC[hardcore]} reported as {progress}/6 ' +
                      f'(currently {progress_was}/6) {updated_ago}s ago (reporter_id: {reporter_id})')

    @check_dclone_status.before_loop
    async def before_check_dclone_status(self):
        """
        Runs before the background task starts. This waits for the bot to connect to Discord and sets the initial dclone status.
        """
        await self.wait_until_ready()  # wait until the bot logs in

        # get the current progress from the dclone API
        status = self.dclone.status(region=DCLONE_REGION, ladder=DCLONE_LADDER, hardcore=DCLONE_HC)

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
            hardcore = data.get('hc')
            progress = int(data.get('progress'))
            reporter_id = data.get('reporter_id')

            # set current progress and report
            self.dclone.current_progress[(region, ladder, hardcore)] = progress
            if progress != 1:
                print(f'Progress for {REGION[region]} {LADDER[ladder]} {HC[hardcore]} starting at {progress}/6 (reporter_id: {reporter_id})')

            # populate the report cache with DCLONE_REPORTS number of reports at this progress
            for _ in range(0, DCLONE_REPORTS):
                self.dclone.report_cache[(region, ladder, hardcore)].append(progress)


client = DiscordClient(intents=discord.Intents.default())
client.run(DISCORD_TOKEN)
