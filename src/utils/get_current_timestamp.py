from datetime import datetime


def get_current_timestamp():
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M-%S")
    return timestamp
