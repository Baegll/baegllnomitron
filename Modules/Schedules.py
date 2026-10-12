#
#  Nomitron 6 Safe
#

async def setup(bot):
    if not bot.has('Vars', 'Day'):  bot.set(('Vars', 'Day'), 0)
    if not bot.has('Vars', 'Turn'): bot.set(('Vars', 'Turn'), 0)
    if not bot.has('Vars', 'Week'): bot.set(('Vars', 'Week'), 0)
    if not bot.has('Vars', 'Week'): bot.set(('Vars', 'Weekday'), 'Unknown')

    if 'End Of Day' not in bot.keys('Schedules'): 
        bot.schedule(
            name = 'End Of Day',
            method_name = 'onDayEnd',
            module_name = 'Schedules',
            Key = ('Vars','Time'), Mode='>=', Trigger_Value= bot.Modules['Nomitron'].startDate, sequential_only=False
        )
    if 'End Of Week' not in bot.keys('Schedules'): 
        bot.schedule(
            name = 'End Of Week',
            method_name = 'onWeekEnd',
            module_name = 'Schedules',
            Key = ('Vars','Time'), Mode='>=', Trigger_Value= bot.Modules['Nomitron'].startDate, sequential_only=False
        ) 

    day = bot.get('Vars', 'Day') if bot.has('Vars', 'Day') else 0
    turn = bot.get('Vars', 'Turn') if bot.has('Vars', 'Turn') else 0
    week = bot.get('Vars', 'Week') if bot.has('Vars', 'Week') else 0
    if 'Start Of Day' not in bot.keys('Schedules'): 
        bot.schedule(
            name = 'Start Of Day',
            method_name = 'onDayStart',
            module_name = 'Schedules',
            Key = ('Vars','Day'), Mode='==', Trigger_Value= day + 1, sequential_only=False
        ) 
    if 'Start Of Turn' not in bot.keys('Schedules'): 
        bot.schedule(
            name = 'Start Of Turn',
            method_name = 'onTurnStart',
            module_name = 'Schedules',
            Key = ('Vars','Turn'), Mode='==', Trigger_Value= turn + 1, sequential_only=False
        )
    if 'Start Of Week' not in bot.keys('Schedules'): 
        bot.schedule(
            name = 'Start Of Week',
            method_name = 'onWeekStart',
            module_name = 'Schedules',
            Key = ('Vars','Week'), Mode='==', Trigger_Value= week + 1, sequential_only=False
        ) 

    print('   Schedules Created:')

async def onDayEnd(bot):
    bot.log(f"End Of Day {bot.get('Vars', 'Day')}") 
    # await bot.Modules['Discord_Module'].send(bot, "actions", f"-----------END OF DAY {bot.get('Vars', 'Day')}---------")
    
    day = bot.get('Vars', 'Day') + 1
    isEndOfTurn = ((day-1)*bot.day + bot.Modules['Nomitron'].startDate).weekday() in [0,3,5]
    bot.stage(('Vars', 'Day'), 'increment', 1)
    bot.set(('Vars', 'Weekday'), ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][((day-1)*bot.day + bot.Modules['Nomitron'].startDate).weekday()])
    bot.schedule(
        name = 'End Of Day',
        method_name = 'onDayEnd',
        module_name = 'Schedules',
        Key = ('Vars','Time'), Mode='>=', Trigger_Value= bot.Modules['Nomitron'].startDate + (day * bot.day), sequential_only=False
    )
    # =============================================
    # Perform On Day End Functions Here============


    # =============================================
    if isEndOfTurn:
        await bot.wrap( onTurnEnd, {'bot':bot} )

async def onTurnEnd(bot):
    bot.log(f"End Of Turn {bot.get('Vars', 'Turn')}")
    bot.stage(('Vars', 'Turn'), 'increment', 1)
   
    # =============================================
    # Perform On Day End Functions Here============
    await bot.Modules['Voting'].TallyVotes(bot)


    # =============================================
  
async def onWeekEnd(bot):
    bot.log(f"End Of Week {bot.get('Vars', 'Week')}")
    week = bot.get('Vars', 'Week') + 1
    bot.stage(('Vars', 'Week'), 'increment', 1)
    weekstart = bot.Modules['Nomitron'].startDate - bot.Modules['Nomitron'].startDate.weekday() * bot.day
    
    bot.schedule(
        name = 'End Of Week',
        method_name = 'onWeekEnd',
        module_name = 'Schedules',
        Key = ('Vars','Time'), Mode='>=', Trigger_Value= weekstart + (week * bot.week), sequential_only=False
    )  

    # =============================================
    # Perform On Week End Functions Here===========

    # =============================================


async def onDayStart(bot):
    dayStartTime = (bot.get('Vars', 'Day')-1)*bot.day + bot.Modules['Nomitron'].startDate
    bot.log(f"START OF DAY {bot.get('Vars', 'Day')} <t:{int(dayStartTime.timestamp())}:t>")

    await bot.Modules['Discord_Module'].send(bot, "actions", f"Start Of Day {bot.get('Vars', 'Day')} {bot.get('Vars', 'Weekday')} : <t:{int(dayStartTime.timestamp())}:f>")
    
    bot.schedule(
        name = 'Start Of Day',
        method_name = 'onDayStart',
        module_name = 'Schedules',
        Key = ('Vars','Day'), Mode='==', Trigger_Value= bot.get('Vars','Day') + 1, sequential_only=False
    )
    # =============================================
    # Perform On Day Start Functions Here==========


    # =============================================

async def onTurnStart(bot):
    turnStartTime = (bot.get('Vars', 'Day')-1)*bot.day + bot.Modules['Nomitron'].startDate
    bot.log(f"START OF TURN {bot.get('Vars', 'Turn')} {bot.get('Vars', 'Weekday')}  <t:{int(turnStartTime.timestamp())}:t>")

    await bot.Modules['Discord_Module'].send(bot, "actions", f"Start Of Turn {bot.get('Vars', 'Turn')}")
    bot.schedule(
        name = 'Start Of Turn',
        method_name = 'onTurnStart',
        module_name = 'Schedules',
        Key = ('Vars','Turn'), Mode='==', Trigger_Value= bot.get('Vars','Turn') + 1, sequential_only=False
    )

    turnDurration =3 if ((bot.get('Vars', 'Day')-1)*bot.day + bot.Modules['Nomitron'].startDate).weekday() == 0 else 2
    turnEndTime = (bot.get('Vars', 'Day') + turnDurration - 1) * bot.day + bot.Modules['Nomitron'].startDate

    bot.schedule(
        name = f'On Deck',
        method_name = 'popProposalMain',
        module_name = 'Voting',
        Key = ('Vars','Time'), Mode='>=', Trigger_Value= turnEndTime - 2*bot.day, sequential_only=False
    ) 

    bot.schedule(
        name = f'Vote Starts',
        method_name = 'PutToVote',
        module_name = 'Voting',
        Key = ('Vars','Time'), Mode='>=', Trigger_Value= turnEndTime - 1*bot.day, sequential_only=False
    ) 

    # =============================================
    # Perform On Turn Start Functions Here=========
    await bot.wrap( bot.Modules['Voting'].popProposalJudge, {'bot':bot} )


    # =============================================
        

async def onWeekStart(bot):
    bot.log(f"START Of Week {bot.get('Vars', 'Week')}")
    await bot.Modules['Discord_Module'].send(bot, "actions", f"Start Of Week {bot.get('Vars', 'Week')}")
    week = bot.get('Vars', 'Week')
    
    bot.schedule(
        name = 'Start Of Week',
        method_name = 'onWeekStart',
        module_name = 'Schedules',
        Key = ('Vars','Week'), Mode='==', Trigger_Value= week + 1, sequential_only=False
    ) 

    # =============================================
    # Perform On Week Start Functions Here=========


    # =============================================

