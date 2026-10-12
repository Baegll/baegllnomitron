#
# Items And Teams Module For Discord Bot (Rules 304 and 305)
################################
import discord, re, math

resourceLists = ['Tradeable', 'External', 'Intrinsic', 'Sauces', 'Items', 'Fluids']
sauceSeed = ['Oyster', 'Meat', 'Ratatoile', 'Tomato', 'Garlic', 'Pesto', 'Alfredo']
spiceSeed = {
    'Cinnamon':      "Pet an animal that isn't yours and that you haven't petted as a part of a spice task previously",
    'Onion Powder':  "Make and drink a beverage not submitted by anyone as part of a spice task",
    'Garlic Powder': "Do an athletic trick not submitted by anyone as part of a spice task",
    'Paprica':       "Dress up as a person or character not submitted by anyone as part of a spice task",
    'Pepper':        "With another person do a weird handshake not submitted by anyone as part of a spice task",
    'Basil':         "Put on a short puppet (puppet may loosely defined) show",
    'All Spice':     "The person doing this spice must do the other 2 spices at the same time",
}

pocketsStat    = 'Pockets'
intrinsicStart = {'Luck': 1, pocketsStat: 2}    # what a player starts with; anything else starts at 0
teamSize       = 3
orderChan      = 'sauce-orders'
maxOrderLen    = 1500                           # keeps an order post to a single message
noOrder        = {'Text': None, 'Post Time': None, 'Recall Turn': None, 'MID': None}


async def setup(bot):
    add_command = bot.Modules['Commands'].add_command

    add_command(bot,
        name= 'resource-add',
        description= 'mod only -  add a resource to a category list: !resource-add <category> <name>',
        callback = resourceAdd,
        checks = ['isMod'])

    add_command(bot,
        name= 'resource-remove',
        description= 'mod only -  remove a resource from a category list: !resource-remove <category> <name>',
        callback = resourceRemove,
        checks = ['isMod'])

    add_command(bot,
        name= 'spice-add',
        description= 'mod only -  add a spice or change its description: !spice-add <name>: <description>',
        callback = spiceAdd,
        checks = ['isMod'])

    add_command(bot,
        name= 'spice-remove',
        description= 'mod only -  remove a spice: !spice-remove <name>',
        callback = spiceRemove,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-create',
        description= 'mod only -  create a team and its role: !team-create <name>',
        callback = teamCreate,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-remove',
        description= 'mod only -  remove a team: !team-remove <name>',
        callback = teamRemove,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-rename',
        description= 'mod only -  rename a team and its role: !team-rename <name> <new name>',
        callback = teamRename,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-channel',
        description= 'mod only -  set a team\'s channel: !team-channel <name> <#channel or none>',
        callback = teamChannel,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-add-player',
        description= 'mod only -  put a player on a team: !team-add-player <@player> <name>',
        callback = teamAddPlayer,
        checks = ['isMod'])

    add_command(bot,
        name= 'team-remove-player',
        description= 'mod only -  take a player off their team: !team-remove-player <@player>',
        callback = teamRemovePlayer,
        checks = ['isMod'])

    add_command(bot,
        name= 'set-amount',
        description= 'mod only -  set a player\'s intrinsic or pockets, or a team\'s bags or cups: !set-amount <@player or team> <amount> <resource>',
        callback = setAmount,
        checks = ['isMod'])

    add_command(bot,
        name= 'resources',
        description= 'list everything under Resources',
        callback = showResources,
        checks = ['isSpam', 'isPlayer'])

    add_command(bot,
        name= 'spices',
        description= 'list the spices and their tasks',
        callback = showSpices,
        checks = ['isSpam', 'isPlayer'])

    add_command(bot,
        name= 'team-data',
        description= "get a team's data, yours if no name is given",
        callback = teamData,
        checks = ['isSpam', 'isPlayer'])

    add_command(bot,
        name= 'give',
        description= 'give from your pockets to a player or team: !give <@player or team> <amount> <item>',
        callback = give,
        checks = ['isPlayer', 'isActions'])

    add_command(bot,
        name= 'pocket',
        description= "take from your team's bags or cups: !pocket <amount> <item>",
        callback = pocket,
        checks = ['isPlayer', 'isActions'])

    add_command(bot,
        name= 'order',
        description= f"post your team's Saucy Order to #{orderChan}: !order <text>",
        callback = order,
        checks = ['isPlayer', 'isActions'])

    add_command(bot,
        name= 'order-recall',
        description= "remove your team's order at the start of the next turn",
        callback = orderRecall,
        checks = ['isPlayer', 'isActions'])

    bot.update_nested_dict(('Resources',), structure = {
        'Tradeable': list(sauceSeed),
        'External':  [],
        'Intrinsic': list(intrinsicStart),
        'Sauces':    list(sauceSeed),
        'Items':     [],
        'Fluids':    list(sauceSeed),
    })
    if not bot.has('Spices'): bot.set(('Spices',), kwargs=dict(spiceSeed))
    bot.update_nested_dict(('Teams',), structure = {})

    bot.add_Task(bot.Modules['Discord_Module'].create_channel, dict(text_channel_name=orderChan, catagory_name='BUSINESS', permSetName='Locked') )



# Helpers
async def reply(bot, interaction, text, **kwargs):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, text, **kwargs)

def authorPID(interaction):
    return interaction['Author PID'] if type(interaction) is dict else interaction.user.id

def nameOf(bot, pid):
    return bot.get('Players', pid, 'Name') if bot.has('Players', pid) else str(pid)

def hasRef(bot, *nested_key):
    try: bot.get_Ref(*nested_key)
    except (KeyError, IndexError, TypeError): return False
    return True

def findName(names, words):
    """The entry of ``names`` that the words spell, ignoring case, or None."""
    text = ' '.join(words).strip().lower()
    for name in names:
        if str(name).lower() == text: return name
    return None

def pidFrom(bot, word):
    match = re.fullmatch(r'<@!?(\d+)>', word)
    if match and bot.has('Players', int(match.group(1))): return int(match.group(1))
    return None

def tidy(amount):
    amount = round(amount, 6)
    return int(amount) if amount == int(amount) else amount

def toNumber(word):
    try: amount = float(word)
    except ValueError: return None
    return tidy(amount) if math.isfinite(amount) else None

def amountsText(held):
    return ', '.join(f'{name}: {amount}' for name, amount in held.items()) or 'empty'

def findTarget(bot, words):
    """A player mention or a team name, as ('Players', pid) or ('Teams', name), or None."""
    if len(words) == 1 and pidFrom(bot, words[0]) is not None: return ('Players', pidFrom(bot, words[0]))
    team = findName(bot.keys('Teams'), words)
    return ('Teams', team) if team is not None else None

def targetName(bot, target):
    return nameOf(bot, target[1]) if target[0] == 'Players' else target[1]

def splitAmount(bot, words, names):
    """Split '<target> <amount> <name>' on the number that leaves a known target and a known name."""
    for i, word in enumerate(words):
        target, amount, name = findTarget(bot, words[:i]), toNumber(word), findName(names, words[i+1:])
        if target is not None and amount is not None and name is not None: return target, amount, name
    return None, None, None

def splitTeam(bot, words):
    """Split '<team name> <rest>' on the longest team name the words start with."""
    for i in range(len(words), 0, -1):
        team = findName(bot.keys('Teams'), words[:i])
        if team is not None: return team, list(words[i:])
    return None, list(words)

def teamOf(bot, pid):
    for team, data in bot.get('Teams').items():
        if pid in data['Members']: return team
    return None

def isItem(bot, name):
    return name in bot.get('Resources', 'Items')

def holdables(bot):
    """Everything Pockets, Bags and Cups can hold: the items, then the fluids (sauces are fluids)."""
    resources = bot.get('Resources')
    return resources['Items'] + resources['Fluids'] + resources['Sauces']

def holdPath(bot, target, name):
    """Where a player or team holds an item or fluid: Pockets, or Bags for items and Cups for fluids."""
    table, key = target
    if table == 'Players': return (table, key, 'Pockets')
    return (table, key, 'Bags' if isItem(bot, name) else 'Cups')

def held(bot, path):
    return bot.get(path) if bot.has(path) else {}

def changed(holding, name, amount):
    """A copy of a Pockets, Bags or Cups dict with one amount set; a resource at 0 is removed."""
    holding, amount = dict(holding), tidy(amount)
    if amount == 0: holding.pop(name, None)
    else:           holding[name] = amount
    return holding

def pocketLimit(bot, pid):
    return bot.get('Players', pid).get('Intrinsic', {}).get(pocketsStat, intrinsicStart[pocketsStat])

def amountProblem(bot, name, amount):
    if amount <= 0: return "The amount must be more than 0."
    if isItem(bot, name) and type(amount) is not int: return f"{name} is an item, so the amount must be a whole number."
    return None

def reservedRoles(bot):
    D, A = bot.Modules['Discord_Module'], bot.Modules['Activity']
    roles = [D.moderatorRole, D.PlayerRole, D.botRole, D.InactiveRole, D.JudgeRole, D.JudgeOptInRole, D.DefaultRole, '@everyone', A.OverdueRole, A.ModBlockRole]
    return [role.lower() for role in roles]

def orderPost(team, text):
    return f"**Saucy Order from {team}:**\n{text}"

async def setRole(bot, pid, roleName, hold):
    """Give or take a team's role, if the member and the role are still on the server."""
    if roleName is None or not hasRef(bot, 'Players', pid) or not hasRef(bot, 'Roles', roleName): return
    if hold: await bot.Modules['Discord_Module'].addRole(bot, pid, roleName)
    else:    await bot.Modules['Discord_Module'].removeRole(bot, pid, roleName)

async def deleteOrderPost(bot, team):
    mid = bot.get('Teams', team, 'Order')['MID']
    if mid is None or not hasRef(bot, 'Text Channels', orderChan): return
    try: await bot.Modules['Discord_Module'].chan_from_Name(bot, orderChan).get_partial_message(mid).delete()
    except discord.NotFound: pass
    except Exception as e: bot.log(f"Couldn't delete {team}'s order post from #{orderChan}, remove it by hand: {e!r}", mode='error')



# Resources and Spices
async def resourceAdd(bot, interaction, category = '', *name):
    category, name = findName(resourceLists, [category]), ' '.join(name).strip()
    if category is None or name == '':
        return await reply(bot, interaction, f"Use !resource-add <{' | '.join(resourceLists)}> <name>.")
    listed = bot.get('Resources', category)
    if findName(listed, [name]) is not None:
        return await reply(bot, interaction, f"{name} is already listed under {category}.")
    bot.set(('Resources', category), listed + [name])
    await reply(bot, interaction, f"Added {name} to {category}.")

async def resourceRemove(bot, interaction, category = '', *name):
    category = findName(resourceLists, [category])
    if category is None or len(name) == 0:
        return await reply(bot, interaction, f"Use !resource-remove <{' | '.join(resourceLists)}> <name>.")
    listed = bot.get('Resources', category)
    name = findName(listed, name)
    if name is None:
        return await reply(bot, interaction, f"That isn't listed under {category}.")
    bot.set(('Resources', category), [n for n in listed if n != name])
    await reply(bot, interaction, f"Removed {name} from {category}.")

async def spiceAdd(bot, interaction, *text):
    name, _, description = ' '.join(text).partition(':')
    name, description = name.strip(), description.strip()
    if name == '' or description == '':
        return await reply(bot, interaction, "Use !spice-add <name>: <description>.")
    old = findName(bot.keys('Spices'), [name])
    bot.set(('Spices', name if old is None else old), description)
    await reply(bot, interaction, f"Added the spice {name}." if old is None else f"Updated the spice {old}.")

async def spiceRemove(bot, interaction, *name):
    name = findName(bot.keys('Spices'), name)
    if name is None:
        return await reply(bot, interaction, "I couldn't find that spice.")
    bot.remove('Spices', name)
    await reply(bot, interaction, f"Removed the spice {name}.")

async def showResources(bot, interaction, *args):
    text = "Resources:\n"
    for category, listed in bot.get('Resources').items():
        text += f"{category} : {', '.join(listed) or 'None'}\n"
    await reply(bot, interaction, text)

async def showSpices(bot, interaction, *args):
    text = "Spices:\n"
    for name, description in bot.get('Spices').items():
        text += f"- {name} : {description}\n"
    await reply(bot, interaction, text)



# Teams
async def teamCreate(bot, interaction, *name):
    name = ' '.join(name).strip()
    if name == '' or len(name) > 100:
        return await reply(bot, interaction, "Use !team-create <name>, with a name of at most 100 characters.")
    if findName(bot.keys('Teams'), [name]) is not None:
        return await reply(bot, interaction, f"There is already a team called {name}.")
    if name.lower() in reservedRoles(bot):
        return await reply(bot, interaction, f"{name} is one of the game's roles, so a team can't use it as a name.")

    if not hasRef(bot, 'Roles', name): await bot.Modules['Discord_Module'].create_role(bot, name)
    bot.set(('Teams', name), {'Bags': {}, 'Cups': {}, 'Order': dict(noOrder), 'Members': [], 'Channel': None, 'Role': name})
    await reply(bot, interaction, f"Created the team {name}.")

async def teamRemove(bot, interaction, *name):
    team = findName(bot.keys('Teams'), name)
    if team is None:
        return await reply(bot, interaction, "I couldn't find that team.")
    data = bot.get('Teams', team)
    for pid in data['Members']: await setRole(bot, pid, data['Role'], False)
    await deleteOrderPost(bot, team)
    bot.remove('Teams', team)
    await reply(bot, interaction, f"Removed the team {team}. Its role and channel are still on the server.")

async def teamRename(bot, interaction, *args):
    team, new = splitTeam(bot, args)
    new = ' '.join(new).strip()
    if team is None or new == '' or len(new) > 100:
        return await reply(bot, interaction, "Use !team-rename <name> <new name>, with a new name of at most 100 characters.")
    if new == team or findName(bot.keys('Teams'), [new]) not in [None, team]:
        return await reply(bot, interaction, f"There is already a team called {new}.")
    if new.lower() in reservedRoles(bot):
        return await reply(bot, interaction, f"{new} is one of the game's roles, so a team can't use it as a name.")
    if hasRef(bot, 'Roles', new):
        return await reply(bot, interaction, f"There is already a role called {new}. Delete it or pick another name.")

    data = bot.get('Teams', team)
    old = data['Role']
    if hasRef(bot, 'Roles', old):
        role = bot.get_Ref('Roles', old)
        await role.edit(name=new)
        bot.set_ObjRef('Roles', new, role)
        bot.remove_ObjRef('Roles', old)
        if bot.has('Roles', old):
            bot.set(('Roles', new), bot.get('Roles', old))
            bot.remove('Roles', old)
        for pid in bot.Modules['Discord_Module'].usersWithRole(bot, old):
            bot.set(('Players', pid, 'Roles'), [new if r == old else r for r in bot.get('Players', pid, 'Roles')])
    if data['Order']['MID'] is not None and hasRef(bot, 'Text Channels', orderChan):
        try: await bot.Modules['Discord_Module'].chan_from_Name(bot, orderChan).get_partial_message(data['Order']['MID']).edit(content=orderPost(new, data['Order']['Text']))
        except Exception as e: bot.log(f"Couldn't put {new}'s name on its order post in #{orderChan}: {e!r}", mode='error')

    data['Role'] = new
    bot.remove('Teams', team)
    bot.set(('Teams', new), data)
    await reply(bot, interaction, f"Renamed the team {team} to {new}.")

async def teamChannel(bot, interaction, *args):
    team = findName(bot.keys('Teams'), args[:-1])
    if team is None:
        return await reply(bot, interaction, "Use !team-channel <name> <#channel or none>.")
    channel = args[-1]
    match = re.fullmatch(r'<#(\d+)>', channel)
    if match:
        found = bot.where(('Text Channels', '*'), lambda db: db['TID'] == int(match.group(1)))
        channel = found[0][1] if found else None
    elif channel.lower() == 'none':
        bot.set(('Teams', team, 'Channel'), None)
        return await reply(bot, interaction, f"{team} no longer has a channel.")
    else:
        channel = channel.lstrip('#')
    if channel is None or not bot.has('Text Channels', channel):
        return await reply(bot, interaction, "I couldn't find that channel.")
    bot.set(('Teams', team, 'Channel'), channel)
    await reply(bot, interaction, f"{team}'s channel is now #{channel}.")

async def teamAddPlayer(bot, interaction, player = '', *name):
    pid, team = pidFrom(bot, player), findName(bot.keys('Teams'), name)
    if pid is None or team is None:
        return await reply(bot, interaction, "Use !team-add-player <@player> <name>.")
    if not bot.Modules['Discord_Module'].isPlayer(bot, pid):
        return await reply(bot, interaction, f"{nameOf(bot, pid)} is not a player.")
    old = teamOf(bot, pid)
    if old == team:
        return await reply(bot, interaction, f"{nameOf(bot, pid)} is already on {team}.")

    text = f"{nameOf(bot, pid)} is now on {team}."
    if old is not None:
        await setRole(bot, pid, bot.get('Teams', old, 'Role'), False)
        bot.set(('Teams', old, 'Members'), [m for m in bot.get('Teams', old, 'Members') if m != pid])
        text = f"{nameOf(bot, pid)} moved from {old} to {team}."
    await setRole(bot, pid, bot.get('Teams', team, 'Role'), True)
    members = bot.get('Teams', team, 'Members') + [pid]
    bot.set(('Teams', team, 'Members'), members)
    if len(members) > teamSize: text += f" {team} now has {len(members)} members; teams are meant to have {teamSize}."
    await reply(bot, interaction, text)

async def teamRemovePlayer(bot, interaction, player = '', *args):
    pid = pidFrom(bot, player)
    team = teamOf(bot, pid) if pid is not None else None
    if team is None:
        return await reply(bot, interaction, "Use !team-remove-player <@player>. They must be on a team.")
    await setRole(bot, pid, bot.get('Teams', team, 'Role'), False)
    bot.set(('Teams', team, 'Members'), [m for m in bot.get('Teams', team, 'Members') if m != pid])
    await reply(bot, interaction, f"{nameOf(bot, pid)} is no longer on {team}.")

async def teamData(bot, interaction, *name):
    team = findName(bot.keys('Teams'), name) if name else teamOf(bot, authorPID(interaction))
    if team is None:
        text = "I couldn't find that team." if name else "You aren't on a team. Use !team-data <name>."
        return await reply(bot, interaction, f"{text}\nTeams : {', '.join(bot.keys('Teams')) or 'None'}", ephemeral=True)
    data = bot.get('Teams', team)
    text  = f"Team : {team}\n"
    text += f"Members : {', '.join(nameOf(bot, pid) for pid in data['Members']) or 'None'}\n"
    text += f"Channel : {data['Channel']}\n"
    text += f"Role : {data['Role']}\n"
    text += f"Bags : {amountsText(data['Bags'])}\n"
    text += f"Cups : {amountsText(data['Cups'])}\n"
    order = data['Order']
    if order['Text'] is None:
        text += "Order : None\n"
    else:
        text += f"Order : posted <t:{int(order['Post Time'].timestamp())}:f>"
        if order['Recall Turn'] is not None: text += f", being removed at the start of turn {order['Recall Turn']}"
        text += f"\n{order['Text']}\n"
    await reply(bot, interaction, text, ephemeral=True)



# Amounts
async def setAmount(bot, interaction, *args):
    resources = bot.get('Resources')
    target, amount, name = splitAmount(bot, args, resources['Intrinsic'] + holdables(bot))
    if target is None:
        return await reply(bot, interaction, "Use !set-amount <@player or team> <amount> <resource>. The resource must be listed under Intrinsic, Items, Fluids or Sauces.")
    table, key = target
    if table == 'Players' and not bot.Modules['Discord_Module'].isPlayer(bot, key):
        return await reply(bot, interaction, f"{nameOf(bot, key)} is not a player.")

    if table == 'Players' and name in resources['Intrinsic']:
        if type(amount) is not int:
            return await reply(bot, interaction, f"{name} is intrinsic, so the amount must be a whole number.")
        bot.set(('Players', key, 'Intrinsic', name), amount)
        text = f"{nameOf(bot, key)} now has {amount} {name}."
        if name == pocketsStat and sum(held(bot, ('Players', key, 'Pockets')).values()) > amount:
            text += " That is fewer than they are carrying; they keep it, but can't pocket anything more."
        return await reply(bot, interaction, text)

    if name not in holdables(bot):
        return await reply(bot, interaction, f"{name} is intrinsic, and teams don't hold intrinsic resources.")
    if amount < 0 or (isItem(bot, name) and type(amount) is not int):
        return await reply(bot, interaction, "The amount can't be less than 0." if amount < 0 else f"{name} is an item, so the amount must be a whole number.")
    path = holdPath(bot, target, name)
    holding = changed(held(bot, path), name, amount)
    if table == 'Players' and sum(holding.values()) > pocketLimit(bot, key):
        return await reply(bot, interaction, f"That doesn't fit: {nameOf(bot, key)} has {pocketLimit(bot, key)} {pocketsStat}. Raise their {pocketsStat} first.")
    bot.set(path, holding)
    await reply(bot, interaction, f"{targetName(bot, target)} now has {amount} {name} in their {path[-1].lower()}.")

async def give(bot, interaction, *args):
    pid = authorPID(interaction)
    target, amount, name = splitAmount(bot, args, holdables(bot))
    if target is None:
        return await reply(bot, interaction, "Use !give <@player or team> <amount> <item>.")
    if amountProblem(bot, name, amount):
        return await reply(bot, interaction, amountProblem(bot, name, amount))
    if target == ('Players', pid):
        return await reply(bot, interaction, "You can't give to yourself.")
    pockets = held(bot, ('Players', pid, 'Pockets'))
    if pockets.get(name, 0) < amount:
        return await reply(bot, interaction, f"You only have {pockets.get(name, 0)} {name} in your pockets.")

    table, key = target
    path = holdPath(bot, target, name)
    theirs = held(bot, path)
    theirs = changed(theirs, name, theirs.get(name, 0) + amount)
    if table == 'Players':
        if not bot.Modules['Discord_Module'].isPlayer(bot, key):
            return await reply(bot, interaction, f"{nameOf(bot, key)} is not a player.")
        if sum(theirs.values()) > pocketLimit(bot, key):
            return await reply(bot, interaction, f"{nameOf(bot, key)} doesn't have room in their pockets.")
    bot.set(('Players', pid, 'Pockets'), changed(pockets, name, pockets[name] - amount))
    bot.set(path, theirs)
    await reply(bot, interaction, f"{nameOf(bot, pid)} gave {amount} {name} to {targetName(bot, target)}.")

async def pocket(bot, interaction, amount = '', *name):
    pid = authorPID(interaction)
    amount, name = toNumber(amount), findName(holdables(bot), name)
    if amount is None or name is None:
        return await reply(bot, interaction, "Use !pocket <amount> <item>.")
    team = teamOf(bot, pid)
    if team is None:
        return await reply(bot, interaction, "You aren't on a team.")
    if amountProblem(bot, name, amount):
        return await reply(bot, interaction, amountProblem(bot, name, amount))
    path = holdPath(bot, ('Teams', team), name)
    stock = held(bot, path)
    if stock.get(name, 0) < amount:
        return await reply(bot, interaction, f"{team} only has {stock.get(name, 0)} {name} in its {path[-1].lower()}.")
    pockets = held(bot, ('Players', pid, 'Pockets'))
    pockets = changed(pockets, name, pockets.get(name, 0) + amount)
    if sum(pockets.values()) > pocketLimit(bot, pid):
        return await reply(bot, interaction, f"You don't have room in your pockets: you have {pocketLimit(bot, pid)} {pocketsStat}.")
    bot.set(path, changed(stock, name, stock[name] - amount))
    bot.set(('Players', pid, 'Pockets'), pockets)
    await reply(bot, interaction, f"{nameOf(bot, pid)} pocketed {amount} {name} from {team}.")



# Orders
async def order(bot, interaction, *text):
    team = teamOf(bot, authorPID(interaction))
    text = discord.utils.escape_mentions(' '.join(text).strip())    # the bot reposts this, so it mustn't ping
    if team is None:
        return await reply(bot, interaction, "You aren't on a team.")
    if text == '' or len(text) > maxOrderLen:
        return await reply(bot, interaction, f"Use !order <text>, with at most {maxOrderLen} characters.")
    if bot.get('Teams', team, 'Order')['Text'] is not None:
        return await reply(bot, interaction, f"{team} already has an order posted. Use !order-recall to remove it at the start of the next turn.")
    if not bot.has('Text Channels', orderChan):
        return await reply(bot, interaction, f"#{orderChan} doesn't exist yet, try again in a moment.")

    msgs = await bot.Modules['Discord_Module'].send(bot, orderChan, orderPost(team, text))
    bot.set(('Teams', team, 'Order'), {'Text': text, 'Post Time': bot.get('Vars', 'Time'), 'Recall Turn': None, 'MID': msgs[0]['MID']})
    await reply(bot, interaction, f"{team}'s order is posted in #{orderChan}.")

async def orderRecall(bot, interaction, *args):
    team = teamOf(bot, authorPID(interaction))
    if team is None:
        return await reply(bot, interaction, "You aren't on a team.")
    current = bot.get('Teams', team, 'Order')
    if current['Text'] is None:
        return await reply(bot, interaction, f"{team} has no order posted.")
    if current['Recall Turn'] is not None:
        return await reply(bot, interaction, f"{team}'s order is already being removed at the start of turn {current['Recall Turn']}.")
    turn = bot.get('Vars', 'Turn') + 1
    bot.set(('Teams', team, 'Order', 'Recall Turn'), turn)
    await reply(bot, interaction, f"{team}'s order will be removed at the start of turn {turn}.")



async def syncRoles(bot):
    reserved = reservedRoles(bot)
    for team, data in bot.get('Teams').items():
        role = data['Role']
        if role is None or role.lower() in reserved: continue
        if not hasRef(bot, 'Roles', role): await bot.Modules['Discord_Module'].create_role(bot, role)
        for pid in bot.keys('Players'):
            if bot.Modules['Discord_Module'].hasRole(bot, pid, role) != (pid in data['Members']):
                await setRole(bot, pid, role, pid in data['Members'])

async def reload_references(bot):
    # Queued, so it runs once Discord_Module's reload of the roles is committed
    bot.add_Task(syncRoles)

"""
Update Function Called Every 10 Seconds
"""
async def update(bot):
    listed = bot.get('Resources', 'Intrinsic')
    for pid, player in bot.get('Players').items():
        if not bot.Modules['Discord_Module'].isPlayer(bot, pid): continue
        intrinsic = {name: player.get('Intrinsic', {}).get(name, intrinsicStart.get(name, 0)) for name in listed}
        if player.get('Intrinsic') != intrinsic: bot.set(('Players', pid, 'Intrinsic'), intrinsic)
        if 'Pockets' not in player: bot.set(('Players', pid, 'Pockets'), {})

    # Recalled orders come down at the start of their turn
    turn = bot.get('Vars', 'Turn')
    for team, data in bot.get('Teams').items():
        if data['Order']['Recall Turn'] is not None and turn >= data['Order']['Recall Turn']:
            await deleteOrderPost(bot, team)
            bot.set(('Teams', team, 'Order'), dict(noOrder))
