import socket
import time
from typing import Tuple

def do_i_have_internet() -> Tuple[bool, float]:
    try:
        start_time = time.time()  # Record the start time
        # Try to connect to a well-known DNS server (e.g., Google's DNS)
        socket.create_connection(('8.8.8.8', 53), timeout=2)
        end_time = time.time()  # Record the end time

        response_time = end_time - start_time  # Calculate the response time
        return True, response_time  # Return internet status and response time

    except OSError:
        return False, float('inf')  # Indicate no internet and invalid response time


if __name__ == "__main__":
    print(do_i_have_internet())
