import interactions
from interactions import (slash_command, SlashContext, listen, slash_option, OptionType,
                          StringSelectMenu, component_callback, ComponentContext, Embed, File,
                          Button, ButtonStyle, Timestamp, Intents)

from src.image.image_management import ImageManagement
from src.config.config_loader import ConfigLoader
from src.utils.response import Response


config = ConfigLoader()
token = config.config["discord"]["token"]
bot = interactions.Client(token=token, intents=Intents.GUILDS | Intents.ALL)

destination_channel_id = config.config["discord"]["destinationChannelId"]
status_channel_id = config.config["discord"]["statusChannelId"]
refresh_channel_id = config.config["discord"]["refreshChannelId"]
image_management = ImageManagement(image_config=config.config["imageConfig"])

@listen()
async def on_startup():
    global destination_channel
    global status_channel
    destination_channel = bot.get_channel(destination_channel_id)
    status_channel = bot.get_channel(destination_channel_id)
    print("Setupped Channels")

@listen()
async def on_ready():
    print(f"Logged in as {bot.user}")

@listen()
async def on_message_create(ctx):
    print("Recived a message")
    channel_id = int(ctx.message.channel.id)
    if channel_id == refresh_channel_id:
        rsp = image_management.create_new_image()
        if not rsp.is_success():
            print("error. couldnt take image")

        await send_image(image_management.get_latest_image().source_path)


async def send_image(image_path):
    # Ensure destination_channel is available
    if destination_channel:
        await destination_channel.send(file=File(image_path))
        embed = Embed(title="Success", description="Successfully sent the image.", color=0x00FF00)
        await status_channel.send(embed=embed)

        return Response(True, 'Image sent to the destination channel')
    else:
        return Response(False, 'Destination channel not found')


@slash_command(name="clear", description="Clear messages in the channel")
@slash_option(
    name="amount",
    description="Number of messages to clear",
    required=True,
    min_value=1,
    opt_type=OptionType.INTEGER
)
async def clear(ctx: SlashContext, amount: int):
    await ctx.channel.purge(limit=amount)
    await ctx.send(f"Cleared {amount} messages!", ephemeral=True)

def start_discord_bot():
    bot.start()

if __name__ == "__main__":
    start_discord_bot()
