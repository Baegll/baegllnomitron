#
# Admin Module For Discord Bot
################################


async def setup(bot):
    bot.Modules['Commands'].add_command(bot,
        name= 'history-check',
        description= 'mod only -  reload the history files and show differences from the current state',
        callback = historyCheck,
        checks = ['isMod'])

    bot.Modules['Commands'].add_command(bot,
        name= 'history-overwrite',
        description= 'mod only -  pick which side wins a history/state mismatch at the next start: history, state or off',
        callback = historyOverwrite,
        checks = ['isMod'])

    bot.Modules['Commands'].add_command(bot,
        name= 'restart',
        description= 'mod only -  save and exit and restart',
        callback = exitBot,
        checks = ['isMod'])

async def historyCheck(bot, interaction, *args):
    unresolved, report = bot.check_history()
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, '\n'.join(report), wrap=['```\n', '```'])

async def historyOverwrite(bot, interaction, mode = '', *args):
    path = bot.Modules['Nomitron'].HISTORY_OVERWRITE
    if mode == 'off':
        bot.remove(*path)
    elif mode in ['history', 'state']:
        bot.set(path, kwargs=mode)
    else:
        return await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Use !history-overwrite history, state or off.')
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, f"At the next start, a history/state mismatch will be resolved in favour of: {mode}. Use !exit to restart now.")

async def exitBot(bot, interaction, *args):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'Saving and exiting.')
    bot.merge_commit(message=f'Exit command - {bot.now()}')    # commit this batch, e.g. a !history-overwrite just before
    await bot.client.close()                                   # client.run returns and Nomitron saves on the way out

async def update_display(bot):
    chanName = 'game-data'
    if not bot.has('Text Channels', chanName):
        return await bot.Modules['Discord_Module'].create_channel(bot, chanName, 'BUSINESS', 'Locked')
    
    displayMsgs = [ ]
    displayMsgs.append({
            'Content': f"Nomic Time: Week {bot.get('Vars', 'Week')} - Day {bot.get('Vars', 'Day')} ({bot.get('Vars', 'Weekday')})- Turn {bot.get('Vars', 'Turn')} \n at {bot.get('Vars', 'Time').strftime('%Y-%m-%d %H:%M:%S')}",
    })
    displayMsgs.append({
            'Content': f"Next Proposal Number {bot.get('Vars', 'Next Proposal Number')} ",
    })
    await bot.Modules['Discord_Module'].display(bot, chanName, displayMsgs)
 
    