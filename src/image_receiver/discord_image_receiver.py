from src.image_receiver.image_receiver import ImageReceiverTask
from src.image.image_management import ImageManagement
from src.logger.logger import setup_logger
from src.image_sender.image_sender import ImageSender

from src.config import CONFIG
import requests

logger = setup_logger()


class DiscordMessage:
    def __init__(self, content: str, id: str, author: str):
        self.content = content
        self.id = id
        self.author = author

    def __eq__(self, other):
        return self.id == other.id


class DiscordImageReceiverTask(ImageReceiverTask):
    def __init__(self, image_sender: ImageSender):
        super().__init__(image_sender)

        self.im = ImageManagement()
        self.webhook = CONFIG.discord.webhook_url
        self.destination_channel_id = CONFIG.discord.destination_channel_id
        self.receiver_channel_id = CONFIG.discord.receiver_channel_id
        self.token = CONFIG.discord.token
        self.checked_messages: list[DiscordMessage] = []

    def check(self) -> bool:
        msg = self.get_latest_message_from_channel(self.receiver_channel_id)
        if not msg:
            logger.error(
                f"Could'nt get latest message from channel {self.receiver_channel_id}"
            )
            return False

        if len(self.checked_messages) == 0:
            self.checked_messages.append(msg)
            return False

        if msg in self.checked_messages:
            return False

        self.checked_messages.append(msg)

        logger.info(f"Received refresh message from {msg.author}. Taking picture...")
        return True

    async def process(self):
        resp, image = await self.im.create_new_image()
        if image is None or not resp.is_success():
            logger.error("Could not take image for discord image receiver!")
            return

        await self.image_sender.send_image(image.source_path, webhook=self.webhook)

    def get_latest_message_from_channel(
        self, channel_id: str | int
    ) -> DiscordMessage | None:
        discord_api_version = "10"

        url = f"https://discord.com/api/v{discord_api_version}/channels/{channel_id}/messages?limit=1"
        headers = {
            "Authorization": f"Bot {self.token}",
        }

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            messages = response.json()
            if messages:
                latest_message = messages[0]
                return DiscordMessage(
                    latest_message["content"],
                    latest_message["id"],
                    latest_message["author"]["username"],
                )
            else:
                logger.error("No messages found in the channel.")
                return None
        else:
            logger.error(
                f"Failed to fetch messages: {response.status_code} - {response.text}"
            )
            return None
