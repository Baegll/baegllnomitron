# Rule 302 and Proposal 311. Arbitrary Arcana text is adjudicated by players/Judges.
import random
import re

majorArcana = [
    'The Fool', 'The Magician', 'The High Priestess', 'The Empress', 'The Emperor',
    'The Hierophant', 'The Lovers', 'The Chariot', 'Strength', 'The Hermit',
    'Wheel of Fortune', 'Justice', 'The Hanged Man', 'Death', 'Temperance',
    'The Devil', 'The Tower', 'The Star', 'The Moon', 'The Sun', 'Judgement', 'The World',
]
minorArcana = [f'{rank} of {suit}'
    for suit in ['Swords', 'Wands', 'Coins', 'Cups']
    for rank in ['Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
                 'Ten', 'Page', 'Knight', 'Queen', 'King', 'Ace']]
arcana = majorArcana + minorArcana
effects = {
    'The Chariot': 'This turn, the top three Tarot Proposals move onto the Deck instead of the top two.',
    'Wheel of Fortune': 'Every active player gains 1 Luck.',
    'The Hanged Man': 'No Tarot Proposals move onto the Deck this turn.',
    'Two of Wands': 'This turn, each player may have up to two Tarot Proposals in the Tarot Queue.',
}


async def setup(bot):
    definitions = {name: {'Count': 1 if name in majorArcana else None,
                         'Weight': 0 if name in majorArcana else None,
                         'Effect': effects.get(name, '')} for name in arcana}
    bot.update_nested_dict(('Cards',), {
        'Definitions': definitions, 'Outside': [], 'Turn Card': None,
        'Previous Turn Cards': [], 'Seen': [], 'Last Tarot Deck': None,
        'Opening Spread': None,
    })
    for name, callback, description, checks in [
        ('arcana', showArcana, 'show the Turn Card and Arcana Effects', ['isPlayer', 'isSpam']),
        ('hand', showHand, 'privately show your cards', ['isPlayer']),
        ('cards', showCards, 'show global/public cards and hands visible to you', ['isPlayer', 'isSpam']),
        ('crystal-draw', crystalDraw, 'spend 2 Crystals to draw, once per turn', ['isPlayer', 'isActions']),
        ('tarot-top', tarotTop, 'spend 2 Crystals: !tarot-top <proposal id>', ['isPlayer', 'isActions']),
        ('tarot-remove', tarotRemove, 'remove your queued Tarot: !tarot-remove <proposal id>', ['isPlayer', 'isActions']),
        ('opening-spread', openingSpread, 'mod only - !opening-spread <voter IDs> : <passed author IDs>', ['isMod']),
        ('opening-draw', openingDraw, 'claim your Opening Spread draw this turn', ['isPlayer', 'isActions']),
    ]:
        bot.Modules['Commands'].add_command(bot, name=name, callback=callback,
                                           description=description, checks=checks)


def players(bot, active=False):
    discord = bot.Modules['Discord_Module']
    return [pid for pid in bot.keys('Players') if discord.isPlayer(bot, pid)
            and (not active or discord.isActive(bot, pid))]


def canDraw(bot, pid):
    if isinstance(pid, (list, tuple)):
        return bot.has(*pid) and bot.get(*pid).get('Can Draw Cards', True)
    return bot.get('Players', pid).get('Can Draw Cards', True)


def members(bot, owner):
    if isinstance(owner, (list, tuple)) and len(owner) == 2 and owner[0] == 'Teams':
        return bot.get(*owner).get('Members', []) if bot.has(*owner) else []
    return [owner] if owner in players(bot) else []


def visible(bot, card, pid):
    return card['Zone'] != 'Private Hand' or pid in members(bot, card['Owner'])


def crystals(bot, pid):
    return bot.get('Players', pid).get('Intrinsic', {}).get('Crystals', 0)


def hasEffect(bot, name):
    return effectApplies(bot.get('Cards'), name)


def effectApplies(cards, name):
    sentences = re.split(r'(?<=[.!?])\s+', cards['Definitions'][name]['Effect'].strip())
    return cards['Turn Card'] == name and effects[name] in sentences


def weight(cards, name, turn=False):
    definition = cards['Definitions'][name]
    count = sum(card['Name'] == name for card in cards['Outside'])
    count += cards['Turn Card'] == name
    if definition['Count'] is not None and count >= definition['Count']: return 0
    if turn:
        if name in cards['Previous Turn Cards']: return 0
        if name in majorArcana: return 2 if definition['Effect'] else 6
    if definition['Weight'] is not None: return definition['Weight']
    return 1 if definition['Count'] is not None else 2 ** -count


def choose(cards, turn=False):
    names = list(cards['Definitions'])
    weights = [weight(cards, name, turn) for name in names]
    return random.choices(names, weights=weights)[0] if any(weights) else None


async def newCard(bot, name, owner, zone):
    card = {'Name': name, 'Owner': owner, 'Zone': zone}
    # Other rules/modules supply edition/sticker lotteries and restrictions.
    for module in bot.Modules.values():
        if hasattr(module, 'on_card_created'): await module.on_card_created(bot, card)
    return card


async def draw(bot, cards, pid, name=None, card=None):
    if not canDraw(bot, pid): return None
    name = choose(cards) if name is None else name
    if name is None: return None
    card = await newCard(bot, name, pid, 'Private Hand') if card is None else dict(card)
    card.update({'Owner': pid, 'Zone': 'Private Hand'})
    cards['Outside'].append(card)
    for member in members(bot, pid):
        await bot.Modules['Discord_Module'].send(bot, member, f'You drew {name}.')
    # Turn Card selection never calls this hook.
    for module in bot.Modules.values():
        if hasattr(module, 'on_card_draw'): await module.on_card_draw(bot, pid, dict(card))
    return name


async def onTurnStart(bot):
    cards = bot.get('Cards')
    if cards['Turn Card'] is not None: return
    cards['Turn Card'] = choose(cards, turn=True)
    name = cards['Turn Card']
    cards['Turn Card Details'] = await newCard(bot, name, None, 'Global') if name else None
    if name in arcana and name not in cards['Seen']: cards['Seen'].append(name)
    for field in ['Turn Card', 'Turn Card Details', 'Seen']: bot.set(('Cards', field), cards[field])
    if name == 'Wheel of Fortune' and effectApplies(cards, name):
        for pid in players(bot, active=True):
            luck = bot.get('Players', pid).get('Intrinsic', {}).get('Luck', 1)
            bot.set(('Players', pid, 'Intrinsic', 'Luck'), luck + 1)
    text = cards['Definitions'][name]['Effect'] if name in arcana else ''
    known = effects.get(name, '')
    remainder = text.replace(known, '', 1).strip() if known else text.strip()
    notice = '\nManual adjudication required for unrecognized effect text; the bot has not applied it.' if remainder else ''
    await bot.Modules['Discord_Module'].send(bot, 'actions', f'Turn Card: {name or "none"}\n{text}{notice}')


async def onTurnEnd(bot):
    cards = bot.get('Cards')
    name = cards['Turn Card']
    cards['Previous Turn Cards'] = [name] if name else []
    if name and name not in arcana:
        card = cards.get('Turn Card Details') or {'Name': name, 'Owner': None, 'Zone': 'Global'}
        eligible = [pid for pid in players(bot, active=True) if canDraw(bot, pid)]
        if not eligible:
            cards['Outside'].append(card)
            await bot.Modules['Discord_Module'].send(bot, 'actions', f'{name} remains global: no active player can draw it. A Judge must resolve its handoff.')
        else: await draw(bot, cards, random.choice(eligible), name, card=card)
    cards['Turn Card'] = None
    cards['Turn Card Details'] = None
    for field in ['Turn Card', 'Turn Card Details', 'Previous Turn Cards', 'Outside']: bot.set(('Cards', field), cards[field])


def wordChanges(old, new):
    # Word-level edit distance: replacing one word costs one change.
    old, new = old.split(), new.split()
    row = list(range(len(new) + 1))
    for i, word in enumerate(old, 1):
        nextrow = [i]
        for j, other in enumerate(new, 1):
            nextrow.append(min(row[j] + 1, nextrow[-1] + 1, row[j-1] + (word != other)))
        row = nextrow
    return row[-1]


def tarotText(bot, text):
    prefix = 'Amend Rule 302 by setting the following Arcana Effect:'
    if text.startswith(prefix): text = text[len(prefix):].strip()
    name, separator, effect = text.partition(':')
    name, effect = name.strip(), effect.strip()
    if not separator or name not in arcana:
        raise ValueError('Use <Arcana name>: <new Arcana Effect>. This only changes that effect in Rule 302.')
    cards = bot.get('Cards')
    validateEffect(cards, name, effect)
    return name, effect


def validateEffect(cards, name, effect):
    old = cards['Definitions'][name]['Effect']
    if not old and name not in cards['Seen']:
        raise ValueError('That Arcana has not been a Turn Card yet.')
    if old and wordChanges(old, effect) > 2:
        raise ValueError('A Tarot Proposal may change at most 2 words of the current Arcana Effect.')


async def syncEffects(bot, text):
    # A changed official list supersedes the cache. An unchanged source must not
    # undo passed proposals while the external rules repository awaits updating.
    match = re.search(r'(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*)?List of Arcana Effects(?:\*\*)?[ \t]*$', text)
    if not match: return
    section = re.split(r'(?m)^#{1,6}\s', text[match.end():], maxsplit=1)[0].strip()
    cards = bot.get('Cards')
    if cards.get('Rule Effects Source') == section: return
    names = '|'.join(re.escape(name) for name in sorted(arcana, key=len, reverse=True))
    entries = list(re.finditer(r'(?m)^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?(' + names + r')(?:\*\*)?[ \t]*:(?:\*\*)?[ \t]*', section))
    if section and (not entries or section[:entries[0].start()].strip()):
        return await bot.Modules['Discord_Module'].send(bot, 'actions', 'Could not parse the official Arcana Effect list. A moderator must reconcile Rule 302 before relying on cached effects.')
    official = {name: '' for name in arcana}
    for i, entry in enumerate(entries):
        end = entries[i+1].start() if i+1 < len(entries) else len(section)
        official[entry[1]] = section[entry.end():end].strip()
    for name, effect in official.items(): bot.set(('Cards', 'Definitions', name, 'Effect'), effect)
    bot.set(('Cards', 'Rule Effects Source'), section)


async def showArcana(bot, payload, *args):
    cards = bot.get('Cards')
    text = f'Turn Card: {cards["Turn Card"] or "none"}\n'
    text += '\n'.join(f'{name}: {cards["Definitions"][name]["Effect"] or "(empty)"}' for name in arcana)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)


async def showHand(bot, payload, *args):
    pid = payload['Author PID']
    words = payload['Content'].split(maxsplit=1)
    owner = ['Teams', words[1].strip()] if len(words) > 1 else pid
    if pid not in members(bot, owner):
        return await bot.Modules['Discord_Module'].send(bot, pid, 'You are not a member of that entity.')
    hand = [c['Name'] for c in bot.get('Cards', 'Outside') if c['Owner'] == owner and c['Zone'].endswith('Hand') and visible(bot, c, pid)]
    await bot.Modules['Discord_Module'].send(bot, pid, 'Your hand:\n' + ('\n'.join(hand) or '(empty)'))


async def showCards(bot, payload, *args):
    cards = bot.get('Cards')
    visibleCards = [str(card) for card in cards['Outside'] if visible(bot, card, payload['Author PID'])]
    if cards['Turn Card']: visibleCards.append(str(cards.get('Turn Card Details') or {'Name': cards['Turn Card'], 'Zone': 'Global'}))
    # Always DM: the result can include the requester's private cards.
    await bot.Modules['Discord_Module'].send(bot, payload['Author PID'], '\n'.join(visibleCards) or '(no visible cards)')


async def crystalDraw(bot, payload, *args):
    pid, turn = payload['Author PID'], bot.get('Vars', 'Turn')
    cards = bot.get('Cards')
    if bot.get('Players', pid).get('Crystal Draw Turn') == turn:
        text = 'You already used your Crystal draw this turn.'
    elif crystals(bot, pid) < 2: text = 'You need 2 Crystals.'
    elif await draw(bot, cards, pid) is None: text = 'You cannot draw a card.'
    else:
        bot.set(('Cards', 'Outside'), cards['Outside'])
        bot.set(('Players', pid, 'Intrinsic', 'Crystals'), crystals(bot, pid) - 2)
        bot.set(('Players', pid, 'Crystal Draw Turn'), turn)
        text = 'Spent 2 Crystals to draw a card.'
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)


def ownTarot(bot, payload):
    words = payload['Content'].split(maxsplit=1)
    propid = words[1].strip() if len(words) > 1 else ''
    proposal = bot.get('Queue-Proposals', propid) if bot.has('Queue-Proposals', propid) else {}
    if proposal.get('PID') != payload['Author PID'] or proposal.get('Queue') != 'tarot' or proposal.get('State') != 'Queue':
        raise ValueError('Give the ID of one of your queued Tarot Proposals (shown in #tarot-queue).')
    return propid


async def tarotTop(bot, payload, *args):
    try:
        propid = ownTarot(bot, payload)
        pid = payload['Author PID']
        if crystals(bot, pid) < 2: raise ValueError('You need 2 Crystals.')
        priority = max([p.get('Tarot Priority', 0) for p in bot.get('Queue-Proposals').values()] + [0]) + 1
        bot.set(('Queue-Proposals', propid, 'Tarot Priority'), priority)
        bot.set(('Players', pid, 'Intrinsic', 'Crystals'), crystals(bot, pid) - 2)
        text = 'Spent 2 Crystals to move your Tarot Proposal to the top.'
    except ValueError as error: text = str(error)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)


async def tarotRemove(bot, payload, *args):
    try:
        bot.remove('Queue-Proposals', ownTarot(bot, payload))
        text = 'Removed your Tarot Proposal.'
    except ValueError as error: text = str(error)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)


async def openingSpread(bot, payload, *args):
    cards = bot.get('Cards')
    if cards['Opening Spread'] is not None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, 'The Opening Spread has already happened.')
    words = payload['Content'].split(maxsplit=1)
    voters, separator, authors = words[1].partition(':') if len(words) > 1 else ('', '', '')
    eligible, passed = set(map(int, re.findall(r'\d+', voters))), set(map(int, re.findall(r'\d+', authors)))
    pids = players(bot)
    if not separator or not (eligible | passed) <= set(pids):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, 'Use !opening-spread <voter IDs> : <passed author IDs>; all IDs must be players.')
    if any(not canDraw(bot, pid) for pid in passed):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, 'A listed author cannot draw; resolve their restriction before applying the Opening Spread.')
    for pid in pids: bot.set(('Players', pid, 'Intrinsic', 'Crystals'), crystals(bot, pid) + 2)
    for pid in sorted(passed): await draw(bot, cards, pid)
    cards['Opening Spread'] = {'Turn': bot.get('Vars', 'Turn'), 'Eligible': sorted(eligible), 'Claimed': []}
    bot.set(('Cards', 'Outside'), cards['Outside'])
    bot.set(('Cards', 'Opening Spread'), cards['Opening Spread'])
    await bot.Modules['Discord_Module'].return_resp(bot, payload, 'Opening Spread applied once. Eligible voters may use !opening-draw before this turn ends.')


async def openingDraw(bot, payload, *args):
    cards, pid = bot.get('Cards'), payload['Author PID']
    opening = cards['Opening Spread']
    if not opening or opening['Turn'] != bot.get('Vars', 'Turn') or pid not in opening['Eligible'] or pid in opening['Claimed']:
        text = 'You have no Opening Spread draw available this turn.'
    elif await draw(bot, cards, pid) is None: text = 'You cannot draw a card.'
    else:
        opening['Claimed'].append(pid)
        bot.set(('Cards', 'Outside'), cards['Outside'])
        bot.set(('Cards', 'Opening Spread'), opening)
        text = 'Opening Spread draw claimed.'
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)
