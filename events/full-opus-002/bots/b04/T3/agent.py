import os
import pickle
import random
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, 'evtab.pkl'), 'rb') as _f:
    _T = pickle.load(_f)
RANKT = _T['rank']
SUITT = _T['suited']
with open(os.path.join(_DIR, 'pf.pkl'), 'rb') as _f:
    _P = pickle.load(_f)
EQR = _P['eqr']
LEVELS = _P['levels']
PCT = _P['pct']
EQ1 = _P['eq1']
MULTI = _P['multi']
RC = _P['rc']
RC_LEVELS = sorted(RC.keys())
with open(os.path.join(_DIR, 'icm.pkl'), 'rb') as _f:
    VT = pickle.load(_f)
PTS = [100, 60, 40, 25, 15, 10, 5, 0]


def vicm(n, chips, total):
    """ICM points of holding `chips` among n players (others equal)."""
    if n < 2:
        return PTS[0]
    if n > 8:
        n = 8
    if chips <= 0:
        return PTS[n - 1]
    f = chips / total * 200.0
    i = int(f)
    row = VT[n]
    if i >= 200:
        return row[200]
    t = f - i
    return row[i] * (1 - t) + row[i + 1] * t

RANKS = '23456789TJQKA'
SUITS = 'cdhs'
CID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
RANK_KEYS = (0, 1, 5, 22, 98, 453, 2031, 8698, 22854, 83661, 262349, 636345, 1479181)
COUNT = 1 << 23
KEY = tuple(((RANK_KEYS[c >> 2] + COUNT) << 16) | (1 << 4 * (c & 3)) for c in range(52))
RANK_BIT = tuple(1 << (c >> 2) for c in range(52))
SB = {8 << 4 * s: tuple(RANK_BIT[c] if c & 3 == s else 0 for c in range(52)) for s in range(4)}


def ev(cards):
    s = 0x3333
    for c in cards:
        s += KEY[c]
    fl = s & 0x8888
    if fl:
        b = SB[fl]
        m = 0
        for c in cards:
            m += b[c]
        f = SUITT[m]
        r = RANKT[s >> 16]
        return f if f > r else r
    return RANKT[s >> 16]


def hclass(c1, c2):
    r1, r2 = c1 >> 2, c2 >> 2
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    if hi == lo or (c1 & 3) == (c2 & 3):
        return hi * 13 + lo
    return lo * 13 + hi


def lvl_index(p):
    # index into LEVELS nearest to p
    best = 0
    bd = 9.0
    for i, l in enumerate(LEVELS):
        d = abs(l - p)
        if d < bd:
            bd = d
            best = i
    return best


def eq_vs_range(h, p):
    """equity of class h vs top-p range (interpolated)."""
    if p <= LEVELS[0]:
        return EQR[h][0]
    if p >= 1.0:
        return EQR[h][-1]
    for i in range(1, len(LEVELS)):
        if LEVELS[i] >= p:
            a, b = LEVELS[i - 1], LEVELS[i]
            t = (p - a) / (b - a)
            return EQR[h][i - 1] * (1 - t) + EQR[h][i] * t
    return EQR[h][-1]


def rc_for(p):
    if p >= 0.95:
        return None
    for l in RC_LEVELS:
        if l >= p:
            return RC[l]
    return None


class Stat:
    __slots__ = ('hands', 'vpip', 'pfr', 'fr_opp', 'fr_fold', 'steal_opp', 'steal_fold',
                 'pf_allin', 'call_allin_opp', 'call_allin', 'post_bets', 'post_calls',
                 'fold_bet_opp', 'fold_bet', 'sd', 'sd_pct', 'sh_n', 'sh_pct')

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.fr_opp = 0
        self.fr_fold = 0
        self.steal_opp = 0
        self.steal_fold = 0
        self.pf_allin = 0
        self.call_allin_opp = 0
        self.call_allin = 0
        self.post_bets = 0
        self.post_calls = 0
        self.fold_bet_opp = 0
        self.fold_bet = 0
        self.sd = 0
        self.sd_pct = 0.0
        self.sh_n = 0
        self.sh_pct = 0.0


class Agent:
    def __init__(self, config):
        self.seat = config['seat']
        self.rng = random.Random(config['seed'])
        self.nseats = config.get('seats', 8)
        self.stats = [Stat() for _ in range(self.nseats)]
        self.points = config.get('points', [100, 60, 40, 25, 15, 10, 5, 0])
        self.hand_id = -1
        self.pf_aggressor = None

    # ------------------------------------------------------------------ stats
    def observe(self, event):
        try:
            if event.get('type') != 'hand_end':
                return
            self._update_stats(event)
        except Exception:
            pass

    def _update_stats(self, event):
        hist = event.get('history') or []
        st = self.stats
        seen = set()
        vp = set()
        pr = set()
        raised = False
        cur_bet = 0
        bb_amt = 0
        allin_seen = False
        stacks_start = {}
        for rec in hist:
            si, seat, act, amt = rec[0], rec[1], rec[2], rec[3]
            if si != 0:
                continue
            if act == 'bb':
                bb_amt = amt
                cur_bet = max(cur_bet, amt)
            if act in ('sb', 'bb', 'ante'):
                seen.add(seat)
                continue
            seen.add(seat)
            if seat == self.seat:
                if act == 'raise':
                    raised = True
                    cur_bet = amt
                continue
            if raised:
                st[seat].fr_opp += 1
                if act == 'fold':
                    st[seat].fr_fold += 1
            if act in ('call', 'raise'):
                vp.add(seat)
            if act == 'raise':
                pr.add(seat)
                raised = True
                cur_bet = amt
        # all-in tracking (start stacks = end stacks - payoffs)
        try:
            ends = event.get('stacks') or []
            pay = event.get('payoffs') or {}
            start = {}
            for s in seen:
                pv = pay.get(s, pay.get(str(s), 0))
                start[s] = ends[s] - pv
            committed = {}
            shover = None
            for rec in hist:
                si, seat, act, amt = rec[0], rec[1], rec[2], rec[3]
                if si != 0:
                    continue
                if act == 'ante':
                    continue
                if act in ('sb', 'bb', 'call', 'raise'):
                    if act == 'raise':
                        committed[seat] = amt
                        if seat in start and amt >= start[seat] - 1 and amt > 0:
                            if seat != self.seat:
                                st[seat].pf_allin += 1
                            if shover is None:
                                shover = seat
                                continue
                    elif act == 'call':
                        if shover is not None and seat != self.seat and seat != shover:
                            st[seat].call_allin_opp += 1
                            st[seat].call_allin += 1
                        continue
                    else:
                        committed[seat] = amt
                        continue
                if act == 'fold' and shover is not None and seat != self.seat:
                    st[seat].call_allin_opp += 1
            if shover is not None and shover != self.seat:
                shown0 = event.get('shown') or {}
                cs = shown0.get(shover, shown0.get(str(shover)))
                if cs and len(cs) == 2:
                    st[shover].sh_n += 1
                    st[shover].sh_pct += PCT[hclass(CID[cs[0]], CID[cs[1]])]
        except Exception:
            pass
        for s in seen:
            if s != self.seat:
                st[s].hands += 1
        for s in vp:
            st[s].vpip += 1
        for s in pr:
            st[s].pfr += 1
        # postflop aggression / folds to bets
        bet_on = {}
        for rec in hist:
            si, seat, act, amt = rec[0], rec[1], rec[2], rec[3]
            if si == 0 or seat == self.seat:
                if si > 0 and act in ('raise', 'bet'):
                    bet_on[si] = True
                continue
            if act in ('raise', 'bet'):
                st[seat].post_bets += 1
                bet_on[si] = True
            elif act == 'call':
                st[seat].post_calls += 1
                st[seat].fold_bet_opp += 1
            elif act == 'fold':
                st[seat].fold_bet_opp += 1
                st[seat].fold_bet += 1
        shown = event.get('shown') or {}
        for s, cards in shown.items():
            try:
                s = int(s)
                if s == self.seat or len(cards) != 2:
                    continue
                h = hclass(CID[cards[0]], CID[cards[1]])
                st[s].sd += 1
                st[s].sd_pct += PCT[h]
            except Exception:
                pass

    def _pfr(self, s):
        x = self.stats[s]
        return (x.pfr + 0.18 * 6) / (x.hands + 6)

    def _vpip(self, s):
        x = self.stats[s]
        return (x.vpip + 0.28 * 6) / (x.hands + 6)

    def _fold_to_raise(self, s):
        x = self.stats[s]
        return (x.fr_fold + 0.7 * 5) / (x.fr_opp + 5)

    def _fold_to_bet(self, s):
        x = self.stats[s]
        return (x.fold_bet + 0.45 * 5) / (x.fold_bet_opp + 5)

    # ------------------------------------------------------------------ act
    def act(self, obs):
        try:
            a = self._act(obs)
        except Exception:
            a = None
        if a is None:
            if 'check' in obs['legal']:
                return {'action': 'check'}
            return {'action': 'fold'}
        return a

    def _act(self, obs):
        if obs.get('phase') == 'discard':
            return {'action': 'discard', 'cards': obs['hole'][:obs['n_discard']]}
        hole = [CID[c] for c in obs['hole']]
        board = [CID[c] for c in obs['board']]
        if obs['street_index'] == 0:
            return self._preflop(obs, hole)
        return self._postflop(obs, hole, board)

    # helpers
    def _raise(self, obs, amt):
        legal = obs['legal']
        if 'raise' not in legal and 'bet' not in legal:
            return self._call(obs)
        lo, hi = obs['min_raise_to'], obs['max_raise_to']
        amt = int(amt)
        if amt >= hi * 0.85:
            amt = hi
        amt = max(lo, min(hi, amt))
        return {'action': 'raise', 'amount': amt}

    def _call(self, obs):
        if 'call' in obs['legal']:
            return {'action': 'call'}
        return {'action': 'check'}

    def _fold(self, obs):
        if 'check' in obs['legal']:
            return {'action': 'check'}
        return {'action': 'fold'}

    def _allin(self, obs):
        legal = obs['legal']
        if 'raise' in legal or 'bet' in legal:
            return {'action': 'raise', 'amount': obs['max_raise_to']}
        return self._call(obs)

    def _order(self, obs):
        """alive seats in preflop action order (UTG first ... BB last)."""
        alive = sorted(obs['alive'])
        bb = obs['bb_seat']
        n = len(alive)
        if bb in alive:
            i = alive.index(bb)
        else:
            i = 0
        return [alive[(i + 1 + k) % n] for k in range(n)]

    # ------------------------------------------------------------------ preflop
    def _preflop(self, obs, hole):
        me = self.seat
        h = hclass(hole[0], hole[1])
        pct = PCT[h]
        bb = max(obs['bb'], 1)
        stacks = obs['stacks']
        bets = obs['bets']
        pot = obs['pot']
        to_call = obs['to_call']
        my_bet = bets[me]
        my_total = stacks[me] + my_bet
        in_hand = obs['in_hand']
        order = self._order(obs)
        my_idx = order.index(me) if me in order else 0
        behind = [s for s in order[my_idx + 1:] if s in in_hand and stacks[s] > 0]
        others = [s for s in in_hand if s != me]
        # max total of others (for effective stack)
        opp_tot = max([stacks[s] + bets[s] for s in others] or [0])
        eff = min(my_total, opp_tot)
        eff_bb = eff / bb
        hist = [r for r in obs['history'] if r[0] == 0]
        raises = [r for r in hist if r[2] == 'raise']
        limpers = [r[1] for r in hist if r[2] == 'call']
        cur = max(bets) if bets else 0
        n_alive = len(obs['alive'])

        if not raises:
            # unopened (maybe limpers)
            if to_call == 0:
                # BB option with limpers
                if pct <= 0.12 and eff_bb > 12:
                    return self._raise(obs, cur + bb * (3 + len(limpers)))
                if pct <= 0.20 and eff_bb <= 12:
                    return self._allin(obs)
                return {'action': 'check'}
            # push/fold zone
            if eff_bb <= 14 or (my_total / bb) <= 14:
                lim = [x for x in limpers if x in in_hand and x != me and stacks[x] > 0]
                return self._shove_decision(obs, h, behind + lim, pot, my_total, bb, set(lim))
            # open raise
            nb = len(behind)
            base = {0: 0.0, 1: 0.45, 2: 0.36, 3: 0.27, 4: 0.21, 5: 0.17, 6: 0.14, 7: 0.12}.get(nb, 0.11)
            if n_alive == 2:
                base = 0.72
            elif n_alive == 3 and nb == 2:
                base = 0.44
            # adjust by fold tendencies of players behind
            if behind:
                ftr = sum(self._fold_to_raise(s) for s in behind) / len(behind)
                base *= 0.7 + 0.6 * (ftr - 0.5) + 0.3
            if limpers:
                base = min(base, 0.14)
            if pct <= base:
                size = bb * (2.3 if nb <= 2 else 2.5) + len(limpers) * bb
                if limpers:
                    size += bb
                return self._raise(obs, size)
            # SB complete with decent hand vs BB
            if nb == 1 and pct <= 0.6 and to_call <= bb / 2 and eff_bb > 20:
                return self._call(obs)
            return self._fold(obs)

        # facing a raise
        last = raises[-1]
        raiser = last[1]
        raise_to = last[3]
        n_raises = len(raises)
        raiser_total = stacks[raiser] + bets[raiser]
        raiser_allin = stacks[raiser] == 0
        # estimate raiser range
        pfr = self._pfr(raiser)
        if n_raises == 1:
            r_range = min(0.6, max(0.05, pfr * 1.1))
        elif n_raises == 2:
            r_range = min(0.3, max(0.025, pfr * 0.35))
        else:
            r_range = min(0.15, max(0.02, pfr * 0.18))
        # shove ranges are wider when short
        rb = raiser_total / bb
        if raiser_allin or raise_to >= 0.6 * raiser_total:
            r_range = max(r_range, min(0.6, 1.6 / max(rb, 1.0) + 0.04)) if n_raises == 1 else r_range
            xr = self.stats[raiser]
            if xr.hands >= 10 and n_raises <= 2:
                freq = xr.pf_allin / xr.hands
                r_range = max(r_range, min(0.85, freq * 1.6))
            if xr.sh_n >= 2 and n_raises <= 2:
                r_est = max(0.03, min(0.9, 2.0 * xr.sh_pct / xr.sh_n))
                r_range = (r_range * 2.0 + r_est * xr.sh_n) / (2.0 + xr.sh_n)
        # multiple opponents still in -> tighten
        # short-handed: PFR measured at a full table understates late-position ranges
        if n_raises == 1 and n_alive <= 3:
            shove_like = raiser_allin or raise_to >= 0.6 * raiser_total
            if n_alive == 2:
                r_range = max(r_range, min(0.85, 3.5 / max(rb, 1.0) + 0.22) if shove_like else 0.55)
            elif raiser != obs['bb_seat']:
                r_range = max(r_range, min(0.7, 2.5 / max(rb, 1.0) + 0.12) if shove_like else 0.35)
        callers_after = [r[1] for r in hist if r[2] == 'call' and hist.index(r) > hist.index(last)]
        eq = eq_vs_range(h, r_range)
        if callers_after:
            eq *= 0.85 ** len(callers_after)
        # chips required
        call_amt = min(to_call, stacks[me])
        final_pot_if_call = pot + call_amt
        need = call_amt / (final_pot_if_call + 0.0)
        commit = call_amt >= 0.45 * my_total or raiser_allin or eff_bb <= 18
        if commit:
            total = sum(stacks) + pot
            my_behind = stacks[me]
            v_fold = vicm(n_alive, my_behind, total)
            # call (for the whole effective stack) vs raiser
            E = min(my_total, raiser_total)
            uncalled = max(0, bets[raiser] - E)
            win_c = my_behind + pot - uncalled + (E - bets[raiser] if bets[raiser] < E else 0)
            lose_c = my_behind - (E - my_bet)
            n_w = n_alive - 1 if raiser_total <= my_total else n_alive
            v_call = eq * vicm(n_w, win_c, total) + (1 - eq) * vicm(n_alive, lose_c, total)
            best = v_fold
            choice = 'fold'
            if raiser_allin or E <= bets[raiser]:
                if v_call > best:
                    choice = 'call'
            else:
                # shove: raiser folds sometimes
                pc = 0.45 if (raiser_total - bets[raiser]) > 1.5 * bets[raiser] else 0.8
                if callers_after:
                    pc = min(0.9, pc + 0.25 * len(callers_after))
                eq_c = eq_vs_range(h, max(0.02, r_range * pc))
                if callers_after:
                    eq_c *= 0.85 ** len(callers_after)
                v_shove = (1 - pc) * vicm(n_alive, my_behind + pot, total) + pc * (
                    eq_c * vicm(n_w, win_c, total) + (1 - eq_c) * vicm(n_alive, lose_c, total))
                if v_shove > best:
                    best = v_shove
                    choice = 'shove'
                if v_call > best and call_amt >= 0.45 * my_total:
                    choice = 'call'
            if choice == 'call':
                return self._call(obs)
            if choice == 'shove':
                return self._allin(obs)
            return self._fold(obs)
        # deep: 3-bet / call / fold
        if eq >= 0.62 or pct <= 0.025:
            if eff_bb <= 30:
                if pct <= 0.025:
                    return self._allin(obs)
                total = sum(stacks) + pot
                my_behind = stacks[me]
                E = min(my_total, raiser_total)
                win_c = my_behind + pot + max(0, E - bets[raiser])
                lose_c = my_behind - (E - my_bet)
                n_w = n_alive - 1 if raiser_total <= my_total else n_alive
                pc = 0.45 if not callers_after else 0.7
                eq_c = eq_vs_range(h, max(0.02, r_range * pc))
                if callers_after:
                    eq_c *= 0.85 ** len(callers_after)
                v_shove = (1 - pc) * vicm(n_alive, my_behind + pot, total) + pc * (
                    eq_c * vicm(n_w, win_c, total) + (1 - eq_c) * vicm(n_alive, lose_c, total))
                if v_shove > vicm(n_alive, my_behind, total):
                    return self._allin(obs)
                if call_amt <= eff * 0.12:
                    return self._call(obs)
                return self._fold(obs)
            return self._raise(obs, raise_to * 3 + sum(bets) - bets[raiser] - my_bet)
        # resteal shove vs frequent openers
        if n_raises == 1 and not callers_after and eff_bb <= 32 and not raiser_allin and pct <= 0.3 \
                and r_range >= 0.2 and self.stats[raiser].hands >= 12:
            total = sum(stacks) + pot
            my_behind = stacks[me]
            E = min(my_total, raiser_total)
            win_c = my_behind + pot + max(0, E - bets[raiser])
            lose_c = my_behind - (E - my_bet)
            n_w = n_alive - 1 if raiser_total <= my_total else n_alive
            pc = 0.4
            eq_c = eq_vs_range(h, max(0.02, r_range * pc))
            v_shove = (1 - pc) * vicm(n_alive, my_behind + pot, total) + pc * (
                eq_c * vicm(n_w, win_c, total) + (1 - eq_c) * vicm(n_alive, lose_c, total))
            if v_shove > vicm(n_alive, my_behind, total) + 0.2:
                return self._allin(obs)
        # call: implied odds hands
        pair = (hole[0] >> 2) == (hole[1] >> 2)
        if pair and call_amt <= eff * 0.06 and eff_bb >= 35:
            return self._call(obs)
        if eq >= need + 0.05 and eq >= 0.47 and call_amt <= eff * 0.10 and eff_bb >= 30:
            return self._call(obs)
        if me == obs['bb_seat'] and eq >= need + 0.06 and call_amt <= 2.5 * bb and n_raises == 1:
            return self._call(obs)
        return self._fold(obs)

    def _shove_decision(self, obs, h, behind, pot, my_total, bb, limset=()):
        stacks = obs['stacks']
        bets = obs['bets']
        me = self.seat
        my_bet = bets[me]
        my_behind = stacks[me]
        total = sum(stacks) + pot
        n = len(obs['alive'])
        p_all_fold = 1.0
        ev = 0.0
        for s in behind:
            their_total = stacks[s] + bets[s]
            e = min(my_total, their_total)
            ebb = e / bb
            c = min(0.55, 1.4 / max(ebb, 1.0) + 0.05)
            # opponent looseness adjustment
            x = self.stats[s]
            if x.call_allin_opp >= 2:
                c = (c * 3 + x.call_allin) / (3 + x.call_allin_opp)
            vp = self._vpip(s)
            c *= 0.6 + 0.4 * (vp / 0.28)
            c = max(0.03, min(0.7, c))
            if s in limset:
                c = min(0.75, c * 1.4 + 0.08)
            eq = eq_vs_range(h, c)
            win_chips = my_behind + pot + (e - bets[s])
            lose_chips = my_behind - (e - my_bet)
            n_w = n - 1 if their_total <= e else n
            v = eq * vicm(n_w, win_chips, total) + (1 - eq) * vicm(n, lose_chips, total)
            ev += p_all_fold * c * v
            p_all_fold *= (1 - c)
        ev += p_all_fold * vicm(n, my_behind + pot, total)
        if ev > vicm(n, my_behind, total):
            return self._allin(obs)
        if obs['to_call'] == 0:
            return {'action': 'check'}
        return self._fold(obs)

    # ------------------------------------------------------------------ postflop
    def _equity(self, hole, board, opp_ranges, n_iter, filt=None):
        """filt: list per opponent of None or bluff prob (hand must beat board category)."""
        rng = self.rng.random
        if filt is None:
            filt = [None] * len(opp_ranges)
        bcat = 0
        if len(board) >= 5:
            bcat = ev(board) >> 20
        else:
            cnt = {}
            for c in board:
                cnt[c >> 2] = cnt.get(c >> 2, 0) + 1
            vs = sorted(cnt.values(), reverse=True)
            if vs and vs[0] >= 3:
                bcat = 3
            elif vs and vs[0] == 2:
                bcat = 2 if (len(vs) > 1 and vs[1] == 2) else 1
        dead = set(hole)
        dead.update(board)
        deck = [c for c in range(52) if c not in dead]
        nd = len(deck)
        nb = 5 - len(board)
        known = hole + board
        bk = 0x3333
        for c in board:
            bk += KEY[c]
        hk = bk + KEY[hole[0]] + KEY[hole[1]]
        lists = [rc_for(p) for p in opp_ranges]
        win = 0.0
        tot = 0
        my_fixed = None
        if nb == 0:
            my_fixed = ev(known)
        pc = time.perf_counter
        t_end = pc() + 0.00034
        for it in range(n_iter):
            if (it & 3) == 3 and pc() > t_end:
                break
            used = []
            ok = True
            for oi, L in enumerate(lists):
                fp = filt[oi]
                for _t in range(10):
                    if L is not None:
                        a, b = L[int(rng() * len(L))]
                    else:
                        a = deck[int(rng() * nd)]
                        b = deck[int(rng() * nd)]
                    if a == b or a in dead or b in dead or a in used or b in used:
                        continue
                    if fp is not None and _t < 9:
                        if (ev([a, b] + board) >> 20) <= bcat and rng() > fp:
                            continue
                    break
                else:
                    ok = False
                    break
                used.append(a)
                used.append(b)
            if not ok:
                continue
            run = []
            while len(run) < nb:
                c = deck[int(rng() * nd)]
                if c in used or c in run:
                    continue
                run.append(c)
            if my_fixed is None:
                mv = ev(known + run)
            else:
                mv = my_fixed
            best = 0
            ties = 0
            bc = board + run
            for i in range(0, len(used), 2):
                v = ev([used[i], used[i + 1]] + bc)
                if v > best:
                    best = v
                    ties = 1 if v == mv else 0
                elif v == best and v == mv:
                    ties += 1
            tot += 1
            if mv > best:
                win += 1.0
            elif mv == best:
                win += 1.0 / (1 + ties)
        if tot == 0:
            return 0.5
        return win / tot

    def _postflop(self, obs, hole, board):
        me = self.seat
        stacks = obs['stacks']
        bets = obs['bets']
        pot = obs['pot']
        to_call = obs['to_call']
        in_hand = obs['in_hand']
        others = [s for s in in_hand if s != me]
        n_opp = len(others)
        hist = obs['history']
        street = obs['street_index']
        # preflop ranges of opponents
        pf = [r for r in hist if r[0] == 0]
        pf_raisers = [r[1] for r in pf if r[2] == 'raise']
        last_pf_raiser = pf_raisers[-1] if pf_raisers else None
        ranges = []
        for s in others:
            nr = pf_raisers.count(s)
            if nr >= 2:
                p = 0.06
            elif nr == 1:
                p = max(0.08, min(0.5, self._pfr(s) * 1.1))
                if len(pf_raisers) >= 2 and pf_raisers[-1] == s:
                    p = max(0.05, min(0.2, self._pfr(s) * 0.4))
            else:
                if pf_raisers:
                    p = max(0.15, min(0.6, self._vpip(s) * 0.9))
                else:
                    p = max(0.3, min(0.9, self._vpip(s) * 1.3)) if s != obs['bb_seat'] else 0.95
            ranges.append(p)
        n_iter = 60 if n_opp == 1 else (40 if n_opp == 2 else 28)
        if street == 3:
            n_iter += 25
        # street action so far
        cur = [r for r in hist if r[0] == street]
        street_raises = [r for r in cur if r[2] in ('raise', 'bet')]
        filt = None
        if to_call > 0 and street_raises:
            bt = street_raises[-1][1]
            if bt != me and bt in others:
                xb = self.stats[bt]
                aggb = (xb.post_bets + 1) / (xb.post_bets + xb.post_calls + 3)
                bp = (0.30, 0.22, 0.14)[street - 1] * (0.5 + 1.5 * aggb)
                if len(street_raises) >= 2:
                    bp *= 0.5
                filt = [bp if s == bt else None for s in others]
        eq = self._equity(hole, board, ranges, n_iter, filt)
        my_stack = stacks[me]
        spr = my_stack / max(pot, 1)
        i_was_aggr = last_pf_raiser == me
        if to_call == 0:
            # check or bet
            fair = 1.0 / (n_opp + 1)
            vth = 0.62 if n_opp == 1 else fair + 0.28
            if street == 3:
                vth += 0.06
            if eq >= vth:
                frac = 0.65 if eq < 0.8 else 0.8
                if spr < 1.2:
                    if eq >= (0.75 if street < 3 else 0.82):
                        return self._allin(obs)
                    frac = 0.4
                elif street == 3 and eq < 0.82:
                    frac = 0.5
                return self._raise(obs, pot * frac)
            # c-bet / bluff
            if n_opp == 1:
                opp = others[0]
                fb = self._fold_to_bet(opp)
                bluff_p = 0.0
                if street == 1 and i_was_aggr:
                    bluff_p = 0.35 + 0.6 * (fb - 0.45)
                elif street >= 2 and eq >= 0.35 and i_was_aggr and street == 2:
                    bluff_p = 0.25 + 0.5 * (fb - 0.45)
                elif not street_raises and fb > 0.55:
                    bluff_p = 0.4 * (fb - 0.45) * 2
                if street == 1 and eq > 0.4:
                    bluff_p += 0.15
                if self.rng.random() < bluff_p:
                    return self._raise(obs, pot * 0.5)
            elif n_opp == 2 and street == 1 and i_was_aggr and eq >= 0.4:
                if self.rng.random() < 0.4:
                    return self._raise(obs, pot * 0.5)
            return {'action': 'check'}
        # facing a bet
        call_amt = min(to_call, my_stack)
        need = call_amt / (pot + call_amt)
        bet_frac = to_call / max(pot - to_call, 1)
        # bettor's range stronger than preflop range: discount equity
        disc = 0.02 + 0.05 * min(1.5, bet_frac) + 0.01 * (street - 1)
        if len(street_raises) >= 2:
            disc += 0.06
        # aggressive opponents: less discount
        bettor = street_raises[-1][1] if street_raises else None
        if bettor is not None and bettor != me:
            x = self.stats[bettor]
            agg = (x.post_bets + 1) / (x.post_bets + x.post_calls + 3)
            disc *= 0.6 + 0.8 * (1 - agg)
        eqa = eq - disc
        if call_amt >= 0.3 * my_stack:
            total = sum(stacks) + pot
            n_alive = len(obs['alive'])
            opp_max = max([stacks[s] + bets[s] for s in others] or [0]) - bets[me]
            R = min(my_stack, max(call_amt, opp_max))
            win_c = my_stack + pot + (R - call_amt)
            lose_c = my_stack - R
            v_fold = vicm(n_alive, my_stack, total)
            e2 = max(0.0, eqa)
            v_call = e2 * vicm(n_alive, win_c, total) + (1 - e2) * vicm(n_alive, lose_c, total)
            if v_call > v_fold:
                if eqa >= (0.85 if street == 3 else 0.6):
                    return self._allin(obs)
                return self._call(obs)
            return self._fold(obs)
        if eqa >= (0.80 if street == 3 else 0.70) and eq >= 0.75:
            if spr < 1.5 or call_amt >= 0.4 * my_stack:
                return self._allin(obs)
            return self._raise(obs, to_call * 2.5 + pot)
        if eqa >= need:
            if call_amt >= 0.6 * my_stack and eqa >= need + 0.05:
                return self._allin(obs)
            return self._call(obs)
        return self._fold(obs)
