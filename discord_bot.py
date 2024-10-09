import interactions
from interactions import (slash_command, SlashContext, listen, slash_option, OptionType,
                          StringSelectMenu, component_callback, ComponentContext, Embed, File,
                          Button, ButtonStyle, Timestamp, Intents)

from pathlib import Path

from src.image.image_management import ImageManagement
from src.config.config_loader import ConfigLoader
from src.utils.response import Response
from src.logger.logger import setup_logger
from src.config.config_models import ImageConfig

logger = setup_logger(logger_name=__name__, log_file="logs/observice_log.log")


@listen()
async def on_startup():
    global destination_channel
    global status_channel
    destination_channel = bot.get_channel(destination_channel_id)
    status_channel = bot.get_channel(status_channel_id)
    logger.info("Configured channels!")

@listen()
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

@listen()
async def on_message_create(ctx):
    channel_id = int(ctx.message.channel.id)
    if channel_id == refresh_channel_id:
        if ctx.message.content == "refresh":
            rsp = image_management.create_new_image()
            if not rsp.is_success():
                logger.error("Error! Could'nt take image")
                return

            await send_image(image_management.get_latest_image().source_path)


async def send_image(image_path) -> Response:
    # Ensure destination_channel is available
    if destination_channel:
        await destination_channel.send(file=File(image_path))
        embed = Embed(title="Success", description="Successfully sent the image.", color=0x00FF00)
        await status_channel.send(embed=embed)

        logger.info("Image sent to the destination channel")
        return Response(True, 'Image sent to the destination channel')
    else:
        logger.error("Destination channel not found!")
        return Response(False, 'Destination channel not found!')


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


if __name__ == "__main__":
    config = ConfigLoader()
    token = config.config["discord"]["token"]
    bot = interactions.Client(token=token, intents=Intents.GUILDS | Intents.ALL)
    destination_channel_id = config.config["discord"]["destinationChannelId"]
    status_channel_id = config.config["discord"]["statusChannelId"]
    refresh_channel_id = config.config["discord"]["refreshChannelId"]
    # TODO TEMP SOLUTION
    # dict imageConfig --> dataclass ImageConfig
    dict_img_config = config.config["imageConfig"]
    img_config = ImageConfig(images_dir=Path(dict_img_config["imagesDir"]) , quality=dict_img_config["quality"] , type=dict_img_config["type"])
    image_management = ImageManagement(image_config=img_config)
    bot.start()
