#
# Activity Days Module For Discord Bot (Rule 307)
################################
import random

activityChan   = 'actions'
activityChance = 1/8                # each day except Monday
activityDays   = ['Rain Day', 'Circus Day', 'Snow Day', 'Leg Day', 'Arms Day', 'Fun Day', 'Spaghetti Night', 'Judgement Day']   # all equally likely


async def setup(bot):
    if not bot.has('Vars', 'Activity Day'): bot.set(('Vars', 'Activity Day'), None)


# Called from Schedules.onDayStart, after the Start Of Day message
async def onDayStart(bot):
    if bot.get('Vars', 'Weekday') == 'Monday': return bot.set(('Vars', 'Activity Day'), None)    # never an Activity Day, so nothing to announce

    day = None
    if random.random() < activityChance:
        day = random.choice(activityDays)
    bot.set(('Vars', 'Activity Day'), day)

    if day is None: text = 'Today is not an Activity Day.'
    else:           text = f'Today is an Activity Day: **{day}**'
    await bot.Modules['Discord_Module'].send(bot, activityChan, text)
