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


class JoinPartyButton(Button):
    def __init__(self, party_owner):
        super().__init__(label="Join Party", style=discord.ButtonStyle.primary)
        self.party_owner = party_owner  # Store the ID of the party creator

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        global active_parties

        party_members = active_parties.get(self.party_owner, [])

        if user.id in party_members:
            await interaction.response.send_message(f"{user.mention}, you are already in the party!", ephemeral=True)
        else:
            party_members.append(user.id)
            active_parties[self.party_owner] = party_members
            await interaction.response.send_message(f"{user.mention} has joined the party! ({len(party_members)}/8)", ephemeral=False)
            # channel = client.get_channel(12324234183172)
            # await channel.send('hello')

            # After joining, send a message with the "Leave Party" button
            view = LeavePartyView(self.party_owner)
            await interaction.followup.send(f"{user.mention}, click the button below if you want to leave the party.", view=view, ephemeral=True)

        # Once the party has 8 members, create channels and remove the party from the active list
        if len(party_members) == 8:
            await create_party_channels(interaction.guild, interaction.channel, party_members)
            # Remove the party from active parties
            del active_parties[self.party_owner]


class LeavePartyButton(Button):
    def __init__(self, party_owner):
        super().__init__(label="Leave Party", style=discord.ButtonStyle.danger)
        self.party_owner = party_owner  # Store the ID of the party creator

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        global active_parties

        party_members = active_parties.get(self.party_owner, [])

        # Handle leaving the party
        if user not in party_members:
            await interaction.response.send_message(f"{user.mention}, you are not in the party!", ephemeral=True)
        else:
            party_members.remove(user)
            active_parties[self.party_owner] = party_members
            await interaction.response.send_message(f"{user.mention} has left the party. ({len(party_members)}/8)", ephemeral=False)


class PartyView(View):
    def __init__(self, party_owner):
        super().__init__()
        # Add the "Join Party" button
        self.add_item(JoinPartyButton(party_owner=party_owner))


class LeavePartyView(View):
    def __init__(self, party_owner):
        super().__init__()
        # Add the "Leave Party" button
        self.add_item(LeavePartyButton(party_owner=party_owner))


async def create_party_channels(guild, channel, members):
    # Create a new category
    category = await guild.create_category("Party Room")

    # Create a text channel and a voice channel in that category
    text_channel = await guild.create_text_channel("party-text", category=category)
    voice_channel = await guild.create_voice_channel("party-voice", category=category)

    # Set permissions so only party members have access
    for member in members:
        await text_channel.set_permissions(member, read_messages=True, send_messages=True)
        await voice_channel.set_permissions(member, connect=True, speak=True)

    # Remove permissions for @everyone
    await text_channel.set_permissions(guild.default_role, read_messages=False)
    await voice_channel.set_permissions(guild.default_role, connect=False)

    await channel.send("Party created! Voice and text channels are ready!")


class ToonSelect(Select):
    def __init__(self, character_dict):
        super().__init__()
        self.placeholder = 'Pick your toon!'
        options = []
        for i in character_dict:
            if character_dict[i][1] > 0:
                options.append(discord.SelectOption(label=i))

        self.options = options
        self.character_dict = character_dict

    async def callback(self, interaction: discord.Interaction):
        selected_dict = copy.deepcopy(self.character_dict)
        message = f"Join {interaction.user.mention}'s party!\n"
        selected_dict[self.values[0]][0] +=1
        for i in selected_dict:
            if selected_dict[i][1] > 0:
                message += f"{i} : {selected_dict[i][0]}/{selected_dict[i][1]}\n"
        
        await interaction.response.send_message(message, view=PartyView(interaction.user.id))


class ToonSelectView(View):
    def __init__(self, character_dict):
        super().__init__()

        self.add_item(ToonSelect(character_dict))

# @bot.tree.command(name="testfunc", description="test function REMOVE LATER")
# async def testfunc(interaction: discord.Interaction):
#     await create_party_channels(interaction.guild, interaction.channel, [])
#     await interaction.response.send_message("HI")

@bot.tree.command(name="create-party", description="Start a party, include all the toons you want in your party (including yourself!)")
async def create_party(interaction: discord.Interaction, any: int = 0, astro: int = 0, boxten: int = 0, brightney: int = 0, cosmo: int = 0, finn: int = 0, flutter: int = 0, gigi: int = 0, glisten: int = 0, goob: int = 0,
                       pebble: int = 0, poppy: int = 0, razzledazzle: int = 0, rodger: int = 0, scraps: int = 0, shelly: int = 0, shrimpo: int = 0, sprout: int = 0, teagan: int = 0, tisha: int = 0, toodles: int = 0, vee: int = 0):
    global active_parties
    
    
    # Check if the party creator already has an active party
    if interaction.user.id in active_parties:
        await interaction.response.send_message(f"{interaction.user.mention}, you already have an active party! Run /disband-party to disband your party!", ephemeral=True)
        return
    
    # Create character dictionary of needed/have
    character_dict = {
        'any': [0,any], 'astro': [0,astro], 'boxten': [0,boxten], 'brightney': [0,brightney], 'cosmo': [0,cosmo], 'finn': [0,finn], 'flutter': [0,flutter], 'gigi': [0,gigi], 'glisten': [0,glisten], 'goob': [0,goob],
        'pebble': [0,pebble], 'poppy': [0,poppy], 'razzledazzle': [0,razzledazzle], 'rodger': [0,rodger], 'scraps': [0,scraps], 'shelly': [0,shelly], 'shrimpo': [0,shrimpo], 'sprout': [0,sprout], 'teagan': [0,teagan], 'tisha': [0,tisha], 'toodles': [0,toodles], 'vee': [0,vee]
    }
    
    # Basic error checks
    total_characters = 0
    for i in character_dict:
        if character_dict[i][1] < 0:
            await interaction.response.send_message("You must have between 0-8 for every toon!", ephemeral=True)
            return
        total_characters += character_dict[i][1]

    if total_characters <= 1:
        await interaction.response.send_message("You must have at least two toons!", ephemeral=True)
        return

    if total_characters > 8:
        await interaction.response.send_message("You can't have more than eight total toons!", ephemeral=True)
        return

    # Initialize a new party for the user
    active_parties[interaction.user.id] = [interaction.user.id]

    await interaction.response.send_message("Select your toon!", view=ToonSelectView(character_dict), ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()  # Sync slash commands
    print(f'Logged in as {bot.user}')


bot.run(os.getenv('TOKEN'))
