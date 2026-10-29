class Agent:
    def __init__(self, config):
        pass

    def act(self, obs):
        if obs["min_raise_to"]:
            return {"action": "raise", "amount": obs["min_raise_to"]}
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}
