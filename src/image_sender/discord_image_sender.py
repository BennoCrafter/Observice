from src.image_sender.image_sender import ImageSender
from pathlib import Path
from src.utils.response import Response
from src.logger.logger import setup_logger
import requests

logger = setup_logger()


class DiscordImageSender(ImageSender):
    async def send_image(self, image_path: Path | str, **kwargs) -> Response:
            webhook = kwargs.get("webhook")
            if webhook is None:
                logger.error("No webhook URL provided")
                return Response(False, "No webhook URL provided")

            if not webhook.startswith("http"):
                logger.error(f"Invalid webhook URL: {webhook}")
                return Response(False, f"Invalid webhook URL {webhook}")

            try:
                with open(image_path, 'rb') as image_file:
                    files = {
                        'file': (str(image_path), image_file, 'image/jpeg')
                    }

                    data = {
                        'content': "<@773082338162507776>"
                    }

                    response = requests.post(webhook, files=files, data=data)

                if response.status_code != 200:
                    logger.error(f"Unexpected status code {response.status_code} when sending message to Discord")
                    return Response(False, f"Unexpected status code {response.status_code} when sending message to Discord")
                else:
                    logger.info("Message sent successfully with image!")
                    return Response(True, "Message sent successfully with image!")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending message to Discord: {e}")
                return Response(False, f"Error sending message to Discord: {e}")
