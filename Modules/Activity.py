import discord
inactiveRule = [ ]

InactiveRole  = "Inactive"
OverdueRole = "Overdue"
ModBlockRole = 'Mod-Blocked'
inactive_forcing_roles = [OverdueRole, ModBlockRole]


async def makeActive(bot, pid):
    if bot.Modules['Discord_Module'].isActive(bot, pid): return
    else: await bot.Modules['Discord_Module'].removeRole(bot, pid, InactiveRole)

async def makeInactive(bot,pid):
    if not bot.Modules['Discord_Module'].isActive(bot, pid): return
    else: await bot.Modules['Discord_Module'].addRole(bot, pid, InactiveRole)


async def update(bot,):
    roles = bot.keys('Roles')
    for role in [InactiveRole, OverdueRole, ModBlockRole]:
        if role not in roles: 
            bot.add_Task(bot.Modules['Discord_Module'].create_role, {'roleName': role})

    for pid in bot.keys('Players'):
        if not bot.Modules['Discord_Module'].isPlayer(bot, pid): continue

        # Active Checks
        if bot.Modules['Discord_Module'].isActive(bot, pid):
            if bot.get('Players',pid).get('Last Active Time') is not  None:
                bot.set(('Players', pid, 'Last Active Time'), None)
        # Inactive Checks
        else:
            if bot.get('Players',pid).get('Last Active Time') is  None:
                bot.set(('Players', pid, 'Last Active Time'), bot.get('Vars','Time'))
        
            for role in inactive_forcing_roles:
                if bot.Modules['Discord_Module'].hasRole(bot, pid, role): await makeInactive(bot, pid)


async def attemptActivate(bot,pid):
    if not bot.Modules['Discord_Module'].isActive(bot, pid):
        for role in inactive_forcing_roles:
            if bot.Modules['Discord_Module'].hasRole(bot, pid, role): return False
        await makeActive(bot, pid)
    return True



async def declare_inactive(bot, interaction:  discord.Interaction):
    if type(interaction) is dict:
        s = await makeInactive(bot, interaction["Author PID"])
    else:
        s = await makeInactive(bot, interaction.user.id)
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'You are now Inactive', ephemeral=0)

async def declare_active(bot, interaction:  discord.Interaction):
    if type(interaction) is dict:
        s = await attemptActivate(bot, interaction["Author PID"])
    else:
        s = await attemptActivate(bot, interaction.user.id)
    if s: 
        await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'You are now Active', ephemeral=0)
    else:
        await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'You cannot be made active at this time. You have a forced inactive role', ephemeral=True)


async def setup(bot): 
    
    bot.Modules['Commands'].add_command(bot,
        name= 'declare-active',
        description= 'make yourself Active if possible',
        callback = declare_active,
        checks = ['isPlayer', 'isActions'])

    bot.Modules['Commands'].add_command(bot,
        name= 'declare-inactive',
        description= 'make yourself Inctive if possible',
        callback = declare_inactive,
        checks = ['isPlayer', 'isActions'])

