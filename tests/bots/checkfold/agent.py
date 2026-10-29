class Agent:
    def __init__(self, config):
        pass

    def act(self, obs):
        if obs["phase"] == "discard":
            return {"action": "discard", "cards": obs["hole"][:obs["n_discard"]]}
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
