import os
import discord
import logging
import asyncio
import datetime
import json
import random

from discord.ext import commands
from dotenv import load_dotenv
from agent import MistralAgent, NewsAgent, DebateStatsTracker

PREFIX = "!"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord")

# Load the environment variables
load_dotenv()

# Create the bot with all intents
# The message content and members intent must be enabled in the Discord Developer Portal for the bot to work.
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Import the Mistral agent from the agent.py file
news_agent = NewsAgent()
debate_agent = MistralAgent()

# Get the token from the environment variables
token = os.getenv("DISCORD_TOKEN")
print(f"Token loaded: {'Yes' if token else 'No'}")
print(f"Token length: {len(token) if token else 0}")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "123456789012345678"))

# Track active debates
active_debates = {}
stats_tracker = DebateStatsTracker()

# Add this class near the top of your bot.py file, after the imports
class FakeMessage:
    """A simple class to simulate a Discord message for the agent."""
    def __init__(self, content, author=None):
        self.content = content
        self.author = author

@bot.event
async def on_ready():
    """
    Called when the client is done preparing the data received from Discord.
    Prints message on terminal when bot successfully connects to discord.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready
    """
    logger.info(f"{bot.user} has connected to Discord!")
    
    # starts the conversation by greeting the user
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        welcome_embed = discord.Embed(
            title="EchoBreaker Debate Bot",
            description="I'm here to help you sharpen your debate skills by challenging you with strong political viewpoints.",
            color=discord.Color.blue()
        )
        welcome_embed.add_field(
            name="How to start",
            value="Type `!debate [topic]` to begin a debate\nExample: `!debate climate change` or just `!debate` for a random topic",
            inline=False
        )
        welcome_embed.add_field(
            name="Difficulty levels",
            value="`!debate easy [topic]` - For beginners (0.8x points)\n"
                 "`!debate normal [topic]` - Standard difficulty (1.0x points)\n"
                 "`!debate hard [topic]` - For experienced debaters (1.2x points)",
            inline=False
        )
        welcome_embed.add_field(
            name="Commands",
            value="`!stats` - View your debate statistics\n"
                 "`!leaderboard` - See top debaters\n"
                 "`!enddebate` - End current debate session",
            inline=False
        )
        welcome_embed.add_field(
            name="Earning Points",
            value="• Longer debates earn more points (up to 30 base points)\n"
                 "• Longer, thoughtful responses get bonus points\n"
                 "• Complete debates daily to build your streak\n"
                 "• Earn achievements to showcase your skills",
            inline=False
        )
        welcome_embed.add_field(
            name="Features",
            value="• Gamified debates with points and levels\n"
                  "• AI-powered fact-checking of your claims\n"
                  "• Personalized feedback to improve your skills\n"
                  "• Multiple difficulty levels",
            inline=False
        )
        welcome_embed.add_field(
            name="Historical Figures",
            value="`!figures` - View available historical figures\n"
                  "`!figure [name]` - View details about a figure\n"
                  "`!customfigure [name]` - Create any historical figure\n"
                  "`!debate [figure] [topic]` - Debate as a historical figure",
            inline=False
        )
        
        await channel.send("Hello, I'm EchoBreaker! Ready to debate?", embed=welcome_embed)

@bot.event
async def on_message(message: discord.Message):
    """
    Called when a message is sent in any channel the bot can see.

    https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message
    """
    # Don't delete this line! It's necessary for the bot to process commands.
    await bot.process_commands(message)

    # Ignore messages from self or other bots to prevent infinite loops.
    if message.author.bot or message.content.startswith("!"):
        return

    # Check if user is in an active debate
    if message.author.id in active_debates:
        logger.info(f"Processing debate message from {message.author}: {message.content}")
        
        # Update message count and award points for each message
        debate_info = active_debates[message.author.id]
        debate_info["messages_count"] += 1
        
        # Track total characters for averaging later
        message_length = len(message.content)
        if "total_chars" not in debate_info:
            debate_info["total_chars"] = 0
        debate_info["total_chars"] += message_length
        
        # Award points based on message quality (length)
        if message_length > 300:
            quality_points = 3
        elif message_length > 150:
            quality_points = 2
        elif message_length > 50:
            quality_points = 1
        else:
            quality_points = 0
            
        debate_info["points_accumulated"] += quality_points
        
        # Use the enhanced fact-checking response method
        response_data = await debate_agent.fact_check_and_respond(message)
        response = response_data["response"]
        fact_check = response_data["fact_check"]
        
        # Award bonus points for accurate claims
        if fact_check and "✅" in fact_check:
            debate_info["points_accumulated"] += 2
            fact_check += "\n*+2 points awarded for accurate claims!*"
        
        # Send the response
        if len(response) <= 2000:
            await message.reply(response)
        else:
            # Split the response into chunks of 1900 characters
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            for i, chunk in enumerate(chunks):
                await message.channel.send(f"**Part {i+1}/{len(chunks)}**: {chunk}")
        
        # If there's a fact check, send it as a separate embed
        if fact_check:
            fact_check_embed = discord.Embed(
                title="Fact Check Results",
                description=fact_check,
                color=discord.Color.blue()
            )
            fact_check_embed.set_footer(text="Powered by Perplexity AI")
            await message.channel.send(embed=fact_check_embed)

# Commands
@bot.command(name="debate", help="Start a political debate with the bot. Optional: [figure] [difficulty] [topic]")
async def debate(ctx, arg1=None, arg2=None, *, topic=None):
    """
    Start a debate session with the bot.
    
    Can be used in multiple ways:
    !debate - Start debate with random topic
    !debate topic - Start debate on specific topic
    !debate figure topic - Start debate as historical figure
    !debate difficulty topic - Start debate with difficulty setting
    !debate figure difficulty topic - Full specification
    """
    user_id = ctx.author.id
    
    # Check if user is already in a debate
    if user_id in active_debates:
        await ctx.send("You're already in an active debate! Type `!enddebate` to end it first.")
        return
    
    # Parse the arguments
    figure = None
    difficulty = "normal"
    
    # Process first argument
    if arg1:
        # Check if arg1 is a figure name
        if debate_agent.historical_figures.get_figure_details(arg1):
            figure = arg1
        # Check if arg1 is a difficulty
        elif arg1 in ["easy", "normal", "hard"]:
            difficulty = arg1
        # Check if it might be an unknown historical figure
        elif arg1.isalpha() and len(arg1) > 3 and not arg1.isdigit():
            await ctx.send(f"I don't recognize '{arg1}' as a historical figure. Use `!figures` to see available options or create a custom figure with `!customfigure {arg1}`.")
            return
        # Otherwise it's part of the topic
        else:
            if topic:
                topic = f"{arg1} {arg2} {topic}"
            elif arg2:
                topic = f"{arg1} {arg2}"
            else:
                topic = arg1
            arg1 = None
            arg2 = None
    
    # Process second argument if first was used
    if arg1 and arg2:
        # If we already have a figure, check for difficulty
        if figure and arg2 in ["easy", "normal", "hard"]:
            difficulty = arg2
        # Otherwise it's part of the topic
        else:
            if topic:
                topic = f"{arg2} {topic}"
            else:
                topic = arg2
            arg2 = None
    
    # Inform user about difficulty level
    difficulty_factor = {"easy": 0.8, "normal": 1.0, "hard": 1.2}
    difficulty_desc = {
        "easy": "I'll take it easy on you and be more willing to concede points.",
        "normal": "I'll present a balanced debate with moderate intensity.",
        "hard": "I'll aggressively defend my position and challenge your arguments thoroughly."
    }
    
    # Set historical figure if specified
    figure_desc = ""
    if figure:
        figure_details = debate_agent.historical_figures.get_figure_details(figure)
        debate_agent.set_historical_figure(figure)
        figure_desc = f"**Debating as: {figure_details['name']}**\n{figure_details['description']}\n\n"
    else:
        debate_agent.reset_persona()
    
    # Display settings
    await ctx.send(
        f"{figure_desc}**Difficulty: {difficulty.upper()}**\n{difficulty_desc[difficulty]}\n" +
        f"Point multiplier: {difficulty_factor[difficulty]}x"
    )
    
    if topic:
        await ctx.send(f"Let's start a debate about {topic}! I'll find a relevant news article for us to discuss...")
        # Get an article related to the specified topic
        top_article = news_agent.get_article_by_topic(topic)
    else:
        await ctx.send("Let's start a debate! I'll find a current news article for us to discuss...")
        # Pull a random top article from the news API
        top_article = news_agent.get_top_article()

    title = top_article["title"]
    author = top_article["author"] if top_article["author"] else "Unknown author"
    description = top_article["description"] if top_article["description"] else "No description available"
    url = top_article["url"]
    
    # Display the article to the user
    article_embed = discord.Embed(
        title=title,
        description=description,
        url=url,
        color=discord.Color.blue()
    )
    article_embed.set_author(name=author)
    article_embed.set_footer(text="Source: NewsAPI")
    
    await ctx.send("Here's a news article on this topic:", embed=article_embed)
    
    # Set up the debate agent with context about the article
    setup_message = FakeMessage(
        content=f"Take a strong political position on this news article: {title}. {description} " +
                f"Difficulty level: {difficulty}",
        author=ctx.author
    )
    
    # Get the AI's opening position
    opening_position = await debate_agent.run(setup_message)
    
    # Truncate if too long
    if len(opening_position) > 1500:
        opening_position = opening_position[:1497] + "..."
    
    # Send the debate prompt with gamification info
    await ctx.send(f"**Let's begin our debate!**\n\n{opening_position}\n\n" +
                   f"What's your position on this? I'll defend my viewpoint, and you try to convince me otherwise.\n" +
                   f"(You're now in an active debate - all your messages will be part of the debate until you type `!enddebate`)\n\n" +
                   f"**Debate Tips:**\n" +
                   f"• Longer, thoughtful responses earn more points\n" +
                   f"• Present evidence to support your arguments\n" +
                   f"• Address my key points directly")
    
    # Mark user as in an active debate
    active_debates[user_id] = {
        "article": top_article,
        "start_time": datetime.datetime.now(),
        "difficulty": difficulty,
        "points_accumulated": 0,
        "messages_count": 0
    }

@bot.command(name="enddebate", help="End your current debate session.")
async def enddebate(ctx):
    """End the current debate session and award points."""
    user_id = ctx.author.id
    
    if user_id in active_debates:
        debate_info = active_debates[user_id]
        
        # Reset agent's persona
        debate_agent.reset_persona()
        
        # Calculate debate duration and points
        start_time = debate_info["start_time"]
        duration = (datetime.datetime.now() - start_time).total_seconds()
        
        # Get difficulty multiplier
        difficulty = debate_info["difficulty"]
        difficulty_factor = {"easy": 0.8, "normal": 1.0, "hard": 1.2}
        
        # Award points and update stats
        result = stats_tracker.complete_debate(user_id, int(duration))
        points_earned = result["points_earned"]
        adjusted_points = int(points_earned * difficulty_factor[difficulty])
        
        # Add bonus points based on message count
        message_count = debate_info["messages_count"]
        message_bonus = min(10, message_count)  # Cap at 10 bonus points
        total_points = adjusted_points + message_bonus
        
        # Update final stats
        stats = stats_tracker.add_points(user_id, total_points)
        
        # Create an embed for the debate summary
        embed = discord.Embed(
            title="Debate Completed!",
            description=f"You've earned {total_points} points from this debate.",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Base Points", value=f"{points_earned} pts", inline=True)
        embed.add_field(name="Difficulty Bonus", value=f"{difficulty.capitalize()} ({difficulty_factor[difficulty]}x)", inline=True)
        embed.add_field(name="Message Bonus", value=f"+{message_bonus} pts", inline=True)
        embed.add_field(name="Debate Duration", value=f"{int(duration // 60)} minutes", inline=True)
        embed.add_field(name="Messages Sent", value=str(message_count), inline=True)
        
        # Check for level ups
        old_level = (stats["points"] - total_points) // 100 + 1
        new_level = stats["level"]
        if new_level > old_level:
            embed.add_field(name="LEVEL UP!", value=f"You are now level {new_level}!", inline=False)
        
        # Check for new achievements
        new_achievements = stats_tracker._check_achievements(user_id, stats)
        if new_achievements:
            embed.add_field(name="New Achievements!", value="\n".join([f"• {ach}" for ach in new_achievements]), inline=False)
        
        await ctx.send(embed=embed)
        
        # Show overall stats
        stats_embed = create_stats_embed(ctx.author, stats)
        await ctx.send("Your updated stats:", embed=stats_embed)
        
        # Generate and show debate feedback
        feedback = generate_debate_feedback(debate_info)
        
        feedback_embed = discord.Embed(
            title="Debate Feedback",
            description="Here's some feedback to help improve your debating skills:",
            color=discord.Color.purple()
        )
        
        for i, tip in enumerate(feedback):
            feedback_embed.add_field(name=f"Tip {i+1}", value=tip, inline=False)
            
        await ctx.send(embed=feedback_embed)
        
        del active_debates[user_id]
    else:
        await ctx.send("You don't have an active debate session.")

@bot.command(name="ping", help="Pings the bot.")
async def ping(ctx, *, arg=None):
    if arg is None:
        await ctx.send("Pong!")
    else:
        await ctx.send(f"Pong! Your argument was {arg}")

@bot.command(name="stats", help="View your debate statistics.")
async def show_stats(ctx, member: discord.Member = None):
    """Show debate statistics for yourself or another user."""
    target = member or ctx.author
    stats = stats_tracker.get_user_stats(target.id)
    
    embed = create_stats_embed(target, stats)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"], help="View the debate points leaderboard.")
async def leaderboard(ctx):
    """Show the top 10 users by debate points."""
    top_users = stats_tracker.get_leaderboard(10)
    
    embed = discord.Embed(
        title="Debate Leaderboard",
        description="Top debaters ranked by points",
        color=discord.Color.gold()
    )
    
    for i, (user_id, user_stats) in enumerate(top_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            username = user.name
        except:
            username = f"User {user_id}"
        
        embed.add_field(
            name=f"{i}. {username}",
            value=f"Level {user_stats['level']} • {user_stats['points']} pts • {user_stats['debates_completed']} debates",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="factcheck", help="Explains how the fact-checking feature works")
async def explain_factcheck(ctx):
    """Explains the fact-checking feature to users."""
    embed = discord.Embed(
        title="Fact-Checking in Debates",
        description="EchoBreaker uses AI-powered fact-checking to verify claims made during debates.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="How it works",
        value="When you make factual claims in your arguments, the bot will:\n"
              "1. Detect potential factual statements\n"
              "2. Verify them using Perplexity's search capabilities\n"
              "3. Display the results alongside the bot's response",
        inline=False
    )
    
    embed.add_field(
        name="Verdicts",
        value="✅ **True**: Claim is accurate based on reliable sources\n"
              "⚠️ **Partly True** or **Needs Context**: Claim has some accuracy but is missing important context\n"
              "❌ **False**: Claim contradicts reliable sources",
        inline=False
    )
    
    embed.add_field(
        name="Benefits",
        value="• Earn bonus points for accurate claims\n"
              "• Learn to distinguish facts from opinions\n"
              "• Improve your research and argumentation skills",
        inline=False
    )
    
    embed.set_footer(text="Fact-checking powered by Perplexity AI")
    
    await ctx.send(embed=embed)

@bot.command(name="figures", aliases=["historicalfigures", "personas"], help="List available historical figures for debates")
async def list_figures(ctx):
    """Show a list of historical figures the bot can debate as."""
    figures = debate_agent.historical_figures.get_figure_names()
    
    embed = discord.Embed(
        title="Available Historical Figures",
        description="Choose a historical figure for your next debate using `!debate [figure] [topic]`\nExample: `!debate churchill democracy`",
        color=discord.Color.gold()
    )
    
    for figure_id in figures:
        figure = debate_agent.historical_figures.get_figure_details(figure_id)
        embed.add_field(
            name=figure["name"],
            value=f"**Era:** {figure['era']}\n"
                  f"**Style:** {figure['style']}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="figure", help="Get details about a specific historical figure")
async def figure_details(ctx, figure_id):
    """Show detailed information about a specific historical figure."""
    figure = debate_agent.historical_figures.get_figure_details(figure_id)
    
    if not figure:
        await ctx.send(f"Historical figure '{figure_id}' not found. Use `!figures` to see available options.")
        return
    
    embed = discord.Embed(
        title=figure["name"],
        description=figure["description"],
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Era", value=figure["era"], inline=True)
    embed.add_field(name="Debate Style", value=figure["style"], inline=False)
    embed.add_field(name="Key Beliefs", value=figure["beliefs"], inline=False)
    embed.add_field(
        name="Usage",
        value=f"Start a debate with this figure using:\n`!debate {figure_id.lower()} [topic]`",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name="customfigure", aliases=["custom"], help="Create a custom historical figure to debate as")
async def create_custom_figure(ctx, *, figure_name):
    """
    Create a custom historical figure to debate as.
    
    Args:
        figure_name: The name of the historical figure to create
    """
    if not figure_name:
        await ctx.send("Please provide the name of a historical figure. Example: `!customfigure Napoleon Bonaparte`")
        return
    
    # Show typing indicator while generating
    async with ctx.typing():
        await ctx.send(f"Generating debate persona for {figure_name}... This might take a moment.")
        
        # Generate the custom figure
        figure_key, figure_data = await debate_agent.historical_figures.generate_custom_figure(
            figure_name, debate_agent.client
        )
        
        if not figure_key:
            await ctx.send(f"Sorry, I couldn't generate a persona for {figure_name}. Please try a different figure.")
            return
    
    # Create an embed to display the new figure
    embed = discord.Embed(
        title=f"New Historical Figure: {figure_data['name']}",
        description=figure_data['description'],
        color=discord.Color.purple()
    )
    
    embed.add_field(name="Era", value=figure_data["era"], inline=True)
    embed.add_field(name="Debate Style", value=figure_data["style"], inline=False)
    embed.add_field(name="Key Beliefs", value=figure_data["beliefs"], inline=False)
    embed.add_field(
        name="Usage",
        value=f"Start a debate with this figure using:\n`!debate {figure_key} [topic]`",
        inline=False
    )
    
    await ctx.send(f"✅ Successfully created a debate persona for **{figure_data['name']}**!", embed=embed)

@bot.command(name="helpfigures", help="Learn how to use the historical figures feature")
async def help_figures(ctx):
    """Show help information about the historical figures feature."""
    embed = discord.Embed(
        title="Historical Figures in Debates",
        description="Debate with the bot as if you were talking to historical figures from throughout time.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Pre-defined Figures",
        value="Use `!figures` to see the list of pre-defined historical figures\n"
              "Use `!figure [name]` to see details about a specific figure\n"
              "Example: `!figure churchill`",
        inline=False
    )
    
    embed.add_field(
        name="Creating Custom Figures",
        value="You can create any historical figure with:\n"
              "`!customfigure [full name]`\n"
              "Examples:\n"
              "• `!customfigure Napoleon Bonaparte`\n"
              "• `!customfigure Queen Elizabeth I`\n"
              "• `!customfigure Genghis Khan`",
        inline=False
    )
    
    embed.add_field(
        name="Starting a Debate",
        value="Start a debate with a historical figure:\n"
              "`!debate [figure] [topic]`\n"
              "Examples:\n"
              "• `!debate aristotle ethics`\n"
              "• `!debate churchill hard democracy`\n"
              "• `!debate napoleon_bonaparte war`",
        inline=False
    )
    
    await ctx.send(embed=embed)

# Add this helper function after the FakeMessage class
def create_stats_embed(user, stats):
    """Creates an embed to display a user's debate stats."""
    embed = discord.Embed(
        title=f"{user.name}'s Debate Stats",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    
    # Calculate XP to next level
    xp_to_next = (stats["level"] * 100) - stats["points"]
    
    embed.add_field(name="Level", value=f"{stats['level']} ({stats['points']} points)", inline=True)
    embed.add_field(name="Next Level", value=f"{xp_to_next} points needed", inline=True)
    embed.add_field(name="Debates Completed", value=str(stats["debates_completed"]), inline=True)
    embed.add_field(name="Current Streak", value=f"{stats['streak']} days", inline=True)
    embed.add_field(name="Longest Streak", value=f"{stats['longest_streak']} days", inline=True)
    
    # Add achievements if any
    if stats["achievements"]:
        achievements_list = "\n".join([
            "• First Debate" if "first_debate" in stats["achievements"] else "",
            "• Debate Master" if "debate_master" in stats["achievements"] else "",
            "• Point Collector" if "point_collector" in stats["achievements"] else "",
            "• 3-Day Streak" if "streak_3" in stats["achievements"] else "",
            "• Skilled Debater" if "high_level" in stats["achievements"] else ""
        ])
        embed.add_field(name="Achievements", value=achievements_list, inline=False)
    
    return embed

# Add this new function near the stats embed function
def generate_debate_feedback(debate_info):
    """Generates constructive feedback for the user based on their debate performance."""
    message_count = debate_info["messages_count"]
    avg_message_length = debate_info.get("total_chars", 0) / max(message_count, 1)
    duration_minutes = (datetime.datetime.now() - debate_info["start_time"]).total_seconds() / 60
    
    # Generate appropriate feedback based on metrics
    feedback = []
    
    # Engagement feedback
    if message_count < 3:
        feedback.append("Try to engage more deeply in the debate. Aim for at least 3-4 exchanges to develop your arguments fully.")
    elif message_count > 8:
        feedback.append("Great engagement level! You maintained a sustained conversation.")
    
    # Message length feedback
    if avg_message_length < 100:
        feedback.append("Your responses were quite brief. Try to elaborate more on your arguments with examples and evidence.")
    elif avg_message_length > 300:
        feedback.append("You provided detailed responses, which is excellent for presenting thorough arguments.")
    
    # Debate duration feedback
    if duration_minutes < 5:
        feedback.append("Consider spending more time developing your arguments. Longer debates allow for deeper exploration of topics.")
    elif duration_minutes > 15:
        feedback.append("You demonstrated strong commitment by sustaining a lengthy debate. This shows dedication to the topic.")
    
    # Add random debate tips
    debate_tips = [
        "When countering an argument, first acknowledge it before presenting your rebuttal.",
        "Using specific examples strengthens your arguments more than general statements.",
        "Try the 'steel man' technique: present your opponent's argument in its strongest form before countering it.",
        "Focus on addressing the strongest points in your opponent's argument, not just the weakest ones.",
        "Maintaining a respectful tone makes your arguments more persuasive than aggressive language.",
        "Cite specific sources when possible to add credibility to your claims.",
        "Use questions strategically to expose flaws in your opponent's reasoning.",
        "Connect abstract principles to concrete impacts to make your arguments more relatable.",
        "Consider the practical implications of your position to strengthen its real-world relevance.",
        "Structure your arguments clearly with a main claim followed by supporting evidence."
    ]
    
    # Add 2 random tips
    feedback.extend(random.sample(debate_tips, 2))
    
    return feedback

# Start the bot, connecting it to the gateway
bot.run(token)
