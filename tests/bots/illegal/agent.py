class Agent:
    def __init__(self, config):
        self.n = 0

    def act(self, obs):
        self.n += 1
        if self.n % 2:
            return {"action": "raise", "amount": 1}
        return "call"
