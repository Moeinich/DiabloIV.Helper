from time import sleep
from random import uniform

from helper import config_helper, logging_helper
from bot import rotation


class Manager:
    def __init__(self) -> None:
        self.cfg = self.reload_config()

    def reload_config(self):
        try:
            return config_helper.read_config() or {}
        except Exception as ex:
            logging_helper.log_debug("Failed to read config: %s" % ex)
            return {}

    def game_manager(self, move: bool = True) -> None:
        try:
            rotation.rotation()
        except Exception as ex:
            logging_helper.log_debug("game_manager error: %s" % ex)
