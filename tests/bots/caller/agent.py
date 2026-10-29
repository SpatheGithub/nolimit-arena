class Agent:
    def __init__(self, config):
        pass

    def act(self, obs):
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}
