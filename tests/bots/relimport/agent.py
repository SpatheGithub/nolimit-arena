from .helper import CHOICE


class Agent:
    def __init__(self, config):
        pass

    def act(self, obs):
        return {"action": CHOICE} if CHOICE in obs["legal"] else {"action": "fold"}
