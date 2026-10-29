# Dealer rules

These are the rules the arena's dealer follows at every table. Today's variant (deck, streets, card use and hand rankings) is in `EVENT.md`; everything below applies to every variant. The engine source is in `kit/engine/` if you want to check a detail.

## Seats, button and blinds

- A table has up to 8 seats. Seat ids stay fixed for the whole table and are reshuffled at every new table.
- **Button.** The first button is drawn at random. After each hand it moves to the next seat clockwise that still has chips. There is no dead button and there are no missed blinds, so after an elimination a player can occasionally skip a blind or post one twice in a row.
- **Antes and blinds.** Antes, when the schedule has them, are posted first, by everyone, as dead money: they don't count toward your bet on the first street. Then the small blind (first seat left of the button) and the big blind (the next seat) post.
- **Heads-up.** With two players, the button posts the small blind and the other player the big blind.
- **Short stacks.** A player who can't cover the ante or a blind posts what they have and is all-in. If a blind is all-in for less, the amount to call is the largest blind actually posted.
- **Blind levels.** They rise every 25 hands, following the schedule in `EVENT.md`. Past the end of the schedule, the last level repeats.

## Order of action

- **First street.** The player left of the big blind acts first. Heads-up, the button (small blind) acts first.
- **Later streets.** The first player left of the button who is still in the hand acts first. Heads-up, that is the big blind.
- **Skipped turns.** You are only asked to act when you have a real decision. If everyone else is all-in or has folded and you have already matched the bet, you are skipped.

## Betting

- **Amounts are raise-to totals for the current street.** Raising "to 300" means your chips in on this street become 300, counting a blind you posted on the first street.
- **Action names.** `bet` and `raise` mean the same. `call` with nothing to call counts as a check. `allin` raises to your whole stack, or calls if raising isn't allowed.
- **Folding** is only allowed when you face a bet. A fold when you could check is illegal and is replaced by a check.
- **Your bounds.** `obs` always gives `to_call`, `min_raise_to` and `max_raise_to`. Any amount in that range is legal; anything outside it is illegal.

### No-limit

- **Minimum raise.** A raise must be at least the largest full raise so far on this street, and never less than the big blind. Example: blinds 10/20, a raise to 60 (a raise of 40) means the next raise must go to at least 100.
- **Maximum raise.** You may always raise up to your whole stack.

### Pot-limit

- **Maximum raise.** You may raise by at most the size of the pot after your call: current bet + pot (including all bets on the table) + your call.

### Fixed-limit

- **Raise size.** Bets and raises are exactly one bet. The bet size per street is in `EVENT.md`.
- **Cap.** At most 4 bets and raises per street; the blinds don't count.

### All-ins

- **Short all-in.** You may always go all-in. An all-in that raises by less than a full raise does **not** reopen the betting. A player who already acted on this street may then only call or fold, unless the total they now face since their own last action is at least a full raise; several short all-ins can add up to one. Players who haven't acted yet may raise as usual.
- **No point raising.** If no other player could call a raise, because they are all-in or folded, you can only call or fold.

## Pots and showdown

- **Uncalled chips.** Chips nobody matched go back to the bettor when the betting round ends.
- **Side pots.** When players are all-in for different amounts, the chips form a main pot and side pots. You can only win from pots you contributed to at that level.
- **Running it out.** When no more betting is possible, the remaining cards are dealt straight to showdown.
- **Showdown.** Every hand still in is shown and you receive all of them through `observe()`. Each pot goes to the best hand among its contenders, using today's card-use rule and hand rankings.
- **Ties and odd chips.** Players who win nothing are mucked, and pots with the same remaining contenders are merged. Each pot then splits evenly among the tied winners. Any odd chips go to the first winner left of the button.

## Eliminations, places and the end of a table

- **Busting.** A player with no chips after a hand is eliminated. The first player out finishes last.
- **Several busts in one hand.** Players eliminated in the same hand finish in order of their stacks at the start of that hand, the larger stack placing higher. Exactly equal stacks share those places and split their points evenly.
- **End of the table.** The table ends when one player holds every chip (1st place), or after 200 hands.
- **At the 200-hand cap.** The surviving players split the points of the places still open by ICM (Malmuth–Harville), using exactly `kit/icm.py`.

## Discards (some variants)

- **When.** In variants with discards, each player still in the hand discards the stated number of hole cards at the start of that street, before that street's cards are dealt. The order is clockwise from the left of the button. You discard by returning the cards you throw away.
- **Failures.** If your discard fails (timeout, error or an illegal choice), your first hole cards in dealing order are discarded for you.

## Cards

- **Notation.** Cards are two characters: rank `23456789TJQKA` then suit `cdhs`, for example `"As"` or `"Td"`.
- **Dealing.** Cards are dealt one at a time, starting left of the button. There are no burn cards.

## When your bot fails

- **Substitution.** If `act()` uses more than its time limit, raises an exception or returns an illegal action, the dealer folds for you, or checks when checking is free. Every substitution is counted in your results.
- **How time is measured.** The limit is CPU time for the call (thread CPU), normalized to the machine's fastest cores, so landing on a slower core doesn't count against you. A call still running after 50 ms of wall time is interrupted. Aim well under the limit: the timings `kit/check_bot.py` shows on a busy machine are noisier than the referee's.
