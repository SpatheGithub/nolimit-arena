class Agent:
    def __init__(self, config):
        self.hung = False

    def act(self, obs):
        if not self.hung:
            self.hung = True
            try:
                while True:
                    pass
            except Exception:
                pass
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}
