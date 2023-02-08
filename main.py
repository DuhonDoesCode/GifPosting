import discord
from discord.ext import commands
from typing import Literal, Optional
from discord.ext.commands import Greedy, Context
import time
import sqlite3
import requests
import json
import topgg

dbl_token = "Top.gg token"

database = sqlite3.connect('gifposting.db')

lock = False

nonoWords = [
    'porn',
    'diives',
    'hentai',
    'ass',
    'twerk',
    'dick',
    'tenor',
    'nigga',
    'nigger',
    'fag',
    'faggot',
    'retard',
    'retarded'
]

f = open("nono.txt", 'r')
tmp = f.readlines()
nonoWords.extend(tmp)

nonoWords2 = []

for i in nonoWords:
    if '\n' in i:
        i = i.strip('\n')
    nonoWords2.append(i)

nonoWords = nonoWords2

f = open("tenorkey.txt", "r")
tenor_key = f.read()
f.close()
f = open("tenorckey.txt","r")
ckey = f.read()
f.close()
lmt = 1

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True

        super().__init__(command_prefix=commands.when_mentioned_or('$'), intents=intents)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = Bot()

# Tree syncer
@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
  ctx: Context, guilds: Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@bot.tree.command()
@discord.app_commands.checks.has_permissions(administrator=True)
async def reaction(interaction: discord.Interaction, emote: str):
    cur = database.cursor()
    guild = interaction.guild_id
    try:
        l = cur.execute(f'SELECT id FROM idlist')
        l = l.fetchall()
        l = [i[0] for i in l]
        if guild not in l:
            int("s")
        cur.execute(f'UPDATE idlist SET emote=? WHERE id=?', (emote, guild,))
        database.commit()
    except:
        cur.execute(f'INSERT INTO idlist VALUES(?, ?)', (guild, emote))
        database.commit()
    
    await interaction.response.send_message(f"Successfully edited your server's gif search reaction to be {emote}")

@bot.tree.command()
async def howto(interaction: discord.Interaction):
    await interaction.response.send_message("To use the bot, first set a guild-wide reaction to be the trigger for the functionality, namely a gif being picked and posted. To do so use /reaction <emote> with <emote> being a Discord emote.\nThe bot has a 1 second hard cooldown on the api seeing as it has a rate limit of 1 request/second.\nTo toggle lock of the bot do /shut (useful in case people are spamming/server is being raided).\nIn order to allow a user to use the gif function, please give them a role simply called 'gif-allow'. This should only be given to trusted members as tenor can get spammy.\nTo use the bot simply react to a message in the chat with the set emote of the server and shortly a gif fetched from Tenor will be sent, based on the message text (it literally just searches the messages and posts the top gif).")


# Will only be for voters
@bot.tree.command()
async def leaderboard(interaction: discord.Interaction):
    cur = database.cursor()
    emoteList = cur.execute("SELECT emote FROM idlist")
    emoteList = emoteList.fetchall()
    emoteSet = set(emoteList)
    leaderboardDict = {}
    for i in emoteSet:
        tmp = {i[0]: emoteList.count(i)}
        leaderboardDict.update(tmp)
    
    sortedLeaderboard = sorted(leaderboardDict.items(), key=lambda x:x[1], reverse=True)
    leaderboardDict = dict(sortedLeaderboard)
    s = ""
    for i, emote in enumerate(leaderboardDict.keys()):
        s += f"{i + 1}. {emote} with {leaderboardDict[emote]}\n"
    await interaction.response.send_message(s, ephemeral=True)

@bot.tree.command()
async def optout(interaction: discord.Interaction):
    cur = database.cursor()
    uid = interaction.user.id
    try:
        tmp = cur.execute(f'SELECT opt FROM optout WHERE id=?', (uid,))
        tmp = tmp.fetchone()
        tmp = tmp[0]
        print(tmp)
        if tmp:
            set_to = 0
        else:
            set_to = 1
        cur.execute(f'UPDATE optout SET opt=? WHERE id=?', (set_to, uid,))
    except:
        cur.execute(f'INSERT INTO optout VALUES(?, ?)', (uid, 0))
        tmp = cur.execute(f'SELECT opt FROM optout WHERE id=?', (uid,))
        tmp = tmp.fetchone()[0]
        if tmp:
            set_to = 0
        else:
            set_to = 1
    database.commit()
    await interaction.response.send_message(f"Toggled your opt-out status (now is {bool(set_to)}), so your messages won't/will be gif'd. To toggle it back, use the command again.", ephemeral=True)

# Will be allowed only for voters
@bot.tree.command()
async def search(interaction: discord.Interaction, query: str):
    global lock
    if lock: # Doesn't do anything if its locked.
        return
    message_check = query.split()
    for i in message_check:
        if i in nonoWords:
            return
    r = requests.get(
        "https://tenor.googleapis.com/v2/search?q=%s&key=%s&client_key=%s&limit=%s" %(query, tenor_key, ckey, lmt))
    if r.status_code == 200:
            # load the GIFs using the urls for the smaller GIF sizes
        top_8gifs = json.loads(r.content)['results'][0]['itemurl']
    else:
        print(r.status_code)
        top_8gifs = "Didn't find anything in Tenor, please try something else."
    time.sleep(1) # Necessary seeing as the Tenor api has a hard 1 request a second rate limit.
    await interaction.response.send_message(f"{top_8gifs}", ephemeral=True)

@bot.event
async def on_raw_reaction_add(reaction):
    global lock
    if lock: # Doesn't do anything if its locked.
        return
    member = reaction.member
    cur = database.cursor()
    guild = reaction.guild_id
    serv = bot.get_guild(guild)
    role = discord.utils.find(lambda r: r.name == 'gif-allow', serv.roles)
    if role not in member.roles:
        return
    emote = cur.execute(f'SELECT emote FROM idlist WHERE id=?', [guild])
    emote = emote.fetchone()[0]
    channel = bot.get_channel(reaction.channel_id)
    message_obj = await channel.fetch_message(reaction.message_id)
    uid = message_obj.author.id
    opt = cur.execute(f"SELECT opt FROM optout WHERE id=?", [uid])
    opt = opt.fetchone()
    opt = opt[0]
    try:
        if opt == 0:
            return
    except:
        pass
    message = message_obj.content
    message_check = message.split()
    for i in message_check:
        if i in nonoWords:
            return
    if emote is None:
        return
    if emote == reaction.emoji.name:
        r = requests.get(
            "https://tenor.googleapis.com/v2/search?q=%s&key=%s&client_key=%s&limit=%s" %(message, tenor_key, ckey, lmt))
        if r.status_code == 200:
            # load the GIFs using the urls for the smaller GIF sizes
            top_8gifs = json.loads(r.content)['results'][0]['itemurl']
        else:
            print(r.status_code)
            top_8gifs = "Didn't find anything in Tenor, please try something else."
        time.sleep(1) # Necessary seeing as the Tenor api has a hard 1 request a second rate limit.
        await channel.send(f"{top_8gifs}")

@bot.tree.command()
@discord.app_commands.checks.has_permissions(manage_messages=True)
async def shut(interaction: discord.Interaction):
    global lock
    lock = not lock
    await interaction.response.send_message("Locked/unlocked the bot.")

f = open("secret.txt", "r")
TOKEN = f.read()
f.close()

bot.run(TOKEN)