class Agent:
    def __init__(self, config):
        print("hello from init")

    def act(self, obs):
        print("thinking about", obs["hole"])
        return {"action": "check"} if "check" in obs["legal"] else {"action": "fold"}
