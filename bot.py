import discord
from discord import app_commands
from discord.ext import commands
import os
import random
import asyncio
import aiohttp
import yt_dlp
import io
import base64
from typing import Optional, List
from yt_dlp import YoutubeDL
import sys
from games import TicTacToe, Hangman, GuessTheNumber, Battleship
from PIL import Image
from io import BytesIO
import json
import ollama

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded .env file successfully")
except ImportError:
    print("Warning: python-dotenv not installed, using system environment variables only")

# Get environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("No DISCORD_TOKEN found in environment variables. Please set it in Render's dashboard.")

# Log environment info (for debugging)
print("Starting bot with the following environment:")
print(f"- Python: {sys.version}")
print(f"- discord.py: {discord.__version__}")
print(f"- Bot user: {os.getenv('BOT_USERNAME', 'Not set')}")
print("-" * 40)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Owner IDs (can bypass all restrictions)
OWNER_IDS = {
    1304359498919444557,  # Original owner
    1329161792936476683,  # Additional owner 1
    903569932791463946    # Additional owner 2
}

def is_owner():
    """Check if the user is a bot owner"""
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in OWNER_IDS
    return app_commands.check(predicate)

# Global variables
active_games = {}
queues = {}
current_song = {}
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

async def send_long_message(interaction: discord.Interaction, text: str, prefix: str = "", max_length: int = 2000):
    """Send a long message by splitting it into chunks if needed."""
    # Remove the prefix length from max_length to account for it in each chunk
    chunk_size = max_length - len(prefix) - 10  # Some buffer for formatting
    
    if len(text) <= chunk_size:
        return await interaction.followup.send(f"{prefix}{text}")
    
    # Split the text into chunks
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    
    # Send the first chunk with the prefix
    await interaction.followup.send(f"{prefix}{chunks[0]}")
    
    # Send remaining chunks
    for chunk in chunks[1:]:
        await interaction.followup.send(chunk)

# GLM AI Integration
async def get_glm_response(prompt: str):
    """Get response from GLM model via Ollama"""
    try:
        # Initialize Ollama client
        client = ollama.Client(host='http://localhost:11434')
        
        # Generate response using GLM model
        response = client.chat(
            model='glm-4.6:cloud',  # Using the GLM model you have installed
            messages=[
                {
                    'role': 'user',
                    'content': f"Please respond in English: {prompt}"
                }
            ],
            options={
                'temperature': 0.7,
                'max_tokens': 1000
            }
        )
        
        # Extract and return the response
        if response and 'message' in response and 'content' in response['message']:
            return response['message']['content']
        else:
            return "No response from GLM model."
            
    except Exception as e:
        return f"Error connecting to GLM model: {str(e)}"

# Music player functions
def search_yt(query: str) -> str:
    # Search for the video using yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'default_search': 'ytsearch',
        'noplaylist': True
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if not info or 'entries' not in info or not info['entries']:
                return None
                
            video_url = info['entries'][0]['url']
            return video_url
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return None

async def play_next(interaction: discord.Interaction):
    if queues[interaction.guild.id]:
        url = queues[interaction.guild.id].pop(0)
        current_song[interaction.guild.id] = url
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['url']
            voice = get(bot.voice_clients, guild=interaction.guild)
            voice.play(FFmpegPCMAudio(url2, **FFMPEG_OPTIONS), 
                      after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction), bot.loop))
            voice.is_playing()
    else:
        current_song[interaction.guild.id] = None

# Events
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        # Debug: Print all synced command names
        print("Synced commands:", [cmd.name for cmd in synced])
    except Exception as e:
        print(f"Error during startup: {e}")
    await bot.change_presence(activity=discord.Game(name="Type /help"))

@bot.event
async def on_message(message):
    # Don't respond to bot's own messages
    if message.author == bot.user:
        return
    
    # Don't respond to other bots
    if message.author.bot:
        return
    
    # Check if bot is mentioned
    if bot.user.mentioned_in(message):
        # Remove the bot mention from the message content
        content = message.content.replace(f'<@!{bot.user.id}>', '').replace(f'<@{bot.user.id}>', '').strip()
        
        if content:
            # Bot was mentioned with a question
            async with message.channel.typing():
                response = await get_glm_response(content)
                await message.reply(f"**{message.author.mention}** asked: {content}\n\n**Answer:** {response}")
        else:
            # Bot was mentioned without content
            await message.reply(f"Hello {message.author.mention}! How can I help you today?")
    
    # Process commands normally
    await bot.process_commands(message)

# AI Commands
@bot.tree.command(name="ask", description="Ask the AI a question")
@app_commands.describe(question="Your question for the AI")
async def ask(interaction: discord.Interaction, question: str):
    """Ask the AI a question"""
    try:
        response = await get_glm_response(question)
        await send_long_message(interaction, f"**Question:** {question}\n\n**Answer:** {response}")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Music Commands
@bot.tree.command(name="play", description="Play music from YouTube")
@app_commands.describe(query="Name or URL of the song to play")
async def play(interaction: discord.Interaction, query: str):
    """Play music from YouTube"""
    if not interaction.user.voice:
        await interaction.response.send_message("You are not connected to a voice channel!", ephemeral=True)
        return
    
    voice_channel = interaction.user.voice.channel
    voice = get(bot.voice_clients, guild=interaction.guild)
    
    if voice and voice.is_connected():
        await voice.move_to(voice_channel)
    else:
        voice = await voice_channel.connect()
    
    url = search_yt(query)
    if not url:
        await interaction.response.send_message("Could not find the song.", ephemeral=True)
        return
    
    if interaction.guild.id not in queues:
        queues[interaction.guild.id] = []
    
    await interaction.response.defer()
    
    if not voice.is_playing() and not voice.is_paused():
        current_song[interaction.guild.id] = url
        await play_next(interaction)
        await interaction.followup.send(f"Now playing: {url}")
    else:
        queues[interaction.guild.id].append(url)
        await interaction.followup.send(f"Added to queue: {url}")

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    """Skip the current song"""
    voice = get(bot.voice_clients, guild=interaction.guild)
    if voice and voice.is_playing():
        voice.stop()
        await interaction.response.send_message("⏭️ Skipped the current song.")
    else:
        await interaction.response.send_message("No song is currently playing.", ephemeral=True)

@bot.tree.command(name="stop", description="Stop the music and clear the queue")
async def stop(interaction: discord.Interaction):
    """Stop the music and clear the queue"""
    voice = get(bot.voice_clients, guild=interaction.guild)
    if voice and voice.is_connected():
        if voice.is_playing() or voice.is_paused():
            voice.stop()
        if interaction.guild.id in queues:
            queues[interaction.guild.id] = []
        if interaction.guild.id in current_song:
            current_song[interaction.guild.id] = None
        await voice.disconnect()
        await interaction.response.send_message("⏹️ Stopped the music and cleared the queue.")
    else:
        await interaction.response.send_message("I'm not connected to a voice channel!", ephemeral=True)

@bot.tree.command(name="queue", description="Show the current music queue")
async def show_queue(interaction: discord.Interaction):
    """Show the current music queue"""
    if interaction.guild.id in queues and queues[interaction.guild.id]:
        queue_list = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queues[interaction.guild.id])])
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")
    else:
        await interaction.response.send_message("The queue is empty.")

# Game Commands
@bot.tree.command(name="tictactoe", description="Start a Tic-Tac-Toe game with another user")
@app_commands.describe(opponent="The user to play against")
async def tictactoe(interaction: discord.Interaction, opponent: discord.Member):
    """Start a Tic-Tac-Toe game"""
    if interaction.user == opponent:
        await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
        return
        
    game = TicTacToe(interaction.user, opponent)
    active_games[interaction.user.id] = game
    active_games[opponent.id] = game
    
    await interaction.response.send_message(
        f"🎮 {interaction.user.mention} has challenged {opponent.mention} to Tic-Tac-Toe!\n"
        f"Board:\n{game.get_board_string()}"
    )

@bot.tree.command(name="hangman", description="Start a game of Hangman")
async def hangman(interaction: discord.Interaction):
    """Start a Hangman game"""
    if interaction.user.id in active_games:
        await interaction.response.send_message("You're already in a game!", ephemeral=True)
        return
        
    game = Hangman(interaction.user)
    active_games[interaction.user.id] = game
    await interaction.response.send_message(
        f"🎮 Hangman game started! Word: {game.get_display_word()}\n"
        f"{game.get_hangman_stage()}"
    )

@bot.tree.command(name="battleship", description="Start a Battleship game with another user")
@app_commands.describe(opponent="The user to play against")
async def battleship(interaction: discord.Interaction, opponent: discord.Member):
    """Start a Battleship game"""
    if interaction.user == opponent:
        await interaction.response.send_message("You can't play against yourself!", ephemeral=True)
        return
        
    game = Battleship(interaction.user, opponent)
    active_games[interaction.user.id] = game
    active_games[opponent.id] = game
    
    await interaction.response.send_message(
        f"🚢 {interaction.user.mention} has challenged {opponent.mention} to Battleship!\n"
        "Setting up boards..."
    )
    await asyncio.sleep(2)
    await interaction.followup.send("Game started! Use `/shoot x y` to make a move.")

# Game Move Commands
@bot.tree.command(name="move", description="Make a move in Tic-Tac-Toe")
@app_commands.describe(position="Position to place your mark (1-9)")
async def move(interaction: discord.Interaction, position: int):
    """Make a move in Tic-Tac-Toe"""
    if interaction.user.id not in active_games:
        await interaction.response.send_message("You're not in a game!", ephemeral=True)
        return
        
    game = active_games[interaction.user.id]
    if not isinstance(game, TicTacToe):
        await interaction.response.send_message("This command is for Tic-Tac-Toe!", ephemeral=True)
        return
        
    if game.make_move(interaction.user, position - 1):  # Convert to 0-based index
        if game.winner:
            await interaction.response.send_message(
                f"Board:\n{game.get_board_string()}\n"
                f"🎉 {game.winner.mention} wins!"
            )
            del active_games[game.player1.id]
            if game.player2:
                del active_games[game.player2.id]
        else:
            await interaction.response.send_message(
                f"Board:\n{game.get_board_string()}\n"
                f"{game.current_player.mention}'s turn!"
            )
    else:
        await interaction.response.send_message("Invalid move!", ephemeral=True)

@bot.tree.command(name="guess", description="Guess a letter in Hangman")
@app_commands.describe(letter="The letter to guess")
async def guess(interaction: discord.Interaction, letter: str):
    """Guess a letter in Hangman"""
    if interaction.user.id not in active_games:
        await interaction.response.send_message("You're not in a game!", ephemeral=True)
        return
        
    game = active_games[interaction.user.id]
    if not isinstance(game, Hangman):
        await interaction.response.send_message("This command is for Hangman!", ephemeral=True)
        return
        
    result = game.guess(letter.upper())
    response = f"Word: {game.get_display_word()}\n{game.get_hangman_stage()}"
    
    if game.winner:
        if game.winner == "won":
            response += f"\n🎉 You won! The word was: {game.word}"
        else:
            response += f"\n😢 Game over! The word was: {game.word}"
        del active_games[interaction.user.id]
    
    await interaction.response.send_message(response)

@bot.tree.command(name="shoot", description="Shoot at coordinates in Battleship")
@app_commands.describe(x="X coordinate (1-10)", y="Y coordinate (1-10)")
async def shoot(interaction: discord.Interaction, x: int, y: int):
    """Shoot at coordinates in Battleship"""
    if interaction.user.id not in active_games:
        await interaction.response.send_message("You're not in a game!", ephemeral=True)
        return
        
    game = active_games[interaction.user.id]
    if not isinstance(game, Battleship):
        await interaction.response.send_message("This command is for Battleship!", ephemeral=True)
        return
        
    if game.current_player != interaction.user:
        await interaction.response.send_message("It's not your turn!", ephemeral=True)
        return
        
    result = game.make_move(interaction.user, x - 1, y - 1)  # Convert to 0-based index
    response = ""
    
    if result == "hit":
        response = "💥 Direct hit!"
    elif result == "miss":
        response = "💦 Missed!"
    elif result == "already_shot":
        response = "You've already shot there!"
    elif result == "sunk":
        response = "🔥 You sunk a ship!"
    elif result == "win":
        response = f"🏆 {interaction.user.mention} has won the game!"
        del active_games[game.player1.id]
        del active_games[game.player2.id]
    else:
        response = "Invalid coordinates!"
    
    response += f"\nYour tracking board:\n{game.get_board_string(interaction.user)}"
    
    if result != "win":
        game.current_player = game.player2 if game.current_player == game.player1 else game.player1
        response += f"\n🎯 {game.current_player.mention}'s turn!"
    
    await interaction.response.send_message(response)

# Utility Commands
@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Show all available commands"""
    help_embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all the available commands:",
        color=discord.Color.blue()
    )
    
    help_embed.add_field(
        name="🎮 Games",
        value=(
            "`/tictactoe @user` - Start a Tic-Tac-Toe game\n"
            "`/hangman` - Start a Hangman game\n"
            "`/battleship @user` - Start a Battleship game\n"
            "`/move 1-9` - Make a move in Tic-Tac-Toe\n"
            "`/guess A` - Guess a letter in Hangman\n"
            "`/shoot x y` - Shoot at coordinates in Battleship"
        ),
        inline=False
    )
    
    help_embed.add_field(
        name="🎵 Music",
        value=(
            "`/play <song>` - Play a song from YouTube\n"
            "`/skip` - Skip the current song\n"
            "`/stop` - Stop the music and clear the queue\n"
            "`/queue` - Show the current music queue"
        ),
        inline=False
    )
    
    help_embed.add_field(
        name="🤖 AI",
        value=(
            "`/ask <question>` - Ask the AI a question\n"
            "`/gemini <prompt>` - Ask Gemini AI a question"
        ),
        inline=False
    )
    
    help_embed.add_field(
        name="🛠️ Utility",
        value=(
            "`/help` - Show this help message\n"
            "`/ping` - Check bot latency\n"
            "`/userinfo [@user]` - Get user information\n"
            "`/serverinfo` - Get server information"
        ),
        inline=False
    )
    
    await interaction.response.send_message(embed=help_embed)

@bot.tree.command(name="ping", description="Check bot's latency")
async def ping(interaction: discord.Interaction):
    """Check bot's latency"""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f'🏓 Pong! Latency: {latency}ms')

@bot.tree.command(name="userinfo", description="Get information about a user")
@app_commands.describe(user="The user to get information about (leave empty for yourself)")
async def user_info(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    """Get user information"""
    member = user or interaction.user
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    
    embed = discord.Embed(
        title=f"User Info - {member}",
        color=member.color
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
    embed.add_field(name="Created At", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Joined At", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles) if roles else "None", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Get information about the server")
async def server_info(interaction: discord.Interaction):
    """Get server information"""
    guild = interaction.guild
    roles = [role.name for role in guild.roles if role.name != "@everyone"]
    
    embed = discord.Embed(
        title=f"Server Info - {guild.name}",
        description=guild.description or "No description",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
    embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Categories", value=len(guild.categories), inline=True)
    embed.add_field(name="Roles", value=len(roles), inline=True)
    embed.add_field(name="Emojis", value=len(guild.emojis), inline=True)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="lockdown", description="[OWNER] Lock down a channel")
@is_owner()
async def lockdown(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Lock down a channel (owner only)"""
    target_channel = channel or interaction.channel
    
    try:
        # Deny send_messages permission for @everyone
        await target_channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(f"🔒 {target_channel.mention} has been locked down.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to lock channel: {e}", ephemeral=True)

@bot.tree.command(name="unlock", description="[OWNER] Unlock a channel")
@is_owner()
async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Unlock a channel (owner only)"""
    target_channel = channel or interaction.channel
    
    try:
        # Reset send_messages permission for @everyone
        await target_channel.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(f"🔓 {target_channel.mention} has been unlocked.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to unlock channel: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages (requires Manage Messages permission)")
@app_commands.describe(amount="Number of messages to delete (1-100)")
@commands.has_permissions(manage_messages=True)
@is_owner()
async def clear_messages(interaction: discord.Interaction, amount: int = 5):
    """Clear messages from the current channel"""
    # Validate amount
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("Please specify a number between 1 and 100.", ephemeral=True)

    # Defer the response since this might take a while
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Add 1 to account for the command message itself
        deleted = await interaction.channel.purge(limit=amount + 1)
        
        # Send confirmation message
        await interaction.followup.send(f"✅ Successfully deleted {len(deleted) - 1} messages.", ephemeral=True)
        
        # Delete the confirmation message after 5 seconds
        msg = await interaction.original_response()
        await asyncio.sleep(5)
        await msg.delete()
        
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ An error occurred while deleting messages: {str(e)}", ephemeral=True)

@bot.tree.command(name="addrole", description="Add a role to a user or everyone")
@is_owner()
async def add_role(interaction: discord.Interaction, role: discord.Role, member: Optional[discord.Member] = None):
    if not interaction.guild:
        return await interaction.response.send_message("❌ Use this in a server.", ephemeral=True)

    # FORCE FETCH: This clears the "pos 0" cache issue
    me = await interaction.guild.fetch_member(interaction.client.user.id)
    
    # Calculate the actual highest position from the fresh data
    bot_top_pos = max([r.position for r in me.roles]) if me.roles else 0

    if bot_top_pos <= role.position:
        return await interaction.response.send_message(
            f"❌ I cannot assign **{role.name}**. My highest role (pos {bot_top_pos}) "
            f"is not above this role (pos {role.position}).",
            ephemeral=True
        )
    
    # If no member specified, add to everyone
    if member is None:
        await interaction.response.defer(ephemeral=True)
        await add_role_to_everyone(interaction, role)
        return
    
    # Add role to specific member
    try:
        if role in member.roles:
            return await interaction.response.send_message(
                f"ℹ️ {member.mention} already has the {role.mention} role.",
                ephemeral=True
            )
            
        await member.add_roles(role, reason=f"Added by {interaction.user}")
        await interaction.response.send_message(
            f"✅ Successfully added {role.mention} to {member.mention}!",
            ephemeral=True
        )
        
    except discord.Forbidden:
        await interaction.response.send_message(
            f"❌ I don't have permission to add roles to {member.mention}.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Failed to add role to {member.mention}: {str(e)}",
            ephemeral=True
        )

async def add_role_to_everyone(interaction: discord.Interaction, role: discord.Role):
    """Helper function to add role to everyone in the server"""
    try:
        guild = interaction.guild
        if not guild.me.guild_permissions.manage_roles:
            return await interaction.followup.send("❌ I don't have permission to manage roles in this server.", ephemeral=True)
            
        members = [m for m in guild.members if not m.bot and role not in m.roles]
        total_members = len(members)
        
        if total_members == 0:
            await interaction.followup.send(
                f"ℹ️ All members already have the {role.mention} role.",
                ephemeral=True
            )
            return
        
        progress_msg = await interaction.followup.send(
            f"🔄 Adding {role.mention} to {total_members} members... (0/{total_members})",
            ephemeral=True
        )
        
        success = 0
        failed = 0
        
        for i, member in enumerate(members, 1):
            try:
                await member.add_roles(role, reason=f"Mass role assignment by {interaction.user}")
                success += 1
                
                # Update progress every 5 members
                if i % 5 == 0 or i == total_members:
                    await progress_msg.edit(
                        content=f"🔄 Adding {role.mention} to members ({i}/{total_members})...\n"
                               f"• Success: {success} | Failed: {failed}"
                    )
                    await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                failed += 1
                print(f"Failed to add role to {member}: {str(e)}")
                continue
        
        await progress_msg.edit(
            content=(
                f"✅ Role assignment complete!\n"
                f"• Successfully added to: {success} members\n"
                f"• Failed to add to: {failed} members\n"
                f"• Role: {role.mention}"
            )
        )
        
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"❌ Discord API error: {str(e)}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="remove", description="Remove a role from a user or everyone (Owner only)")
@is_owner()
async def remove_role(interaction: discord.Interaction, role: discord.Role, member: Optional[discord.Member] = None):
    """Remove a role from a specific user or everyone in the server"""
    if not interaction.guild:
        return await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
    
    # Check if the bot's highest role is lower than the role it's trying to remove
    if interaction.guild.me.top_role <= role:
        return await interaction.response.send_message(
            "❌ I cannot remove this role because it is higher than my own role!",
            ephemeral=True
        )
    
    # If no member specified, remove from everyone
    if member is None:
        await interaction.response.defer(ephemeral=True)
        await remove_role_from_everyone(interaction, role)
        return
    
    # Remove role from specific member
    try:
        if role not in member.roles:
            await interaction.response.send_message(
                f"ℹ️ {member.mention} doesn't have the {role.mention} role.",
                ephemeral=True
            )
            return
            
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(
            f"✅ Successfully removed {role.mention} from {member.mention}!",
            ephemeral=True
        )
        
    except discord.Forbidden:
        await interaction.response.send_message(
            f"❌ I don't have permission to remove roles from {member.mention}.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Failed to remove role from {member.mention}: {str(e)}",
            ephemeral=True
        )

async def remove_role_from_everyone(interaction: discord.Interaction, role: discord.Role):
    """Helper function to remove role from everyone in the server"""
    try:
        guild = interaction.guild
        if not guild.me.guild_permissions.manage_roles:
            return await interaction.followup.send("❌ I don't have permission to manage roles in this server.", ephemeral=True)
            
        members = [m for m in guild.members if role in m.roles]
        total_members = len(members)
        
        if total_members == 0:
            await interaction.followup.send(
                f"ℹ️ No one has the {role.mention} role.",
                ephemeral=True
            )
            return
        
        progress_msg = await interaction.followup.send(
            f"🔄 Removing {role.mention} from {total_members} members... (0/{total_members})",
            ephemeral=True
        )
        
        success = 0
        failed = 0
        
        for i, member in enumerate(members, 1):
            try:
                await member.remove_roles(role, reason=f"Mass role removal by {interaction.user}")
                success += 1
                
                # Update progress every 5 members
                if i % 5 == 0 or i == total_members:
                    await progress_msg.edit(
                        content=f"🔄 Removing {role.mention} from members ({i}/{total_members})...\n"
                               f"• Success: {success} | Failed: {failed}"
                    )
                    await asyncio.sleep(1)  # Rate limiting
            except Exception as e:
                failed += 1
                print(f"Failed to remove role from {member}: {str(e)}")
                continue
        
        await progress_msg.edit(
            content=(
                f"✅ Role removal complete!\n"
                f"• Successfully removed from: {success} members\n"
                f"• Failed to remove from: {failed} members\n"
                f"• Role: {role.mention}"
            )
        )
        
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"❌ Discord API error: {str(e)}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

@bot.tree.command(name="generate", description="Generate an AI image using Pollinations API with Z-Image Turbo")
@is_owner()
@commands.has_permissions(manage_messages=True)
@app_commands.describe(
    prompt="Description of the image to generate",
    model="AI model to use (default: z-image-turbo)"
)
async def generate_image(interaction: discord.Interaction, prompt: str, model: str = "z-image-turbo"):
    """Generate an AI image based on the given prompt using Z-Image Turbo by default"""
    await interaction.response.defer()
    
    try:
        # Pollinations API endpoint for Z-Image Turbo
        url = f"https://image.pollinations.ai/prompt/{prompt}?model={model}"
        
        # Add API key if available
        headers = {}
        api_key = os.getenv("POLLINATIONS_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Convert to Discord file
                    file = discord.File(BytesIO(image_data), filename="generated_image.png")
                    
                    # Send the image
                    embed = discord.Embed(title=f"Generated: {prompt}")
                    embed.set_image(url="attachment://generated_image.png")
                    embed.set_footer(text=f"Model: {model} | Using Z-Image Turbo")
                    
                    await interaction.followup.send(file=file, embed=embed)
                else:
                    error_text = await response.text()
                    print(f"API Error: {response.status} - {error_text}")
                    await interaction.followup.send(
                        f"❌ Failed to generate image (Status: {response.status}). Please try again later."
                    )
    except Exception as e:
        print(f"Error generating image: {e}")
        await interaction.followup.send("❌ An error occurred while generating the image. Please check the logs.")

@bot.tree.command(name="search", description="Search for images on the web")
@app_commands.describe(query="What to search for", limit="Number of results (1-10)")
async def search_images(interaction: discord.Interaction, query: str, limit: int = 5):
    """Search for images using DuckDuckGo"""
    if limit < 1 or limit > 10:
        await interaction.response.send_message("Please choose a limit between 1 and 10.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Create a new browser context for this search
        context = await browser.new_context()
        page = await context.new_page()
        
        # Search on DuckDuckGo
        search_url = f"https://duckduckgo.com/?q={query}&t=h_&iax=images&ia=images"
        await page.goto(search_url)
        
        # Wait for images to load
        await page.wait_for_selector("img[data-testid='image']", timeout=10000)
        
        # Get image URLs
        image_urls = await page.evaluate('''() => {
            const images = Array.from(document.querySelectorAll('img[data-testid="image"]'));
            return images.slice(0, 10).map(img => img.src);
        }''')
        
        # Close the context when done
        await context.close()
        
        if not image_urls:
            await interaction.followup.send("❌ No images found.")
            return
        
        # Send the first image as an embed and the rest as links
        embed = discord.Embed(title=f"Search results for: {query}")
        embed.set_image(url=image_urls[0])
        
        # Add links to other images
        if len(image_urls) > 1:
            other_images = "\n".join([f"{i+1}. [Image {i+1}]({url})" for i, url in enumerate(image_urls[1:limit])])
            embed.add_field(name="More Images", value=other_images, inline=False)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Error searching images: {e}")
        await interaction.followup.send("❌ An error occurred while searching for images.")

@bot.tree.command(name="say", description="Make the bot say something")
@app_commands.describe(message="What should I say?", channel="Channel to send to (default: current channel)")
async def say(interaction: discord.Interaction, message: str, channel: Optional[discord.TextChannel] = None):
    """Make the bot say something"""
    # This is an ephemeral response - only the user who ran the command can see it
    await interaction.response.send_message("✅ Message sent!", ephemeral=True)
    
    # Send the actual message to the specified channel or current channel
    target_channel = channel or interaction.channel
    await target_channel.send(message)

@bot.command(name='addrole')
@commands.has_permissions(manage_roles=True)
@commands.is_owner()
async def add_role_cmd(ctx, role: discord.Role, member: discord.Member = None):
    """Add a role to a user or everyone (Owner only)
    Usage: !addrole @Role [@User]
    Example: !addrole @Member @User  # Add role to specific user
             !addrole @Member        # Add role to everyone
    """
    if not ctx.guild:
        return await ctx.send("❌ This command can only be used in a server.")
        
    try:
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("❌ I don't have permission to manage roles!")
            
        if ctx.guild.me.top_role.position <= role.position:
            return await ctx.send("❌ I can't assign roles that are higher than or equal to my highest role.")
            
        if member:
            # Add role to specific user
            if role in member.roles:
                return await ctx.send(f"ℹ️ {member.mention} already has the {role.mention} role.")
                
            await member.add_roles(role, reason=f"Added by {ctx.author}")
            return await ctx.send(f"✅ Added {role.mention} to {member.mention}!")
        else:
            # Add role to everyone
            members = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
            if not members:
                return await ctx.send(f"ℹ️ Everyone already has the {role.mention} role.")
                
            msg = await ctx.send(f"🔄 Adding {role.mention} to {len(members)} members...")
            success = 0
            
            for m in members:
                try:
                    await m.add_roles(role, reason=f"Mass role assignment by {ctx.author}")
                    success += 1
                    if success % 5 == 0:  # Update every 5 members
                        await msg.edit(content=f"🔄 Adding {role.mention} to members... ({success}/{len(members)})")
                    await asyncio.sleep(0.5)  # Rate limiting
                except:
                    continue
                    
            await msg.edit(content=f"✅ Added {role.mention} to {success} members!")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        print(f"Error in addrole command: {str(e)}")

@bot.command(name='removerole')
@commands.has_permissions(manage_roles=True)
@commands.is_owner()
async def remove_role_cmd(ctx, role: discord.Role, member: discord.Member = None):
    """Remove a role from a user or everyone (Owner only)
    Usage: !removerole @Role [@User]
    Example: !removerole @Member @User  # Remove role from specific user
             !removerole @Member        # Remove role from everyone
    """
    if not ctx.guild:
        return await ctx.send("❌ This command can only be used in a server.")
        
    try:
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("❌ I don't have permission to manage roles!")
            
        if ctx.guild.me.top_role.position <= role.position:
            return await ctx.send("❌ I can't remove roles that are higher than or equal to my highest role.")
            
        if member:
            # Remove role from specific user
            if role not in member.roles:
                return await ctx.send(f"ℹ️ {member.mention} doesn't have the {role.mention} role.")
                
            await member.remove_roles(role, reason=f"Removed by {ctx.author}")
            return await ctx.send(f"✅ Removed {role.mention} from {member.mention}!")
        else:
            # Remove role from everyone
            members = [m for m in ctx.guild.members if role in m.roles]
            if not members:
                return await ctx.send(f"ℹ️ No one has the {role.mention} role.")
                
            msg = await ctx.send(f"🔄 Removing {role.mention} from {len(members)} members...")
            success = 0
            
            for m in members:
                try:
                    await m.remove_roles(role, reason=f"Mass role removal by {ctx.author}")
                    success += 1
                    if success % 5 == 0:  # Update every 5 members
                        await msg.edit(content=f"🔄 Removing {role.mention} from members... ({success}/{len(members)})")
                    await asyncio.sleep(0.5)  # Rate limiting
                except:
                    continue
                    
            await msg.edit(content=f"✅ Removed {role.mention} from {success} members!")
            
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")
        print(f"Error in removerole command: {str(e)}")

@bot.event
async def on_disconnect():
    """Clean up resources when bot disconnects"""
    global browser, playwright
from threading import Thread

async def start_flask():
    from server import app, socketio
    port = int(os.getenv('PORT', 10000))
    
    # Create a simple HTTP server for health checks
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "bot": "starting"}).encode())
    
    # Start the health check server on a different port to avoid conflicts
    health_check_port = 8080  # Using 8080 as an alternative port
    def run_health_check():
        server = HTTPServer(('0.0.0.0', health_check_port), HealthHandler)
        print(f"Health check server started on port {health_check_port}")
        server.serve_forever()
    
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    
    # Start the Flask server
    print(f"Starting Flask server on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

async def main():
    # Start the Flask server in a separate thread
    flask_thread = Thread(target=lambda: asyncio.run(start_flask()), daemon=True)
    flask_thread.start()
    
    # Give the server a moment to start and check if it's running
    await asyncio.sleep(2)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://localhost:{port}') as resp:
                if resp.status == 200:
                    print(f"✅ Flask server is running on port {port}")
    except Exception as e:
        print(f"⚠️  Could not connect to Flask server: {e}")
    
    try:
        # Run the bot
        print("Starting Discord bot...")
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        # Clean up resources
        if 'browser' in globals() and browser:
            await browser.close()
        if 'playwright' in globals() and playwright:
            await playwright.stop()
        print("Bot has been shut down")

if __name__ == "__main__":
    if not TOKEN:
        print("Error: No Discord token found in .env file!")
        sys.exit(1)
        
    import asyncio
    import sys
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)