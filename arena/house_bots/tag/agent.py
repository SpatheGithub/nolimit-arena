"""tag: tight-aggressive with stack-depth modes, the shared core in
_common.TagCore.

Deep: opening ranges by the number of players left to act (wider when the
players behind fold to raises), 3-bets with premiums sized for position,
calls priced by equity against the raiser's estimated range, continuation
bets (no air into calling stations) and barrels, value bets that get thinner
against loose players, calls priced by made-hand class and draws, pot-relative
sizing. At or below 15 big blinds: push/fold by chip EV, with each caller's
range from the calling chart blended with its in-table VPIP and the shover's
range from the pushing chart and its raise frequency, plus a survival premium
on the equity needed to risk busting that shrinks as players bust.
Fixed-limit and Omaha-style variants get simpler versions of the same plan.

Strength: the reference strong bot; it should clearly beat every quick-build
pattern in the zoo.
"""

from ._common import TagCore


class Agent(TagCore):
    pass
