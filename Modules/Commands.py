import discord, numpy, sys, os, inspect, io, typing, asyncio
import random
file_path  = os.path.realpath(os.path.abspath(inspect.getfile(inspect.currentframe())))
path  = os.path.realpath(os.path.abspath(os.path.join(file_path, os.pardir,)))+'/'

def add_command(bot, name, description, callback, checks):
    """Add a command to the bot's command tree.

    ``name`` is the command name, ``description`` is a brief description of
    the command, ``callback`` is the function to be called when the command
    is invoked, and ``checks`` is a list of check functions that determine
    whether the command can be executed.
    """
    # Implementation of adding the command to the bot's command tree goes here.
    if not hasattr(bot, 'Commands'):
        bot.Commands = {}
    bot.Commands[name] = {
        'name': name,
        'description': description,
        'callback': callback,
        'checks': checks
    }

async def isMod(bot, interaction: discord.Interaction):
    if type(interaction) is dict:            
        oktouse = bot.Modules['Discord_Module'].isModerator(bot, interaction['Author PID'])
    else:
        oktouse = bot.Modules['Discord_Module'].isModerator(bot, interaction.user.id)
    return oktouse

async def isPlayer(bot, interaction: discord.Interaction):
    if type(interaction) is dict:            
        oktouse = bot.Modules['Discord_Module'].isPlayer(bot, interaction['Author PID'])
    else:
        oktouse = bot.Modules['Discord_Module'].isPlayer(bot, interaction.user.id)
    return oktouse

async def isDM(bot, interaction: discord.Interaction):
    if type(interaction) is dict:            
        return interaction['Category'] == 'DM'
    else:
        return interaction.channel.type in [bot.discord.ChannelType.private, bot.discord.ChannelType.group]
    
async def isActions(bot, interaction: discord.Interaction):
    if type(interaction) is dict:            
        return interaction['Channel'] == 'actions'
    else:
        return interaction.channel.name == 'actions'
    
async def isSpam(bot, interaction: discord.Interaction):
    if type(interaction) is dict:            
        return ( await isDM(bot, interaction) ) or 'spam' in interaction['Channel']
    else:
        return ( await isDM(bot, interaction) ) or 'spam' in interaction.channel.name
    
checks = {}
checks['isMod'] = isMod
checks['isPlayer'] = isPlayer
checks['isDM'] = isDM
checks['isActions'] = isActions
checks['isSpam'] = isSpam


async def help(bot, interaction: discord.Interaction):
    txt = "Your Available Commands:\n - Use !COMMAND to activate them.\n"
    commands = sorted(bot.Commands.values(), key=lambda x: x['name'])
    
    if await checks['isMod'](bot, interaction):
        txt += "Mod Commands:\n"
        for cmd in commands:
            if ('isMod' in cmd['checks']):
                txt += f"- !{cmd['name']} : {cmd['description']}\n"
        
        txt += "Player Commands:\n"

    for cmd in commands:
        if 'isMod' in cmd['checks']: continue
        txt += f"- !{cmd['name']} : {cmd['description']}\n"

    await bot.Modules['Discord_Module'].return_resp(bot, interaction, txt, wrap=['```diff\n', '```'])
    
async def data(bot, interaction: discord.Integration, player = None):
    if type(interaction) is dict:
        pid = interaction['Author PID'] if player is None else ''.join([char for char in player if char.isdigit()])
    else:
        pid = interaction.user.id if player is None else player.id
    if pid == '' or not bot.has('Players', int(pid)): return await bot.Modules['Discord_Module'].return_resp(bot, interaction, "I couldn't find that player.", ephemeral=True)
    pid = int(pid)
    text  = f"Player : {bot.get('Players',pid, 'Name')}\n"
    text += f"Roles : {', '.join(bot.get('Players',pid, 'Roles'))}\n"
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, text, ephemeral=True)

async def roll(bot, interaction: discord.Interaction, dice :str):
    diceInfo = dice.split('d')
    if len(diceInfo) == 2:
        randNum = numpy.random.randint(1, int(diceInfo[1])+1, int(diceInfo[0]))
        text = f"{dice} -> {sum(randNum)} : {str(randNum).replace('  ',' ').replace(' ',', ')}"
    else: text =  "Bad dice format. Please use something like 69d420 to roll 69 dice with 420 sides"
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, text)

async def ping(bot, interaction: discord.Interaction,): 
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Pong')

async def dance(bot, interaction: discord.Interaction,): 
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, "https://media.tenor.com/3SSi0qLshgkAAAAC/time-to-party-dance.gif")

async def echo(bot, interaction: discord.Interaction, *text):

    await bot.Modules['Discord_Module'].return_resp(bot, interaction, ' '.join(text))


async def clear(bot, interaction: discord.Interaction):
    if type(interaction) is dict:
        if interaction['Category'] == 'DM': return await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Cannot do in DMs')
        messages = [m async for m in bot.Modules['Discord_Module'].chan_from_Name(bot, interaction['Channel']).history(limit=200)]
    else:
        messages = [m async for m in interaction.channel.history(limit=200)]
    for msg in messages: 
        try:await msg.delete()
        except: pass
    
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, '200 Messages Removed By Mod')

async def reloadRefs(bot, interaction:  discord.Interaction):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, f"Refreshing All References")
    await bot.Modules['Nomitron'].RELOAD_REFS(bot)

async def sudo(bot, interaction:  discord.Interaction):
    if type(interaction) is dict:
        if interaction["Author PID"] not in [471529178462814209, ]: return await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Bad!!! You cant use this!!', ephemeral=1)
        if bot.Modules['Discord_Module'].hasRole(bot, interaction["Author PID"], 'Moderator'):
            await bot.Modules['Discord_Module'].removeRole(bot, interaction["Author PID"], 'Moderator')
        else:
            await bot.Modules['Discord_Module'].addRole(bot, interaction["Author PID"], 'Moderator')
    else:
        if interaction.user.id not in [471529178462814209, ]: return await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Bad!!! You cant use this!!', ephemeral=1)
        if bot.Modules['Discord_Module'].hasRole(bot,  interaction.user.id, 'Moderator'):
            await bot.Modules['Discord_Module'].removeRole(bot, interaction.user.id, 'Moderator')
        else:
            await bot.Modules['Discord_Module'].addRole(bot, interaction.user.id, 'Moderator')
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Done', ephemeral=1)

async def playerWithRoles(bot, interaction:  discord.Interaction, *role):
    if type(interaction) is dict:
        roleName = ' '.join(role)
    else:
        roleName = role[0].name
    pids = bot.Modules['Discord_Module'].usersWithRole(bot, roleName)
    names = [bot.get('Players', p,'Name') for p in pids]
    
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Players:\n'+('\n'.join(names)), ephemeral=False)


async def setup(bot):
    global checks    

    #############################################################
    # Settup Command Checks    
    add_command(bot,
        name= 'help',
        description= 'get Help for Commands',
        callback = help,
        checks = ['isSpam', 'isPlayer'])

    add_command(bot,
        name= 'player-data',
        description= "get a player's data",
        callback = data,
        checks = ['isSpam', 'isPlayer'])

    add_command(bot,
        name= 'ping',
        description= 'mod only -  ping Nomitron for a response',
        callback = ping,
        checks = ['isMod'])

    add_command(bot,
        name= 'dance',
        description= 'make nomitron dance.',
        callback = dance,
        checks = ['isPlayer'])
    
    add_command(bot, 
        name= 'roll',
        description= 'roll dice.',
        callback = roll,
        checks = [])

    add_command(bot,
        name= 'echo',
        description= 'mod only -  Nomitron says what you tell it to.',
        callback = echo,
        checks = ['isMod'])

    add_command(bot,
        name= 'refresh-references',
        description= 'mod only -  refresh the server data rules etc',
        callback = reloadRefs,
        checks = ['isMod'])

    add_command(bot,
        name= 'player-role-list',
        description= 'mod only -  list all players with a role',
        callback = playerWithRoles,
        checks = ['isMod'])

    add_command(bot,
        name= 'sudo',
        description= 'mod only -  toggle mod role',
        callback = sudo,
        checks = [])



async def on_message(bot, message):
    if message['Content'][0] == '!':
        cmdKey = message['Content'].split(' ')[0][1:]
        if cmdKey in bot.Commands.keys():
            for check in bot.Commands[cmdKey]['checks']:
                checkResult = await checks[check](bot, message)
                if not checkResult: 
                    return await bot.Modules['Discord_Module'].add_reaction(bot, msgid = message['MID'], dm_pid_or_channel_name = message['Channel'], emoji = '❌')
            args = [message,] + message['Content'].split(' ')[1:]

            await bot.Commands[cmdKey]['callback'](bot,*args)

    if '?' in message['Content'] and '!' == message['Content'][0]:
        options = [[
         "It is certain.",
         "It is decidedly so.",
         "Without a doubt.",
         "Yes definitely.",
         "You may rely on it.",
         "As I see it, yes.",
         "Most likely.",
         "Outlook good.",
         "Yes.",
         "Signs point to yes.",
        ],[
         "Reply hazy, try again.",
         "Ask again later.",
         "Better not tell you now.",
         "Cannot predict now.",
         "Concentrate and ask again.",
        ],[
         "Don't count on it.",
         "My reply is no.",
         "My sources say no.",
         "Outlook not so good.",
         "Very doubtful."]]
        await bot.Modules['Discord_Module'].return_resp(bot, message, random.choice(random.choice(options)))
