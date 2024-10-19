import copy
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Dictionary to track active parties. Key is the party creator's ID, value is a list of members in the party.
active_parties = {}
members_party_dict = {}
# int : int
# player : party leader


def get_party_options(character_dict: dict):
    message = ""
    for i in character_dict:
        if character_dict[i]['wanted'] > 0:
            message += f"{i.capitalize()} : {len(character_dict[i]['players'])}/{
                character_dict[i]['wanted']}\n"

    return message


def leave_party_dict(user_id: int):

    leader_id = members_party_dict.get(user_id, None)

    if leader_id is None:
        return False, None

    if leader_id == user_id:
        return False, leader_id

    party = active_parties[leader_id]
    for character in party['character_list']:
        if user_id in party['character_list'][character]['players']:
            party['character_list'][character]['players'].remove(user_id)
            break
    party['current_members'] -= 1

    del members_party_dict[user_id]

    return True, leader_id


class LeavePartyButton(Button):
    def __init__(self):
        super().__init__(label="Leave Party", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        # print(0)
        # print(members_party_dict)
        # print(active_parties)

        leaved, leader_id = leave_party_dict(user.id)
        # print(1)
        # print(members_party_dict)
        # print(active_parties)
        if not leaved:
            leader = members_party_dict.get(user.id, None)
            if leader is None:
                await interaction.response.send_message(f"{user.mention}, you are not currently in a party.", ephemeral=True)
            elif leader == user.id:
                await interaction.response.send_message(f"{user.mention}, you are the party leader! Use /disband-party instead!", ephemeral=True)
            return

        party_leader = await bot.fetch_user(leader_id)
        await interaction.response.send_message(f"{user.mention}, you have left {party_leader.display_name}'s party.", ephemeral=True)

        # remove permissions
        text_channel = bot.get_channel(active_parties[leader_id]['text'])
        voice_channel = bot.get_channel(active_parties[leader_id]['voice'])
        category = bot.get_channel(active_parties[leader_id]['category'])

        await text_channel.set_permissions(user, read_messages=False, send_messages=False)
        await voice_channel.set_permissions(user, read_messages=False, connect=False)
        await category.set_permissions(user, read_messages=False, send_messages=False)

        await text_channel.send(f"{user.mention} has left the party. \n{active_parties[leader_id]['current_members']}/{active_parties[leader_id]['max_members']} total players.")

        # Edit original message
        character_dict = active_parties[leader_id]['character_list']
        message = f"Join {party_leader.mention}'s party!\n"
        message += get_party_options(character_dict)
        edited_message = await interaction.channel.fetch_message(active_parties[leader_id]['message_id'])
        await edited_message.edit(content=message)

class LeavePartyView(View):
    def __init__(self):
        super().__init__()

        self.timeout = None
        self.add_item(LeavePartyButton())


class JoinToonSelect(Select):
    def __init__(self, character_dict, party_owner: int):
        super().__init__()
        self.placeholder = 'Pick your toon!'
        options = []
        for i in character_dict:
            if character_dict[i]['wanted'] > 0 and len(character_dict[i]['players']) < character_dict[i]['wanted']:
                options.append(discord.SelectOption(label=i))

        self.options = options
        self.party_owner = party_owner

    async def callback(self, interaction: discord.Interaction):
        # Assume character_selected has selected a valid character
        character_selected = self.values[0]

        # Disable Select
        self.disabled = True
        await interaction.response.edit_message(content=f'You selected {character_selected.capitalize()}!', view=self.view)

        # Add user to party
        active_parties[self.party_owner]['current_members'] += 1
        character_dict = active_parties[self.party_owner]['character_list']
        character_dict[character_selected]['players'].append(
            interaction.user.id)
        members_party_dict[interaction.user.id] = self.party_owner

        # Grant permissions to user for channels
        text_channel = bot.get_channel(
            active_parties[self.party_owner]['text'])
        voice_channel = bot.get_channel(
            active_parties[self.party_owner]['voice'])

        await text_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await voice_channel.set_permissions(interaction.user, connect=True, speak=True)

        await text_channel.send(f"{interaction.user.mention} has joined the party as {character_selected.capitalize()}!\n{active_parties[self.party_owner]['current_members']}/{active_parties[self.party_owner]['max_members']} total players @here")

        # Edit the original party view message
        party_leader = await bot.fetch_user(self.party_owner)
        message = f"Join {party_leader.mention}'s party!\n"
        message += get_party_options(character_dict)
        edited_message = await interaction.channel.fetch_message(active_parties[self.party_owner]['message_id'])
        await edited_message.edit(content=message)
        
        view = LeavePartyView()
        await interaction.followup.send(f"{interaction.user.mention}, click the button below if you want to leave the party.", view=view, ephemeral=True)


class JoinPartyButton(Button):
    def __init__(self, party_owner: int):
        super().__init__(label="Join Party", style=discord.ButtonStyle.primary)
        self.party_owner = party_owner  # Store the ID of the party creator

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        party_dict = active_parties.get(self.party_owner, None)
        if party_dict is None:
            await interaction.response.send_message("Sorry! This party has already been disbanded.", ephemeral=True)
            return

        # check if user is already in party
        current_party = members_party_dict.get(user.id, None)
        if current_party == self.party_owner:
            await interaction.response.send_message(f"{user.mention}, you are already in the party!", ephemeral=True)
            return
        elif current_party is not None:
            await interaction.response.send_message(f"{user.mention}, you are already in another party! Use /leave-party to leave your current party.", ephemeral=True)
            return

        if party_dict['current_members'] >= party_dict['max_members']:
            await interaction.response.send_message("This party is full already!", ephemeral=True)
            return

        character_dict = active_parties[self.party_owner]['character_list']
        view = View()
        view.add_item(JoinToonSelect(character_dict, self.party_owner))
        party_owner_user = await bot.fetch_user(self.party_owner)

        message = f"Join {party_owner_user.display_name}'s party!\n"
        message += get_party_options(character_dict)
        await interaction.response.send_message(message, ephemeral=True, view=view)


class PartyView(View):
    def __init__(self, party_owner: int):
        super().__init__()
        # Add the "Join Party" button
        self.add_item(JoinPartyButton(party_owner=party_owner))
        self.timeout = None


async def create_party_channels(guild: discord.Guild, party_leader: discord.User):
    # Create a new category
    category = await guild.create_category(party_leader.display_name + "'s Party")
    active_parties[party_leader.id]['category'] = category.id

    # Create a text channel and a voice channel in that category
    text_channel = await guild.create_text_channel("party-text", category=category)
    voice_channel = await guild.create_voice_channel("party-voice", category=category)
    active_parties[party_leader.id]['text'] = text_channel.id
    active_parties[party_leader.id]['voice'] = voice_channel.id

    # Set permissions so only party members have access
    await text_channel.set_permissions(party_leader, read_messages=True, send_messages=True)
    await voice_channel.set_permissions(party_leader, connect=True, speak=True)

    await text_channel.set_permissions(bot.user, read_messages=True, send_messages=True)
    await voice_channel.set_permissions(bot.user, read_messages=True, connect=True)
    await category.set_permissions(bot.user, read_messages=True, send_messages=True)

    await text_channel.send("Party created! Voice and text channels are ready!" + party_leader.mention)

    # Remove permissions for @everyone
    await text_channel.set_permissions(guild.default_role, read_messages=False)
    await voice_channel.set_permissions(guild.default_role, connect=False)


class LeaderToonSelect(Select):
    def __init__(self, character_dict):
        super().__init__()
        self.placeholder = 'Pick your toon!'
        options = []
        for i in character_dict:
            if character_dict[i]['wanted'] > 0 and len(character_dict[i]['players']) < character_dict[i]['wanted']:
                options.append(discord.SelectOption(label=i))

        self.options = options
        self.character_dict = character_dict

    async def callback(self, interaction: discord.Interaction):
        character_dict = active_parties[interaction.user.id]['character_list']
        character_selected = self.values[0]

        # Disable Select
        self.disabled = True
        await interaction.response.edit_message(content=f'You selected {character_selected.capitalize()}!', view=self.view)

        # Add player to party
        character_dict[character_selected]['players'].append(
            interaction.user.id)
        active_parties[interaction.user.id]['current_members'] += 1
        members_party_dict[interaction.user.id] = interaction.user.id

        message = f"Join {interaction.user.mention}'s party!\n"
        message += get_party_options(character_dict)

        await create_party_channels(interaction.guild, interaction.user)

        message = await interaction.followup.send(message, view=PartyView(interaction.user.id))
        active_parties[interaction.user.id]['message_id'] = message.id
        self.view.stop()


class LeaderToonSelectView(View):
    def __init__(self, character_dict, party_owner: int):
        super().__init__()
        self.add_item(LeaderToonSelect(character_dict))
        self.party_owner = party_owner

    # TODO RESOLVE TIMEOUT
    def on_timeout(self):
        del active_parties[self.party_owner]
        return
    

# @bot.tree.command(name="testfunc", description="test function REMOVE LATER")
# async def testfunc(interaction: discord.Interaction):
#     global active_parties
#     import pprint

#     pprint.pprint(active_parties)
#     await bot.get_channel(active_parties[interaction.user.id]['text']).delete()
#     await bot.get_channel(active_parties[interaction.user.id]['voice']).delete()
#     await bot.get_channel(active_parties[interaction.user.id]['category']).delete()
#     # print(active_parties)

    # await interaction.response.send_message("HI")

@bot.tree.command(name="leave-party", description="Leave your current party.")
async def leave_party(interaction: discord.Interaction):
    await interaction.response.send_message("Click the button below to leave your current party if you are in one.", view=LeavePartyView(), ephemeral=True)

class DisbandButton(Button):
    def __init__(self):
        super().__init__(label="Disband Party", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if active_parties.get(interaction.user.id) is None:
            await interaction.response.send_message("You are not currently hosting any parties.", ephemeral=True)
            return
        
        character_dict = active_parties[interaction.user.id]['character_list']
        
        # clear players in party
        for character in character_dict:
            if len(character_dict[character]['players']) > 0:
                list_players = character_dict[character]['players']
                for player in list_players:
                    del members_party_dict[player]
        
        # Delete channels
        if active_parties[interaction.user.id].get('text') is not None:
            text = bot.get_channel(active_parties[interaction.user.id]['text'])
            if text is not None:
                await text.delete()

        if active_parties[interaction.user.id].get('voice') is not None:
            voice = bot.get_channel(active_parties[interaction.user.id]['voice'])
            if voice is not None:
                await voice.delete()
        
        if active_parties[interaction.user.id].get('category') is not None:
            category = bot.get_channel(active_parties[interaction.user.id]['category'])
            if category is not None:
                await category.delete()
        
        del active_parties[interaction.user.id]
        await interaction.response.send_message("Successfully disbanded party.", ephemeral=True)
           

class DisbandView(View):
    def __init__(self):
        super().__init__()

        self.timeout = None
        self.add_item(DisbandButton())

@bot.tree.command(name="disband-party", description="Disband your current party.")
async def disband_party(interaction: discord.Interaction):
    await interaction.response.send_message("Click the button below to disband your party if you have one.", view=DisbandView(), ephemeral=True)


@bot.tree.command(name="create-party", description="Start a party, include all the toons you want in your party (including yourself!)")
async def create_party(interaction: discord.Interaction, any: int = 0, astro: int = 0, boxten: int = 0, brightney: int = 0, cosmo: int = 0, finn: int = 0, flutter: int = 0, gigi: int = 0, glisten: int = 0, goob: int = 0,
                       pebble: int = 0, poppy: int = 0, razzledazzle: int = 0, rodger: int = 0, scraps: int = 0, shelly: int = 0, shrimpo: int = 0, sprout: int = 0, teagan: int = 0, tisha: int = 0, toodles: int = 0, vee: int = 0):

    # Check if the party creator already has an active party
    if interaction.user.id in active_parties:
        await interaction.response.send_message(f"{interaction.user.mention}, you already have an active party! Run /disband-party to disband your party!", ephemeral=True)
        return

    # Create character dictionary of needed/have
    character_dict = {
        'any toon': {'wanted': any, 'players': []}, 'astro': {'wanted': astro, 'players': []},
        'boxten': {'wanted': boxten, 'players': []}, 'brightney': {'wanted': brightney, 'players': []},
        'cosmo': {'wanted': cosmo, 'players': []}, 'finn': {'wanted': finn, 'players': []},
        'flutter': {'wanted': flutter, 'players': []}, 'gigi': {'wanted': gigi, 'players': []},
        'glisten': {'wanted': glisten, 'players': []}, 'goob': {'wanted': goob, 'players': []},
        'pebble': {'wanted': pebble, 'players': []}, 'poppy': {'wanted': poppy, 'players': []},
        'razzledazzle': {'wanted': razzledazzle, 'players': []}, 'rodger': {'wanted': rodger, 'players': []},
        'scraps': {'wanted': scraps, 'players': []}, 'shelly': {'wanted': shelly, 'players': []},
        'shrimpo': {'wanted': shrimpo, 'players': []}, 'sprout': {'wanted': sprout, 'players': []},
        'teagan': {'wanted': teagan, 'players': []}, 'tisha': {'wanted': tisha, 'players': []},
        'toodles': {'wanted': toodles, 'players': []}, 'vee': {'wanted': vee, 'players': []}
    }

    # Basic error checks
    total_characters = 0
    for i in character_dict:
        if character_dict[i]['wanted'] < 0:
            await interaction.response.send_message("You must have between 0-8 for every toon!", ephemeral=True)
            return
        total_characters += character_dict[i]['wanted']

    if total_characters <= 1:
        await interaction.response.send_message("You must have at least two toons!", ephemeral=True)
        return

    if total_characters > 8:
        await interaction.response.send_message("You can't have more than eight total toons!", ephemeral=True)
        return

    # Initialize a new party for the user
    active_parties[interaction.user.id] = {'character_list': character_dict}
    active_parties[interaction.user.id]['current_members'] = 0
    active_parties[interaction.user.id]['max_members'] = total_characters

    await interaction.response.send_message("Select your toon!", view=LeaderToonSelectView(character_dict, interaction.user.id), ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync slash commands
    print(f'Logged in as {bot.user}')


bot.run(os.getenv('TOKEN'))
