import time


class Agent:
    def __init__(self, config):
        self.n = 0

    def act(self, obs):
        self.n += 1
        if self.n % 4 == 0:
            end = time.thread_time_ns() + 3_000_000
            while time.thread_time_ns() < end:
                pass
        return {"action": "call"} if "call" in obs["legal"] else {"action": "check"}
