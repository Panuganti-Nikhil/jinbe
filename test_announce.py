import discord
from discord.ext import commands
import asyncio

# Test if the announce function is properly defined
async def test_announce_command():
    # Create a mock bot
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='/', intents=intents)
    
    # Import the announce function from jinbe.py
    try:
        # We'll need to modify this approach since we can't directly import
        # Let's just check if the function exists in the file
        with open("jinbe.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        # Check if the announce function is properly defined
        if "@bot.tree.command(name=\"announce\"" in content:
            print("✅ Announce command decorator found")
        else:
            print("❌ Announce command decorator not found")
            
        if "async def announce(interaction: discord.Interaction, message: str):" in content:
            print("✅ Announce function definition found")
        else:
            print("❌ Announce function definition not found")
            
        # Check if the function is properly closed
        lines = content.split('\n')
        announce_start = -1
        announce_end = -1
        
        for i, line in enumerate(lines):
            if "@bot.tree.command(name=\"announce\"" in line:
                announce_start = i
            elif announce_start != -1 and i > announce_start:
                # Look for the next command decorator or the end of the file
                if "@bot.tree.command" in line or (i == len(lines) - 1):
                    announce_end = i
                    break
                    
        if announce_start != -1 and announce_end != -1:
            print(f"✅ Announce function appears to be properly bounded (lines {announce_start}-{announce_end})")
        else:
            print("❌ Could not determine announce function boundaries")
            
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    asyncio.run(test_announce_command())