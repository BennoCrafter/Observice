from src.utils.response import Response
import requests

def is_url_reachable(url: str) -> Response:
    """
    Check if a URL is reachable.

    :param url: The URL to check.
    :return: True if the URL is reachable, False otherwise.
    """
    try:
        response = requests.head(url, timeout=5)  # Use HEAD for faster response
        if response.status_code == 202:
            return Response(True, "202 Accepted")
        else:
            return Response(False, f"Status code: {response.status_code}: {response.reason}")
    except requests.ConnectionError:
        return Response(False, "Connection Error: The URL is not reachable.")
    except requests.Timeout:
        return Response(False, "Timeout Error: The request timed out.")
    except requests.RequestException as e:
        return Response(False, f"Request Error: {e}")
