from config import CONFIG
import simsvc


def test_config_is_valid():
    simsvc.validate(CONFIG)
