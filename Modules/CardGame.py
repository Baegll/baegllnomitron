# Proposal 309. Physical evidence and Uno Reverse rulings are moderator actions.
import random
import shlex
import uuid
from copy import deepcopy

inPlay = ['Personal Deck', 'Play Area']
elevens = ['Eleven of ' + suit for suit in ['Hearts', 'Clubs', 'Spades', 'Diamonds', 'Coins']]
newCards = {
    'The Cursed Apple': {'Count': 2},
    'Pot of Greed': {'Count': None},
    # Inactive: a repeatable ability needs an in-play zone, but this card has no
    # Active, Passive, Summon, or other text permitting entry into either zone.
    'Staff of Nin': {'Count': 3, 'Weight': 0.1, 'Potency': 2, 'Repeatable': True},
    'Stoat': {'Count': 1, 'Keywords': ['Summon', 'Life', 'Attack', 'Cost'], 'Life': 3, 'Attack': 1, 'Cost': 1},
    'Uno Reverse': {'Count': None, 'Keywords': ['Active'], 'Power': 1},
    'Exploding Kitten': {'Count': 3},
    **{name: {'Count': 1} for name in elevens},
    'Shiny Rock': {'Count': 1},
    'Lucky Rock': {'Count': 0, 'Return As': 'Shiny Rock'},
    'Ordinary Rock': {'Count': 0, 'Return As': 'Shiny Rock', 'Keywords': ['Summon', 'Life'], 'Life': 5},
    'Random': {'Count': 2},
}
amendment304 = '''Amend rule 304 with the following changes:

Change 'All Statistics are defined in this rule and new statistics can only be created by amending this rule.' to 'If any new statistics are created, this rule amends itself to list those statistics for as long as they are defined elsewhere'
The limitation "They have at least one effect that they can be spent for" gains "or a passive effect based on the amount of the statistic"
The limitation "They have a negative effect if the amount of the Statistic drops below Zero" gains "or the amount must not be allowed to drop below zero"

"which are intangible numerical resources" becomes "which are numerical intrinsic resources"
The following clarification is added: "Statistics are a subset of intrinsic resources, but not every intrinsic resource is a statistic"'''


def identity(): return uuid.uuid4().hex


async def setup(bot):
    # Run after Arcana.setup has committed its initial Cards table.
    bot.add_Task(initialize)


async def initialize(bot):
    definitions = {name: {'Count': None, 'Weight': None, 'Effect': '', 'Potency': 1, 'Keywords': []} | data for name, data in newCards.items()}
    bot.update_nested_dict(('Cards', 'Definitions'), definitions)
    bot.update_nested_dict(('Card Game',), {'History': [], 'Effects': [], 'Curses': {}, 'Random Rolls': {}, 'Toads': {}, 'Steals': [], 'Drops': [], 'Fund Claims': {}, 'Started 309': False})


def blockedAction(bot, pid):
    return bot.has('Card Game', 'Random Rolls', pid)


def canGainCards(bot, owner):
    if not bot.has('Card Game'): return True
    game = getattr(bot, 'CardAction', None)
    data = game.data if game else bot.get('Card Game')
    turn = bot.get('Vars', 'Turn')
    if any(s['Target'] == owner for s in data['Steals']): return False
    return not (isinstance(owner, int) and data['Toads'].get(owner, -1) > turn)


def canDraw(bot, owner):
    game = getattr(bot, 'CardAction', None)
    data = game.data if game else bot.get('Card Game')
    return canGainCards(bot, owner) and not data['Curses'].get(owner if isinstance(owner, int) else str(owner))


def tradeableGainAllowed(bot, pid, name):
    if not bot.has('Card Game'): return True
    return not (bot.get('Card Game', 'Toads').get(pid, -1) > bot.get('Vars', 'Turn') and name in bot.get('Resources', 'Tradeable'))


async def on_card_created(bot, card):
    card.setdefault('ID', identity())
    definition = bot.get('Cards', 'Definitions').get(card['Name'], {})
    if 'Life' in definition: card.setdefault('Life', definition['Life'])
    if card['Name'] == 'Stoat' and random.random() < 0.01:
        stickers = bot.get('Cards').get('Stickers', {})
        outside = bot.Modules['Arcana'].getCards(bot)['Outside'] + [bot.get('Cards').get('Turn Card Details') or {}]
        applicable = [name for name, rule in stickers.items() if 'Stoat' in rule.get('Cards', []) and not (rule.get('Unique') and any(name in c.get('Stickers', []) for c in outside))]
        if applicable: card.setdefault('Stickers', []).append(random.choice(applicable))


async def on_card_received(bot, owner, card, cards):
    if card['Name'] != 'Exploding Kitten': return
    game = getattr(bot, 'CardAction', None)
    if game and isinstance(owner, int):
        game.gain(owner, 'HP', -10)
    elif isinstance(owner, int):
        hp = bot.get('Players', owner).get('Intrinsic', {}).get('HP', 100)
        # Multiple draws can be staged before any of their HP changes commit.
        for change in bot.Data_Changes:
            if change['path'] == ('Players', owner, 'Intrinsic', 'HP') and change['operation'] == 'set': hp = change['args'][0]
        bot.set(('Players', owner, 'Intrinsic', 'HP'), max(1, hp - 10))
    else:
        await bot.Modules['Discord_Module'].send(bot, 'actions', 'Exploding Kitten drawn by an entity without defined HP: a Judge must resolve its damage.')
    cards['Outside'][:] = [c for c in cards['Outside'] if c.get('ID') != card['ID']]
    await bot.Modules['Discord_Module'].send(bot, 'actions', f'Exploding Kitten automatically played for {owner}: 10 damage (player HP minimum 1), then returned to the MDoMA.')


class Game:
    def __init__(self, bot):
        self.bot = bot
        self.cards, self.players, self.data = bot.Modules['Arcana'].getCards(bot), bot.get('Players'), bot.get('Card Game')
        self.original = deepcopy((self.cards, self.players, self.data))
        self.turn, self.now = bot.get('Vars', 'Turn'), bot.get('Vars', 'Time')

    def save(self):
        beforeCards, beforePlayers, beforeData = self.original
        for field, value in self.cards.items():
            if value != beforeCards.get(field):
                if field == 'Outside': self.bot.Modules['Arcana'].saveOutside(self.bot, value)
                else: self.bot.set(('Cards', field), value)
        for pid, player in self.players.items():
            if player.get('Intrinsic') != beforePlayers[pid].get('Intrinsic'): self.bot.set(('Players', pid, 'Intrinsic'), player['Intrinsic'])
            if player.get('Pockets') != beforePlayers[pid].get('Pockets'): self.bot.set(('Players', pid, 'Pockets'), player['Pockets'])
        for field, value in self.data.items():
            if value != beforeData.get(field): self.bot.set(('Card Game', field), value)

    def definition(self, card): return self.cards['Definitions'][card['Name']]

    def owner(self, text):
        if text.startswith('team:'):
            owner = ['Teams', text[5:]]
            if not self.bot.has(*owner): raise ValueError('Unknown team.')
            return owner
        if text.startswith('player:'): text = text[7:]
        try: pid = int(text.strip('<@!>'))
        except ValueError: raise ValueError('Use a player ID/mention or team:name.')
        if pid not in self.bot.Modules['Arcana'].players(self.bot): raise ValueError('Unknown player.')
        return pid

    def card(self, cid):
        card = next((c for c in self.cards['Outside'] if c.get('ID') == cid), None)
        if card is None: raise ValueError('Unknown card ID; the global Turn Card cannot be moved or used.')
        return card

    def owned(self, pid, cid):
        card = self.card(cid)
        if pid not in self.bot.Modules['Arcana'].members(self.bot, card['Owner']): raise ValueError('That is not your card.')
        if any(s['Target'] == card['Owner'] for s in self.data['Steals']): raise ValueError('That hand is frozen by an Eleven request.')
        return card

    def stat(self, pid, name, default=0): return self.players[pid].setdefault('Intrinsic', {}).get(name, default)

    def gain(self, pid, name, amount):
        self.players[pid].setdefault('Intrinsic', {})[name] = max(1 if name == 'HP' else 0, self.stat(pid, name, 100 if name == 'HP' else 0) + amount)

    def pay(self, pid, name, amount):
        if self.stat(pid, name, 100 if name == 'HP' else 0) - amount < (1 if name == 'HP' else 0): raise ValueError(f'You cannot pay {amount} {name}.')
        self.gain(pid, name, -amount)

    def remove(self, card):
        self.cards['Outside'].remove(card)
        if 'Temporary' in self.definition(card).get('Keywords', []): self.cards.setdefault('Destroyed', []).append(card)
        # Return As affects the deck identity; no physical deck entry is needed:
        # Lucky/Ordinary Rock have Count 0 and Shiny Rock already has its definition.

    async def draws(self, owner, count):
        drawn = 0
        for _ in range(count):
            if await self.bot.Modules['Arcana'].draw(self.bot, self.cards, owner) is not None: drawn += 1
        return drawn

    def event(self, kind, owner, target, **kwargs):
        effect = {'ID': identity(), 'Kind': kind, 'Owner': owner, 'Target': target, 'Turn': self.turn, 'Status': 'Applied', **kwargs}
        self.data['Effects'].append(effect)
        return effect

    def move(self, pid, cid, zone, sacrifice=None):
        card = self.owned(pid, cid)
        definition = self.definition(card)
        if card['Owner'] != pid: raise ValueError('Only your own cards can enter your personal deck or play area.')
        if card['Zone'] == zone: raise ValueError('That card is already there.')
        if (zone == 'Personal Deck' or card['Zone'] == 'Personal Deck') and card.get('Deck Move Turn') == self.turn:
            raise ValueError('That card already moved into or out of a personal deck this turn.')
        if zone == 'Personal Deck':
            if not (set(definition.get('Keywords', [])) & {'Active', 'Passive'} or definition.get('Equip')): raise ValueError('This card does not permit equipping.')
            used = sum(self.definition(c).get('Potency', 1) for c in self.cards['Outside'] if c['Owner'] == pid and c['Zone'] == zone)
            if used + definition.get('Potency', 1) > self.stat(pid, 'DeckCapacity', 3): raise ValueError('Not enough personal deck capacity.')
        if zone == 'Play Area':
            if 'Summon' not in definition.get('Keywords', []) and not definition.get('Play Area'): raise ValueError('This card does not permit summoning.')
            if definition.get('Cost'):
                if sacrifice:
                    victim = self.owned(pid, sacrifice)
                    if victim is card or victim['Zone'] != 'Play Area' or 'Summon' not in self.definition(victim).get('Keywords', []) or victim.get('Life', 0) < definition['Cost']: raise ValueError('Pay the cost from an owned summon with enough Life in your play area.')
                    victim['Life'] -= definition['Cost']
                    if victim['Life'] == 0: self.remove(victim)
                else: self.pay(pid, 'HP', definition['Cost'])
            if 'Life' in definition: card.setdefault('Life', definition['Life'])
        if zone == 'Personal Deck' or card['Zone'] == 'Personal Deck': card['Deck Move Turn'] = self.turn
        card['Zone'] = zone

    def give(self, pid, cid, owner):
        card = self.owned(pid, cid)
        if card['Zone'] in inPlay: raise ValueError('Cards in play cannot be traded by default.')
        if not canGainCards(self.bot, owner): raise ValueError('The recipient cannot gain cards.')
        card.update({'Owner': owner, 'Zone': 'Private Hand'})

    async def use(self, pid, cid, args):
        card = self.owned(pid, cid)
        owner = card['Owner']
        name, definition = card['Name'], self.definition(card)
        if 'Active' in definition.get('Keywords', []) and card['Zone'] != 'Personal Deck': raise ValueError('Active cards can only be used from a personal deck.')
        if definition.get('Repeatable') or 'Passive' in definition.get('Keywords', []):
            if card['Zone'] not in inPlay: raise ValueError('This repeatable/passive card is inactive outside play. Staff of Nin has no rule permitting entry into play.')
        if name == 'Pot of Greed':
            self.remove(card)
            return f'Drew {await self.draws(owner, 2)} cards.'
        if name == 'Lucky Rock':
            if not isinstance(owner, int): raise ValueError('This entity has no defined Luck; a Judge must resolve the effect.')
            self.remove(card)
            self.gain(owner, 'Luck', 1)
            return 'Gained 1 Luck; Lucky Rock returned as Shiny Rock.'
        if name == 'The Cursed Apple':
            target = self.owner(args[0])
            if not isinstance(target, int) or target == owner: raise ValueError('Curse another player.')
            self.remove(card)
            event = self.event('Curse', owner, target)
            self.data['Curses'].setdefault(target, []).append(event['ID'])
            return f'Player {target} is cursed. Effect ID: {event["ID"]}.'
        if name == 'Random':
            target = self.owner(args[0])
            if not isinstance(target, int): raise ValueError('Random targets a player.')
            if target in self.data['Random Rolls']: raise ValueError('That player already owes a Random roll.')
            mana = next((r for r in self.bot.get('Resources', 'Intrinsic') if r.lower() == 'mana'), None)
            if mana is not None:
                if not isinstance(owner, int): raise ValueError('This entity has no defined mana; a Judge must resolve the cost.')
                self.pay(owner, mana, 1)
            self.remove(card)
            event = self.event('Random', owner, target)
            self.data['Random Rolls'][target] = event['ID']
            return f'{target} must use !card random before any other action, including voting. Effect ID: {event["ID"]}.'
        if name in elevens:
            hand = [c for c in self.cards['Outside'] if c['Owner'] == card['Owner'] and c['Name'] in elevens]
            if {c['Name'] for c in hand} != set(elevens): raise ValueError('You need all five Elevens.')
            if args[0] == 'draw':
                for c in hand: self.remove(c)
                return f'Drew {await self.draws(owner, 10)} cards.'
            if args[0] != 'steal': raise ValueError('Use draw or steal <player or team:name>.')
            target = self.owner(args[1])
            if target == card['Owner'] or any(s['Target'] == target for s in self.data['Steals']): raise ValueError('Choose a different, unfrozen entity.')
            for c in hand: self.remove(c)
            eligible = [c['ID'] for c in self.cards['Outside'] if c['Owner'] == target and c['Zone'] not in inPlay]
            event = self.event('Eleven', owner, target)
            if not eligible: return 'That entity has no eligible cards; no cards transfer and no hand freeze is needed.'
            self.data['Steals'].append({'ID': event['ID'], 'Owner': owner, 'Target': target, 'Eligible': eligible, 'Count': min(4, len(eligible)), 'Deadline': self.now + self.bot.day})
            return f'{target} must choose {min(4, len(eligible))} cards with !card respond {event["ID"]} <card ids> within 24 hours. Their cards are frozen until resolution.'
        if name == 'Shiny Rock':
            other = self.card(args[0])
            target = other['Owner']
            if target == card['Owner'] or not isinstance(target, int) or other['Zone'] not in ['Public Hand', 'Play Area']: raise ValueError('Choose a card in another player\'s visible hand or play area.')
            if not canGainCards(self.bot, owner) or not canGainCards(self.bot, target): raise ValueError('An entity cannot gain cards.')
            card.update({'Owner': target, 'Zone': 'Private Hand', 'Name': random.choice(['Lucky Rock', 'Ordinary Rock'])})
            other.update({'Owner': owner, 'Zone': 'Private Hand'})
            event = self.event('Shiny Rock', owner, target)
            return f'Trade completed; rock became {card["Name"]}. Effect ID: {event["ID"]}. Uno Reverse may be submitted this turn for moderator adjudication.'
        if name == 'Uno Reverse': raise ValueError('Use !card reverse <card id> <effect id>.')
        raise ValueError('This card has no implemented usable ability; a Judge must resolve any additional rule-defined effect.')

    def attack(self, pid, cid, targets):
        card = self.owned(pid, cid)
        power = self.definition(card).get('Attack', 0)
        if not power or card['Zone'] not in inPlay: raise ValueError('Attack requires an in-play card with Attack.')
        if card.get('Attack Turn') == self.turn: raise ValueError('That card already attacked this turn.')
        group = None
        for word in targets:
            target = self.owner(word) if word.startswith('player:') else self.card(word)
            owner = target if isinstance(target, int) else target['Owner']
            if group is not None and owner != group: raise ValueError('Overflow can only hit that entity and its summons.')
            group = owner
            if isinstance(target, int):
                protected = any(c['Owner'] == target and c['Zone'] == 'Play Area' and 'Life' in c for c in self.cards['Outside'])
                if protected and not self.definition(card).get('Ignore Summons'): raise ValueError('Attackable summons protect that player.')
                self.gain(target, 'HP', -power)
                power = 0
            else:
                if 'Life' not in target or target['Zone'] not in inPlay: raise ValueError('Target an in-play card with Life.')
                used = min(power, target['Life'])
                target['Life'] -= used
                power -= used
                if target['Life'] <= 0: self.remove(target)
            if not power: break
        if group is None: raise ValueError('Supply at least one attack target.')
        card['Attack Turn'] = self.turn
        event = self.event('Attack', card['Owner'], group)
        return f'Attack applied. Unassigned overflow: {power}. Effect ID: {event["ID"]}.'

    def highStanding(self, pid):
        history = {entry['Number']: entry['Voters'] for entry in self.data['History']}
        for propid, prop in self.bot.get('Queue-Proposals').items():
            if prop.get('State') == 'Voting' and prop.get('Proposal#') is not None:
                history[prop['Proposal#']] = [v['PID-Voter'] for v in self.bot.get('User-Proposal-Votes').values() if v['Proposal-ID'] == propid and v['Vote'] in ['Yay', 'Nay', 'Abstain']]
        last = sorted(history, reverse=True)[:5]
        return len(last) == 5 and all(pid in history[number] for number in last)

    async def fund(self, pid):
        month = self.now.strftime('%Y-%m')
        if not self.highStanding(pid): raise ValueError('High Standing requires a vote on each of the most recent five opened/completed proposals.')
        if any(c['Owner'] == pid for c in self.cards['Outside']): raise ValueError('Your hand, including cards in play, must be empty.')
        if self.data['Fund Claims'].get(pid) == month: raise ValueError('You already used the Communal Card Fund this month.')
        if not await self.draws(pid, 1): raise ValueError('You cannot draw a card.')
        self.data['Fund Claims'][pid] = month
        return 'Communal Card Fund draw claimed.'

    def respond(self, pid, rid, cids):
        request = next((s for s in self.data['Steals'] if s['ID'] == rid), None)
        if request is None or pid not in self.bot.Modules['Arcana'].members(self.bot, request['Target']): raise ValueError('No such request for your entity.')
        if self.now >= request['Deadline']: raise ValueError('The response deadline passed; timeout chooses randomly.')
        self.transfer(request, cids)

    def transfer(self, request, cids):
        if len(set(cids)) != request['Count'] or len(cids) != request['Count'] or not set(cids) <= set(request['Eligible']): raise ValueError('Choose exactly the requested number of distinct eligible card IDs.')
        if not canGainCards(self.bot, request['Owner']): raise ValueError('The recipient cannot gain cards; the request awaits adjudication.')
        selected = [self.card(cid) for cid in cids]
        if any(c['Owner'] != request['Target'] for c in selected): raise ValueError('An eligible card changed owner; a Judge must resolve the request.')
        for card in selected: card.update({'Owner': request['Owner'], 'Zone': 'Private Hand'})
        self.data['Steals'].remove(request)

    def toad(self, pid):
        self.data['Toads'][pid] = self.turn + 3
        dropped = {'ID': identity(), 'Owner': None, 'Turn': self.turn, 'Items': {}, 'Intrinsic': {}}
        resources = self.bot.get('Resources', 'Tradeable')
        for field in ['Pockets', 'Intrinsic']:
            for name, amount in list(self.players[pid].get(field, {}).items()):
                if name in resources:
                    keep = 1 if field == 'Intrinsic' and name == 'HP' else 0
                    dropped['Items' if field == 'Pockets' else field][name] = max(0, amount - keep)
                    self.players[pid][field][name] = keep
        self.data['Drops'].append(dropped)
        for card in self.cards['Outside']:
            if card['Owner'] == pid and card['Zone'] not in inPlay and self.definition(card).get('Tradeable', True): card.update({'Owner': None, 'Zone': 'Global', 'Dropped Turn': self.turn})

    def roll(self, pid):
        if pid not in self.data['Random Rolls']: raise ValueError('You do not owe a Random spell roll.')
        number = random.randint(1, 6)
        del self.data['Random Rolls'][pid]
        if number == 1: self.toad(pid)
        elif number == 2: self.players[pid].setdefault('Intrinsic', {})['Luck'] = 0
        elif number == 3:
            for card in list(self.cards['Outside']):
                if card['Owner'] == pid and card['Zone'] not in inPlay: self.remove(card)
        elif number == 4: self.gain(pid, 'HP', -10)
        elif number == 5: self.gain(pid, 'HP', 20)
        else: self.gain(pid, 'Luck', 2)
        return f'Random spell roll for {pid}: 1d6 = {number}.'

    def pickup(self, pid, key, args):
        card = next((c for c in self.cards['Outside'] if c.get('ID') == key), None)
        if card:
            if not canGainCards(self.bot, pid): raise ValueError('You cannot gain cards.')
            if card['Owner'] is not None or 'Dropped Turn' not in card: raise ValueError('That card is not an unclaimed drop.')
            card.update({'Owner': pid, 'Zone': 'Private Hand'})
            return
        drop = next((d for d in self.data['Drops'] if d['ID'] == key and d['Owner'] is None), None)
        if not drop: raise ValueError('Unknown unclaimed drop.')
        name, amount = args[0], int(args[1])
        if not tradeableGainAllowed(self.bot, pid, name): raise ValueError('A toad cannot gain tradeable resources.')
        field = 'Items' if name in drop['Items'] else 'Intrinsic'
        if amount <= 0 or drop[field].get(name, 0) < amount: raise ValueError('That amount is not available.')
        if field == 'Items':
            pockets = self.players[pid].setdefault('Pockets', {})
            if sum(pockets.values()) + amount > self.stat(pid, 'Pockets', 2): raise ValueError('Not enough pocket capacity.')
            pockets[name] = pockets.get(name, 0) + amount
        else: self.gain(pid, name, amount)
        drop[field][name] -= amount

    def reverse(self, pid, cid, eid):
        card = self.owned(pid, cid)
        if card['Name'] != 'Uno Reverse' or card['Zone'] != 'Personal Deck': raise ValueError('Reveal an equipped Uno Reverse.')
        event = next((e for e in self.data['Effects'] if e['ID'] == eid), None)
        if event is None or event['Turn'] != self.turn or pid not in self.bot.Modules['Arcana'].members(self.bot, event['Target']): raise ValueError('Reverse an effect targeting you this turn.')
        if event['Status'] != 'Applied': raise ValueError('That effect already has a reversal request or ruling.')
        self.remove(card)
        event.update({'Status': 'Reversal Pending', 'Reverse Card': card, 'Reverser': pid})
        return f'Uno Reverse revealed and destroyed. Moderator: apply swapped owner/target for effect {eid}, then !card-admin ruling {eid} resolved; or veto its use with !card-admin ruling {eid} veto.'


async def command(bot, payload, *args):
    try: words = shlex.split(payload['Content'])
    except ValueError:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, 'Unclosed quote; quote team names containing spaces.')
    root = words[0]
    name, args = (words[1], words[2:]) if len(words) > 1 else ('', [])
    public = ['equip', 'unequip', 'summon', 'recall', 'use', 'give', 'attack', 'fund', 'random', 'pickup', 'respond', 'reverse']
    admin = ['curse-result', 'ruling', 'start309', 'history']
    if root not in ['!card', '!card-admin'] or name not in (admin if root == '!card-admin' else public):
        extra = ['opening-spread'] if root == '!card-admin' else ['list', 'crystal-draw', 'opening-draw', 'tarot-top']
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, 'Card actions: ' + ', '.join((admin if root == '!card-admin' else public) + extra))
    pid = payload['Author PID']
    game = Game(bot)
    bot.CardAction = game
    try:
        if blockedAction(bot, pid) and name != 'random' and not bot.Modules['Discord_Module'].isModerator(bot, pid): raise ValueError('You must roll for Random before any other action.')
        text = 'Done.'
        if name in ['equip', 'unequip', 'summon', 'recall']:
            zone = {'equip': 'Personal Deck', 'unequip': 'Private Hand', 'summon': 'Play Area', 'recall': 'Public Hand'}[name]
            game.move(pid, args[0], zone, args[1] if len(args) > 1 else None)
        elif name == 'use': text = await game.use(pid, args[0], args[1:])
        elif name == 'give': game.give(pid, args[0], game.owner(args[1]))
        elif name == 'attack': text = game.attack(pid, args[0], args[1:])
        elif name == 'fund': text = await game.fund(pid)
        elif name == 'random': text = game.roll(pid)
        elif name == 'pickup': game.pickup(pid, args[0], args[1:])
        elif name == 'respond': game.respond(pid, args[0], args[1:])
        elif name == 'reverse': text = game.reverse(pid, args[0], args[1])
        elif name == 'curse-result':
            target, result = game.owner(args[0]), args[1]
            if not isinstance(target, int): raise ValueError('Choose a cursed player.')
            if not game.data['Curses'].get(target): raise ValueError('That player is not cursed.')
            attempts = game.data.setdefault('Curse Attempts', {})
            if result != 'deadlock' and attempts.get(target) == game.turn: raise ValueError('That player must wait until the following turn to retry the drawings.')
            if result not in ['deadlock', 'success', 'failure']: raise ValueError('Use deadlock, success <guesser>, or failure.')
            if result == 'success':
                guesser = game.owner(args[2])
                if not isinstance(guesser, int) or guesser == target: raise ValueError('A different player must correctly identify all four drawings.')
                await game.draws(guesser, 1)
            if result == 'failure': attempts[target] = game.turn
            else: del game.data['Curses'][target]
            text = 'Moderator recorded the Deadlock victory or the result of identifying the witch, Snow White, poisoned apple, and magic mirror.'
        elif name == 'ruling':
            event = next((e for e in game.data['Effects'] if e['ID'] == args[0] and e['Status'] == 'Reversal Pending'), None)
            if event is None or args[1] not in ['resolved', 'veto']: raise ValueError('Choose a pending reversal and resolved or veto.')
            if args[1] == 'veto':
                card = event['Reverse Card']
                used = sum(game.definition(c).get('Potency', 1) for c in game.cards['Outside'] if c['Owner'] == card['Owner'] and c['Zone'] == 'Personal Deck')
                if used + game.definition(card).get('Potency', 1) > game.stat(card['Owner'], 'DeckCapacity', 3): raise ValueError('Free deck capacity before vetoing so the Uno can be restored to its original zone.')
                game.cards['Outside'].append(card)
            else:
                event['Owner'], event['Target'] = event['Target'], event['Owner']
            event['Status'] = 'Reversed (moderator applied)' if args[1] == 'resolved' else 'Vetoed'
        elif name == 'start309':
            await start309(bot, game.owner(args[0]))
            return
        elif name == 'history':
            recordVote(bot, game.data['History'], int(args[0]), [int(word.strip('<@!>')) for word in args[1:]])
        game.save()
        await bot.Modules['Discord_Module'].return_resp(bot, payload, text)
    except (ValueError, IndexError) as error:
        await bot.Modules['Discord_Module'].return_resp(bot, payload, str(error) if str(error) and not isinstance(error, IndexError) else 'Missing arguments; use !card or !card-admin for options.')
    finally: del bot.CardAction


def recordVote(bot, history, number, voters):
    history[:] = [e for e in history if e['Number'] != number] + [{'Number': number, 'Voters': sorted(set(voters))}]
    history.sort(key=lambda e: e['Number'])
    history[:] = history[-5:]


def instantParts(text):
    import re
    parts = re.split(r'(?m)^---[ \t]*$', text.replace('\r\n', '\n'))
    return '\n\n'.join(p.strip() for p in parts[::2] if p.strip()), '\n\n'.join(p.strip() for p in parts[1::2] if p.strip())


async def start309(bot, author):
    if bot.get('Card Game', 'Started 309'): return
    number = bot.get('Vars', 'Next Proposal Number')
    bot.set(('Queue-Proposals', 'proposal-309-instant'), {
        'DOB': bot.get('Vars', 'Time'), 'PID': author, 'Body': amendment304,
        'State': 'On Deck', 'Queue': 'parallel', 'Link': '', 'Proposal#': number,
        'Vote Close Time': None, 'Vote Start Time': None,
        'Channel': bot.Modules['Voting'].votingChanGen(number), 'Endorse-MID': None, 'Rank': None,
    })
    bot.set(('Vars', 'Next Proposal Number'), number + 1)
    bot.set(('Card Game', 'Started 309'), True)
    await bot.Modules['Discord_Module'].send(bot, 'actions', f'Proposal 309 instant amendment placed on the parallel Deck as #{number}; it will use the normal editing and voting schedule.')


async def update(bot):
    if not bot.has('Card Game'): return
    game = Game(bot)
    bot.CardAction = game
    try:
        for request in list(game.data['Steals']):
            if game.now >= request['Deadline']:
                try: game.transfer(request, random.sample(request['Eligible'], request['Count']))
                except ValueError as error:
                    if request.get('Adjudication') != str(error):
                        request['Adjudication'] = str(error)
                        await bot.Modules['Discord_Module'].send(bot, 'actions', f'Eleven request {request["ID"]} needs moderator adjudication: {error}')
        game.save()
    finally: del bot.CardAction


async def onTurnEnd(bot):
    if not bot.has('Card Game'): return
    game = Game(bot)
    # Called after the turn counter increments, so all earlier drops are unclaimed.
    for drop in game.data['Drops']:
        if drop['Owner'] is None and drop['Turn'] < game.turn: drop['Owner'] = 'Nomitron'
    for card in game.cards['Outside']:
        if card['Owner'] is None and card.get('Dropped Turn', game.turn) < game.turn: card['Owner'] = 'Nomitron'
    game.save()
