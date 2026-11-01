# Today's event: full-opus-002

Everything about today's rules is in this file. `kit/RULES.md` has the dealer's rules for every variant (blinds, all-ins, side pots, ties), and `kit/event.json` has the same facts as data.

## The variant: nlhe

**Deck.** 52 cards: ranks 2 3 4 5 6 7 8 9 T J Q K A (low to high), suits clubs, diamonds, hearts, spades.

**Streets.** In order, each street does the following:

| Street | Discard first | Hole cards dealt | Board cards dealt | Betting round |
| :- | -: | -: | -: | :- |
| preflop |  | 2 |  | yes |
| flop |  |  | 3 | yes |
| turn |  |  | 1 | yes |
| river |  |  | 1 | yes |

Each player ends with 2 hole cards; the board ends with 5 cards.

**Making a hand.** Your hand is the best five cards out of your hole cards and the board combined, in any mix.

**Hand rankings, strongest first.** A straight is five consecutive ranks of this deck: the lowest is A-2-3-4-5, the highest T-J-Q-K-A.

| Rank | Hand | Example (hole · board) | How often a player ends with it |
| -: | :- | :- | -: |
| 1 | Straight flush | 8d 5d · Jd 7d 4d Qc 6d | 0.025% |
| 2 | Four of a kind | 2d 3c · 2s 2c 2h Th 7d | 0.149% |
| 3 | Full house | Ad 5c · Th Ts 5h 8d Tc | 2.534% |
| 4 | Flush | 4c Jc · Ac 3c 6c 3s 9s | 2.941% |
| 5 | Straight | 7s Jc · Ts 5c Tc 8h 9s | 4.651% |
| 6 | Three of a kind | 3s Ks · 7d Kh Kd Tc 8s | 4.831% |
| 7 | Two pair | 9s 2d · 8c 8s Jh 2c Kc | 23.547% |
| 8 | One pair | Ac 9c · 9h Qd 8c 5d 3h | 44.028% |
| 9 | High card | 9c 6d · Kh 5h Jd 3h 7c | 17.294% |

Frequencies were measured on 200,000 random deals of this variant: one player's final cards.

**No-limit.** You may bet or raise any amount from the minimum up to your whole stack. The minimum raise is the largest full raise so far on the street, never less than the big blind.

## Table and scoring

- **Seats and stacks.** 8 seats, 2,000 chips each.
- **End of a table.** One player has every chip, or 200 hands have been played. At the cap, the survivors split the points of the places still open by ICM (exactly `kit/icm.py`).
- **Blinds.** They rise every 25 hands; past the last level, it repeats.

| Level | Hands | Small blind | Big blind | Ante |
| -: | :- | -: | -: | -: |
| 1 | 1–25 | 10 | 20 |  |
| 2 | 26–50 | 20 | 40 |  |
| 3 | 51–75 | 40 | 80 |  |
| 4 | 76–100 | 80 | 160 |  |
| 5 | 101–125 | 160 | 320 |  |
| 6 | 126–150 | 320 | 640 |  |
| 7 | 151–175 | 640 | 1280 |  |
| 8 | 176–200 | 1280 | 2560 |  |

**Points by finishing place.** Players eliminated in the same hand place by their stacks at the start of that hand; exactly equal stacks share those places' points.

| 1st | 2nd | 3rd | 4th | 5th | 6th | 7th | 8th |
| -: | -: | -: | -: | -: | -: | -: | -: |
| 100 | 60 | 40 | 25 | 15 | 10 | 5 | 0 |

## Tournament plan

- **Build window.** 60 minutes. Submit with `python kit/submit.py`; at most one accepted submission every 300 seconds, and your latest accepted one plays.
- **Tournaments.** 6: T1 weight 1, T2 weight 2, T3 weight 3, T4 weight 4, T5 weight 5, T6 weight 6. Each is 1000 iterations; every iteration seats every bot once at random tables. Your score is your average points per table.
- **Between tournaments.** A 20-minute patch window to submit fixes; the bot that plays a tournament is frozen when it starts.
- **Limits.** 1 ms of CPU per `act()` call; `__init__` 2 s per table; import 30 s; `bot/` at most 100 MB; standard library plus numpy.


## The card as data

```json
{
 "event": "full-opus-002",
 "variant": {
  "name": "nlhe",
  "streets": [
   {
    "name": "preflop",
    "discard": 0,
    "hole": 2,
    "board": 0,
    "bet": true
   },
   {
    "name": "flop",
    "discard": 0,
    "hole": 0,
    "board": 3,
    "bet": true
   },
   {
    "name": "turn",
    "discard": 0,
    "hole": 0,
    "board": 1,
    "bet": true
   },
   {
    "name": "river",
    "discard": 0,
    "hole": 0,
    "board": 1,
    "bet": true
   }
  ],
  "ranks": "23456789TJQKA",
  "suits": "cdhs",
  "card_use": {
   "hole_min": 0,
   "hole_max": 5
  },
  "ranking": {
   "order": [
    "high_card",
    "pair",
    "two_pair",
    "trips",
    "straight",
    "flush",
    "full_house",
    "quads",
    "straight_flush"
   ],
   "ace_low": true
  },
  "betting": {
   "structure": "no_limit",
   "fl_bets": [],
   "fl_cap": 4
  }
 },
 "points": [
  100,
  60,
  40,
  25,
  15,
  10,
  5,
  0
 ],
 "blinds": [
  [
   10,
   20,
   0
  ],
  [
   20,
   40,
   0
  ],
  [
   40,
   80,
   0
  ],
  [
   80,
   160,
   0
  ],
  [
   160,
   320,
   0
  ],
  [
   320,
   640,
   0
  ],
  [
   640,
   1280,
   0
  ],
  [
   1280,
   2560,
   0
  ]
 ],
 "level_hands": 25,
 "hand_cap": 200,
 "seats": 8,
 "starting_stack": 2000,
 "decision_limit_ms": 1.0,
 "iterations": 1000,
 "tournaments": 6,
 "timing": "thread_cpu",
 "hang_watchdog_ms": 50,
 "init_limit_s": 2,
 "import_limit_s": 30,
 "bot_size_limit_mb": 100,
 "allowed_packages": [
  "numpy"
 ],
 "cooldown_seconds": 300,
 "localsim_max_tables": 1000,
 "localsim_max_seconds": 240,
 "build_minutes": 60,
 "patch_minutes": 20,
 "seed": 4281125837,
 "points_name": "standard",
 "blinds_name": "doubling"
}
```
