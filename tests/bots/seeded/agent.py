import random


class Agent:
    def __init__(self, config):
        self.rng = random.Random(config["seed"])

    def act(self, obs):
        r = self.rng.random()
        if obs["max_raise_to"] and r < 0.2:
            return {"action": "raise", "amount": self.rng.randint(obs["min_raise_to"], obs["max_raise_to"])}
        if "fold" in obs["legal"] and r < 0.45:
            return {"action": "fold"}
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}

    def observe(self, event):
        self.last = event["hand_id"]
