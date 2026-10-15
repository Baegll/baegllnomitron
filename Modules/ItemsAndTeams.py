#
# Items And Teams Module For Discord Bot (Rules 304 and 305)
################################
import math

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
        description= 'mod only -  rename a team and its role: !team-rename <name> : <new name>',
        callback = teamRename,
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

    bot.update_nested_dict(('Resources',), structure = {k:[] for k in resourceLists} | {
        'Tradeable': list(sauceSeed),
        'Intrinsic': list(intrinsicStart),
        'Sauces':    list(sauceSeed),
        'Fluids':    list(sauceSeed),
    })
    if not bot.has('Spices'): bot.set(('Spices',), kwargs=dict(spiceSeed))
    bot.update_nested_dict(('Teams',), structure = {})

def toNumber(value):
    """A word or a sum as an amount: an int when whole, rounded so fluid sums don't drift. None if it isn't a number."""
    try: amount = round(float(value), 6)
    except (ValueError, OverflowError): return None
    if not math.isfinite(amount): return None
    return int(amount) if amount == int(amount) else amount

def pidFrom(bot, word):
    """The id of the server member a mention names, or None."""
    member = bot.Modules['Discord_Module'].player_from_mention(bot, word) if word else None
    return member.id if member is not None else None

def splitAmount(bot, words):
    """Parse '<@player or team> <amount> <resource>' into ('Players', pid) or ('Teams', name), the amount and the resource.

    A team is named by its name, with or without an @, or by mentioning its role. Team names can have spaces,
    so the amount and the resource are read from the end. Returns Nones if nothing fits.
    """
    if len(words) < 3 or toNumber(words[-2]) is None: return None, None, None
    who, amount, name = ' '.join(words[:-2]).strip(), toNumber(words[-2]), words[-1]
    if who == '': return None, None, None
    for team in [who, who[1:]] if who[0] == '@' else [who]:     # a role that can't be mentioned arrives as plain text
        if team in bot.keys('Teams'): return ('Teams', team), amount, name
    pid = pidFrom(bot, who)
    if pid is not None: return ('Players', pid), amount, name

    roleName = bot.Modules['Discord_Module'].role_from_mention(bot, who)
    if roleName is not None and roleName in bot.get('Teams'): return ('Teams', roleName), amount, name
    return None, None, None

def teamOf(bot, pid):
    for team, data in bot.get('Teams').items():
        if pid in data['Members']: return team
    return None

def pocketRoom(bot, pid):
    """How much more a player's pockets can take: their Pockets value less everything they carry."""
    player = bot.get('Players', pid)
    limit = player.get('Intrinsic', {}).get(pocketsStat, 0)
    return round(limit - sum(player.get('Pockets', {}).values()), 6)

async def deleteOrder(bot, team):
    """Take a team's order post down. A post that can't be deleted is reported, for a mod to remove."""
    if not bot.has('Teams', team): return    # removed or renamed since the recall was scheduled
    mid = bot.get('Teams', team, 'Order', 'MID')
    if mid is None: return
    bot.set(('Teams', team, 'Order'), dict(noOrder))
    await bot.Modules['Discord_Module'].chan_from_Name(bot, orderChan).get_partial_message(mid).delete()

def scheduleRecall(bot, team, turn):
    bot.schedule(
            name = 'Remove Order for ' + team,
            method_name = 'deleteOrder',
            module_name = 'ItemsAndTeams',
            kwargs = {'team': team},
            Key = ('Vars','Turn'), Mode='>=', Trigger_Value= turn, sequential_only=False
        )

#ok enough
async def syncRoles(bot):
    """Make the Discord roles match the teams: create a missing team role, give it to the members, take it from anyone else."""
    for team, data in bot.get('Teams').items():
        role = data['Role']
        if role not in bot.get_Ref('Roles'): await bot.Modules['Discord_Module'].create_role(bot, role)
        for pid in bot.get_Ref('Players'):      # the members still on the server
            holds = bot.Modules['Discord_Module'].hasRole(bot, pid, role)
            if pid in data['Members'] and not holds: await bot.Modules['Discord_Module'].addRole(bot, pid, role)
            if pid not in data['Members'] and holds: await bot.Modules['Discord_Module'].removeRole(bot, pid, role)



# Resources and Spices
async def resourceAdd(bot, payload, *args):
    words = payload['Content'].split(' ')
    category, name = words[1:-1], words[-1]
    if len(category) == 0 or name == '' or any(c not in resourceLists for c in category):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Use !resource-add <{' | '.join(resourceLists)}> <name>, with a one-word name.")
    for c in category:
        if name not in bot.get('Resources', c): bot.stage(('Resources', c), 'append', name)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Added {name} to {', '.join(category)}.")

async def resourceRemove(bot, payload, category = '', *name):
    words = payload['Content'].split(' ')
    category, name  = words[1:-1], words[-1]
    if len(category) == 0 or name == '' or any(c not in resourceLists for c in category):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Use !resource-remove <{' | '.join(resourceLists)}> <name>, with a one-word name.")
    category = [c for c in category if name in bot.get('Resources', c)]
    if len(category) == 0:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{name} isn't listed there.")
    for c in category: bot.stage(('Resources', c), '.remove', name)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Removed {name} from {', '.join(category)}.")

async def spiceAdd(bot, payload, *args):
    words = payload['Content'].split(' ',1)
    name, _, description = words[1].partition(':') if len(words) > 1 else ('', '', '')
    name, description = name.strip(), description.strip()
    if name == '' or description == '':
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !spice-add <name>: <description>.")
    bot.set(('Spices', name), description)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Added the spice {name}.")

async def spiceRemove(bot, payload, *args):
    words = payload['Content'].split(' ', 1)
    name = words[1].strip() if len(words) > 1 else ''
    if name == '':
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !spice-remove <name>.")
    bot.remove('Spices', name)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Removed the spice {name}.")

async def showResources(bot, payload, *args):
    text = "Resources:\n"
    for category, listed in bot.get('Resources').items():
        text += f"{category} : {', '.join(listed) or 'None'}\n"
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)

async def showSpices(bot, payload, *args):
    text = "Spices:\n"
    for name, description in bot.get('Spices').items():
        text += f"- {name} : {description}\n"
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)



# Teams
async def teamCreate(bot, payload, *args):
    words = payload['Content'].split(' ', 1)
    name = words[1].strip() if len(words) > 1 else ''
    if name == '' or len(name) > 100:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !team-create <name>, with a name of at most 100 characters.")
    if name in bot.keys('Teams'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is already a team called {name}.")
    if name in bot.get_Ref('Roles'):    # the role sync would take that role from everyone not on the team
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is already a role called {name}. Delete it or pick another name.")

    bot.set(('Teams', name), {'Bags': {}, 'Cups': {}, 'Order': dict(noOrder), 'Members': [], 'Channel': None, 'Role': name})
    bot.add_Task(syncRoles)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Created the team {name}.")

async def teamRemove(bot, payload, *args):
    words = payload['Content'].split(' ', 1)
    name = words[1].strip() if len(words) > 1 else ''
    if name == '':
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !team-remove <name>.")
    if name not in bot.keys('Teams'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is no team called {name}.")

    await deleteOrder(bot, name)
    bot.remove('Teams', name)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Removed the team {name}. Its role and channel are still on the server.")

async def teamRename(bot, payload, *args):
    words = payload['Content'].split(' ', 1)
    oldteam, _, newteam = words[1].partition(':') if len(words) > 1 else ('', '', '')
    oldteam, newteam = oldteam.strip(), newteam.strip()

    if newteam == '' or len(newteam) > 100:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !team-rename <name> : <new name>, with a new name of at most 100 characters.")
    if oldteam not in bot.keys('Teams'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is no team called {oldteam}.")
    if newteam in bot.keys('Teams'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is already a team called {newteam}.")
    if newteam in bot.get_Ref('Roles'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is already a role called {newteam}. Delete it or pick another name.")

    data = bot.get('Teams', oldteam)
    old = data['Role']
    if old in bot.get_Ref('Roles'):
        role = bot.get_Ref('Roles', old)
        await role.edit(name=newteam)
        # Keep the role data in step until the next reload, or a role sync makes a second role
        bot.set_ObjRef('Roles', newteam, role)
        bot.remove_ObjRef('Roles', old)
        bot.set(('Roles', newteam), bot.get('Roles', old))
        bot.remove('Roles', old)
        for pid in bot.Modules['Discord_Module'].usersWithRole(bot, old):
            bot.set(('Players', pid, 'Roles'), [newteam if r == old else r for r in bot.get('Players', pid, 'Roles')])

    data['Role'] = newteam
    bot.remove('Teams', oldteam)
    bot.set(('Teams', newteam), data)
    if data['Order']['Recall Turn'] is not None: scheduleRecall(bot, newteam, data['Order']['Recall Turn'])
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Renamed the team {oldteam} to {newteam}.")

async def teamAddPlayer(bot, payload, *args):
    words = payload['Content'].split(' ', 2)
    player, team = (words[1].strip(), words[2].strip()) if len(words) > 2 else ('', '')
    pid = pidFrom(bot, player)
    if pid is None or team == '':
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !team-add-player <@player> <name>.")
    if team not in bot.keys('Teams'):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"There is no team called {team}.")
    if not bot.Modules['Discord_Module'].isPlayer(bot, pid):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} is not a player.")
    old = teamOf(bot, pid)
    if old == team:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} is already on {team}.")

    text = f"{bot.get('Players', pid, 'Name')} is now on {team}."
    if old is not None:
        bot.stage(('Teams', old, 'Members'), '.remove', pid)
        text = f"{bot.get('Players', pid, 'Name')} moved from {old} to {team}."
    bot.stage(('Teams', team, 'Members'), 'append', pid)
    bot.add_Task(syncRoles)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)

async def teamRemovePlayer(bot, payload, player = '', *args):
    words = payload['Content'].split(' ', 2)
    pid = pidFrom(bot, words[1].strip()) if len(words) > 1 else None
    if pid is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !team-remove-player <@player>.")
    if not bot.Modules['Discord_Module'].isPlayer(bot, pid):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} is not a player.")
    old = teamOf(bot, pid)
    if old is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} is not on a team.")

    text = f"{bot.get('Players', pid, 'Name')} is no longer on {old}."
    bot.stage(('Teams', old, 'Members'), '.remove', pid)
    bot.add_Task(syncRoles)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text)


async def teamData(bot, payload, *args):
    words = payload['Content'].split(' ', 1)
    name = words[1].strip() if len(words) > 1 else ''
    team = name if name else teamOf(bot, payload['Author PID'])
    if team is None or team not in bot.keys('Teams'):
        text = "I couldn't find that team." if name else "You aren't on a team. Use !team-data <name>."
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{text}\nTeams : {', '.join(bot.keys('Teams')) or 'None'}", ephemeral=True)
    data = bot.get('Teams', team)
    text  = f"Team : {team}\n"
    text += f"Members : {', '.join(bot.get('Players', pid, 'Name') for pid in data['Members']) or 'None'}\n"
    text += f"Channel : {data['Channel']}\n"
    text += f"Role : {data['Role']}\n"
    text += f"Bags : {', '.join(f'{k}: {v}' for k, v in data['Bags'].items()) or 'None'}\n"
    text += f"Cups : {', '.join(f'{k}: {v}' for k, v in data['Cups'].items()) or 'None'}\n"
    if data['Order']['Text'] is None:
        text += "Order : None\n"
    else:
        text += f"Order : posted <t:{int(data['Order']['Post Time'].timestamp())}:f>"
        if data['Order']['Recall Turn'] is not None: text += f", being removed at the start of turn {data['Order']['Recall Turn']}"
        text += f"\n{data['Order']['Text']}\n"
    await bot.Modules['Discord_Module'].return_resp(bot, payload, text, ephemeral=True)



# Amounts
async def setAmount(bot, payload, *args):
    args = payload['Content'].split(' ')[1:]
    resources = bot.get('Resources')
    holdable = resources['Items'] + resources['Fluids']
    target, amount, name = splitAmount(bot, args)
    if target is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !set-amount <@player or team> <amount> <resource>. The resource must be listed under Intrinsic, Items, Fluids or Sauces.")
    table, key = target
    who = bot.get('Players', key, 'Name') if table == 'Players' else key
    
    if table == 'Players' and name in resources['Intrinsic']:
        if type(amount) is not int:
            return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{name} is intrinsic, so the amount must be a whole number.")
        bot.set(('Players', key, 'Intrinsic', name), amount)
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{who} now has {amount} {name}.")

    if name in resources['Intrinsic']:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{name} is intrinsic, and teams don't hold intrinsic resources.")
    if name not in holdable:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{name} isn't listed under Intrinsic, Items or Fluids.")
    if amount < 0 or (name in resources['Items'] and type(amount) is not int):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "The amount can't be less than 0, and must be a whole number for an item.")
    path = ('Players', key, 'Pockets') if table == 'Players' else ('Teams', key, 'Bags' if name in resources['Items'] else 'Cups')
    have = bot.get(*path, name) if bot.has(*path, name) else 0
    if table == 'Players' and amount - have > pocketRoom(bot, key):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"That doesn't fit in {who}'s pockets. Raise their {pocketsStat} first.")
    if amount == 0: bot.remove(*path, name)
    else:           bot.set(path + (name,), amount)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{who} now has {amount} {name} in their {path[-1].lower()}.")

# only works for items/fluids
async def give(bot, payload, *args):
    args = payload['Content'].split(' ')[1:]
    pid = payload['Author PID']
    resources = bot.get('Resources')
    target, amount, name = splitAmount(bot, args)
    if target is None or target == ('Players', pid):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !give <@another player or team> <amount> <item>.")
    if amount <= 0 or (name in resources['Items'] and type(amount) is not int):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "The amount must be more than 0, and a whole number for an item.")
    have = bot.get('Players', pid, 'Pockets', name) if bot.has('Players', pid, 'Pockets', name) else 0
    if have < amount:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"You only have {have} {name} in your pockets.")

    table, key = target
    who = bot.get('Players', key, 'Name') if table == 'Players' else key
    if table == 'Players' and not bot.Modules['Discord_Module'].isPlayer(bot, key):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{who} is not a player.")
    if table == 'Players' and amount > pocketRoom(bot, key):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{who} doesn't have room in their pockets.")
    path = ('Players', key, 'Pockets') if table == 'Players' else ('Teams', key, 'Bags' if name in resources['Items'] else 'Cups')
    theirs = bot.get(*path, name) if bot.has(*path, name) else 0
    left = toNumber(have - amount)
    if left == 0: bot.remove('Players', pid, 'Pockets', name)
    else:         bot.set(('Players', pid, 'Pockets', name), left)
    bot.set(path + (name,), toNumber(theirs + amount))
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} gave {amount} {name} to {who}.")

async def pocket(bot, payload, *args):
    pid = payload['Author PID']
    resources = bot.get('Resources')
    args = payload['Content'].split(' ')[1:]
    if len(args) < 2:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !pocket <amount> <item>.")
    amount, name = toNumber(args[0]), args[1]
    team = teamOf(bot, pid)
    if amount is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "Use !pocket <amount> <item>.")
    if name not in resources['Items'] + resources['Fluids']:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{name} isn't an item or a fluid. !resources lists them.")
    if team is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "You aren't on a team.")
    if amount <= 0 or (name in resources['Items'] and type(amount) is not int):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "The amount must be more than 0, and a whole number for an item.")
    path = ('Teams', team, 'Bags' if name in resources['Items'] else 'Cups')
    stock = bot.get(*path, name) if bot.has(*path, name) else 0
    if stock < amount:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team} only has {stock} {name} in its {path[-1].lower()}.")
    if amount > pocketRoom(bot, pid):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "You don't have room in your pockets.")

    have = bot.get('Players', pid, 'Pockets', name) if bot.has('Players', pid, 'Pockets', name) else 0
    left = toNumber(stock - amount)
    if left == 0: bot.remove(*path, name)
    else:         bot.set(path + (name,), left)
    bot.set(('Players', pid, 'Pockets', name), toNumber(have + amount))
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{bot.get('Players', pid, 'Name')} pocketed {amount} {name} from {team}.")



# Orders
async def order(bot, payload, *args):
    team = teamOf(bot, payload['Author PID'])
    words = payload['Content'].split(' ',1)
    text = bot.discord.utils.escape_mentions(words[1].strip()) if len(words) > 1 else ''  # the bot reposts this, so it mustn't ping
    if team is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "You aren't on a team.")
    if text == '' or len(text) > maxOrderLen:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"Use !order <text>, with at most {maxOrderLen} characters.")
    if bot.get('Teams', team, 'Order', 'Text') is not None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team} already has an order posted. Use !order-recall to remove it at the start of the next turn.")
    if not bot.has('Text Channels', orderChan):
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"#{orderChan} doesn't exist yet, try again in a moment.")

    msgs = await bot.Modules['Discord_Module'].send(bot, orderChan, f"{team}'s order:\n{text}")
    bot.set(('Teams', team, 'Order'), {'Text': text, 'Post Time': bot.get('Vars', 'Time'), 'Recall Turn': None, 'MID': msgs[0]['MID']})
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team}'s order is posted in #{orderChan}.")

async def orderRecall(bot, payload, *args):
    team = teamOf(bot, payload['Author PID'])
    if team is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, "You aren't on a team.")
    if bot.get('Teams', team, 'Order', 'Text') is None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team} has no order posted.")
    if bot.get('Teams', team, 'Order', 'Recall Turn') is not None:
        return await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team}'s order is already being removed at the start of turn {bot.get('Teams', team, 'Order', 'Recall Turn')}.")
    turn = bot.get('Vars', 'Turn') + 1
    bot.set(('Teams', team, 'Order', 'Recall Turn'), turn)
    scheduleRecall(bot, team, turn)
    await bot.Modules['Discord_Module'].return_resp(bot, payload, f"{team}'s order will be removed at the start of turn {turn}.")


async def reload_references(bot):
    # Queued, so it runs once Discord_Module's reload of the roles is committed
    bot.add_Task(syncRoles)

"""
Update Function Called Every 10 Seconds
"""
async def update(bot):
    # Players mirror the Intrinsic list
    listed = bot.get('Resources', 'Intrinsic')
    for pid, player in bot.get('Players').items():
        if not bot.Modules['Discord_Module'].isPlayer(bot, pid): continue
        if 'Pockets' not in player: bot.set(('Players', pid, 'Pockets'), {})
        for name in listed:
            if name not in player.get('Intrinsic', {}): bot.set(('Players', pid, 'Intrinsic', name), intrinsicStart.get(name, 0))
        for name in player.get('Intrinsic', {}):
            if name not in listed: bot.remove('Players', pid, 'Intrinsic', name)
