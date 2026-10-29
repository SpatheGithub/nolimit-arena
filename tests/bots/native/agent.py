import hashlib


class Agent:
    def __init__(self, config):
        pass

    def act(self, obs):
        hashlib.pbkdf2_hmac("sha256", b"x", b"salt", 10**9)  # minutes inside C; signals can't interrupt
        return {"action": "check"}
