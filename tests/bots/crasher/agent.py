class Agent:
    def __init__(self, config):
        self.n = 0

    def act(self, obs):
        self.n += 1
        if self.n % 3 == 0:
            raise RuntimeError("boom")
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}
