#
# Voting System Module For Discord Bot
################################
import pickle, sys, time, io, discord, datetime, urllib, re, random # pyright: ignore[reportMissingImports]
from copy import *
defaultProposalData = {
    'Votees': [],
    'Yay':[],
    'Nay':[],
    'Abstain':[],
    'Supporters':[],
    'MIDs': [],
    
    'DOB': None,
    'ProposingPlayer': None,
    'ProposingText' : "" ,
    'Proposal#': 0,
    'Mode': "Unknown", # Queued, Deck, Voting
    'Source': "Unkonwn", # one of the queues
    'Voting-Channel': None,
    'Voting-Start-Time': None,
}
  
  
Queues = ['main', 'judge', 'tarot']
  
yayEmojis = []
yayVotes = [ "aye", "yay", "yes", "y",]

nayEmojis = []
nayVotes = ["nay", "no", "n", ]

abstainEmojis = []
abstainVotes = ['abstain', 'withdraw']
  


propVoteArchiveCat  = lambda propNum: f"CLOSED-VOTES-{50*(propNum//50)}-{49 + 50*(propNum//50)}"
votingChanGen       = lambda propNum: f"proposal-{propNum}".lower().replace(' ','-')
proposalChanGen     = lambda queue: f"{queue}-proposals"
queueChanGen        = lambda queue: f"{queue}-queue"

# Nomitron 6 bot.where returns (table, row id) paths; unwrap them to row ids like the old table API
def where(bot, table, conditional): return [k[1] for k in bot.where((table, '*'), conditional)]

async def setup(bot):
    bot.Modules['Commands'].add_command(bot,
        name= 'opt-in-judge',
        description= 'opt into being a judge',
        callback = optInJudge,
        checks = ['isPlayer', 'isActions'])

    bot.Modules['Commands'].add_command(bot,
        name= 'opt-out-judge',
        description= 'opt out of being a judge',
        callback = optOutJudge,
        checks = ['isPlayer','isActions'])
     
    bot.Modules['Commands'].add_command(bot,
        name= 'pop-prop',
        description= 'mod only -  pop proposals like start of turn',
        callback = popProposal,
        checks = ['isMod'])

    bot.Modules['Commands'].add_command(bot,
        name= 'open-voting',
        description= 'mod only -  move things from deck to voting',
        callback = deckify,
        checks = ['isMod'])

    bot.Modules['Commands'].add_command(bot,
        name= 'tally',
        description= 'mod only -  tally ALL votes',
        callback = tally,
        checks = ['isMod'])
     
    bot.update_nested_dict(('Queue-Proposals',), structure = {})
    bot.update_nested_dict(('User-Proposal-Votes',), structure = {})
    bot.update_nested_dict(('User-Proposal-Endorsement',), structure = {})
    if not bot.has('Vars', 'Next Proposal Number'): bot.set(('Vars', 'Next Proposal Number'), kwargs=301)
    if not bot.has('Vars', 'Next Proposal Number'): bot.set(('Vars', 'Next Proposal Number'), kwargs=301)

    for q in Queues:
        bot.add_Task(bot.Modules['Discord_Module'].create_channel, dict(text_channel_name=proposalChanGen(q), catagory_name='BUSINESS', permSetName='Player Only') )
        bot.add_Task(bot.Modules['Discord_Module'].create_channel, dict(text_channel_name=queueChanGen(q), catagory_name='BUSINESS', permSetName='Locked') )
    bot.add_Task(bot.Modules['Discord_Module'].create_channel, dict(text_channel_name='deck-edits', catagory_name='BUSINESS', permSetName='Player Only') )



async def optInJudge(bot, interaction:  discord.Interaction):
    if type(interaction) is dict:
        await bot.Modules['Discord_Module'].addRole(bot, interaction["Author PID"], bot.Modules['Discord_Module'].JudgeOptInRole)
    else:
        await bot.Modules['Discord_Module'].addRole(bot, interaction.user.id, bot.Modules['Discord_Module'].JudgeOptInRole)
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, "You have opted in as judge", ephemeral=False)

async def optOutJudge(bot, interaction:  discord.Interaction):
    if type(interaction) is dict:
        await bot.Modules['Discord_Module'].removeRole(bot, interaction["Author PID"], bot.Modules['Discord_Module'].JudgeOptInRole)
    else:
        await bot.Modules['Discord_Module'].removeRole(bot, interaction.user.id, bot.Modules['Discord_Module'].JudgeOptInRole)
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, 'You will no longer be considered for judge', ephemeral=0)

async def popProposal(bot, interaction:  discord.Interaction):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, f"Popping")
    await popProposalMain(bot)

async def deckify(bot, interaction:  discord.Interaction):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, f"Deckify")
    await PutToVote(bot)

async def tally(bot, interaction:  discord.Interaction):
    await bot.Modules['Discord_Module'].return_resp(bot, interaction, f"TallyVotes")
    await TallyVotes(bot)


async def TallyVotes(bot):
    bot.log('Vote Tally')
    arcana = bot.Modules['Arcana']
    rewards = {}
    currentCards = bot.get('Cards')
    history = bot.get('Card Game', 'History') if bot.has('Card Game') else None
    # Tally Main Voting Queue
    propIDs = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'Voting')
    propKeys= [bot.get('Queue-Proposals',propID, 'Proposal#') for propID in propIDs]
    sort_propIDs = [x for _, x in sorted(zip(propKeys, propIDs))]
   
    for propID in sort_propIDs:
        if abs( bot.get('Queue-Proposals', propID, 'Vote Start Time') - bot.get('Vars', 'Time') ) < bot.hr: continue
        yay_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID and df['Vote']=='Yay')) 
        nay_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID and df['Vote']=='Nay')) 
        abs_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID and df['Vote']=='Abstain')) 

        all_votes = yay_votes + nay_votes + abs_votes
        votingPlayersPIDs = [bot.get('User-Proposal-Votes', vid, 'PID-Voter') for vid in all_votes]
        propNum = bot.get('Queue-Proposals',propID, 'Proposal#' )
        propOwnerPid = bot.get('Queue-Proposals',propID, 'PID' )
        propChannel  = bot.get('Queue-Proposals',propID, 'Channel' )
        propOwnerName= bot.get('Players',propOwnerPid, 'Name' )

        announceChan = "actions"
        chan = bot.get_Ref('Text Channels', announceChan)

        # Tally Main Voting ( Nomitron 4 Safe)
        if len(yay_votes) > len(nay_votes):
            if bot.has('Queue-Proposals', propID, 'Arcana'):
                name = bot.get('Queue-Proposals', propID, 'Arcana')
                effect = bot.get('Queue-Proposals', propID, 'Arcana Effect')
                try: arcana.validateEffect(currentCards, name, effect)
                except ValueError as error:
                    # Retain votes and the proposal for adjudication; never apply or
                    # reward an amendment that became invalid after an earlier tally.
                    reason = str(error)
                    if bot.get('Queue-Proposals', propID).get('Arcana Conflict') != reason:
                        await bot.Modules['Discord_Module'].send(bot, chan, f'Proposal #{propNum} has a passing tally but needs adjudication: {reason}')
                        bot.set(('Queue-Proposals', propID, 'Arcana Conflict'), reason)
                    continue
                currentCards['Definitions'][name]['Effect'] = effect
                bot.set(('Cards', 'Definitions', name, 'Effect'), effect)
                recipients = {propOwnerPid} | {bot.get('User-Proposal-Votes', vid, 'PID-Voter') for vid in yay_votes}
                for pid in recipients:
                    if bot.Modules['Discord_Module'].isPlayer(bot, pid): rewards[pid] = rewards.get(pid, 0) + 1
            await bot.Modules['Discord_Module'].send(bot, chan, f"- **Vote Status:**  {propOwnerName}'s Proposal Passes\n" \
                f"  Tally: {len(yay_votes)} For, {len(nay_votes)} Against.")
            if history is not None:
                _, instant = bot.Modules['CardGame'].instantParts(bot.get('Queue-Proposals', propID, 'Body'))
                if propNum == 309:
                    bot.add_Task(bot.Modules['CardGame'].start309, {'author': propOwnerPid})
                if instant and propNum != 309:
                    await bot.Modules['Discord_Module'].send(bot, chan, f'Instant effect from #{propNum} requires immediate moderator adjudication:\n{instant}')
        else:
            await bot.Modules['Discord_Module'].send(bot, chan, f"- **Vote Status:**  {propOwnerName}'s Proposal Failed \n" \
                f"  Tally: {len(yay_votes)} For, {len(nay_votes)} Against.")
    
        if propChannel is not None and bot.has('Text Channels', propChannel):
            if bot.has('Channel Catagories',propVoteArchiveCat(propNum)):
                await bot.Modules['Discord_Module'].move_channel_catagory(bot, propChannel, propVoteArchiveCat(propNum))
                await bot.Modules['Discord_Module'].set_channel_perms(bot, propChannel, 'Locked')
            else:
                await bot.Modules['Discord_Module'].create_category(bot, propVoteArchiveCat(propNum))
                bot.add_Task(bot.Modules['Discord_Module'].move_channel_catagory, {'text_channel_name':propChannel, 'catagory_name':propVoteArchiveCat(propNum)})
                bot.add_Task(bot.Modules['Discord_Module'].set_channel_perms, {'text_channel_name':propChannel, 'permSetName':'Locked'} )
        if history is not None: bot.Modules['CardGame'].recordVote(bot, history, propNum, votingPlayersPIDs)
        bot.remove('Queue-Proposals',propID)
        for vote in all_votes: bot.remove('User-Proposal-Votes',vote)

    for pid, amount in rewards.items():
        bot.set(('Players', pid, 'Intrinsic', 'Crystals'), arcana.crystals(bot, pid) + amount)
    if history is not None:
        bot.set(('Card Game', 'History'), history)

async def PutToVote(bot):
    bot.log('Vote Call')
    propIDs = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'On Deck')
    propKeys= [bot.get('Queue-Proposals',propID, 'Proposal#') for propID in propIDs]
    sort_propIDs = [x for _, x in sorted(zip(propKeys, propIDs))]
    for propID in sort_propIDs:
        bot.set(('Queue-Proposals', propID, 'State'), 'Voting')
        bot.set(('Queue-Proposals', propID, 'Vote Start Time'), bot.get('Vars', 'Time'))

        propNum = bot.get('Queue-Proposals',propID, 'Proposal#' )
        propChannel  = bot.get('Queue-Proposals',propID, 'Channel' )
        announceChan = "actions"
        chan = bot.get_Ref('Text Channels', announceChan)
        if bot.has('Text Channels', propChannel): await bot.Modules['Discord_Module'].set_channel_perms(bot, propChannel, 'Player Only')
        await bot.Modules['Discord_Module'].send(bot, chan, f"Voting is open for Proposal #{propNum}")
       

def proposalText(bot, propID):
    yay_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID and df['Vote']=='Yay')) 
    nay_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID and df['Vote']=='Nay')) 
        
    msg = f"Proposal #{bot.get('Queue-Proposals', propID, 'Proposal#')} by: {bot.get('Players', bot.get('Queue-Proposals', propID, 'PID'), 'Name')} ({bot.get('Queue-Proposals', propID, 'Queue')} queue):\n"
    if bot.get('Queue-Proposals', propID, 'State') in ['Voting',"On Deck"]: msg += f"**Status: { bot.get('Queue-Proposals', propID, 'State') } ({len(yay_votes)} For, {len(nay_votes)} Against.)** \n\n"
    if bot.has('Queue-Proposals', propID, 'Arcana'):
        msg += 'Amend Rule 302 by setting the following Arcana Effect:\n\n'
    msg += bot.get('Queue-Proposals', propID, 'Body')
    return msg
  
async def popProposalMain(bot, scheduled_time=None):
    bot.log('Pop Proposal Main')
    ranked = rank_queue(bot)
    
    # Sort and emojinize
    init_proposal_val = bot.get('Vars', 'Next Proposal Number')

    numberOfProp = 1
    for i in range(numberOfProp):
        propIDs= where(bot, 'Queue-Proposals', lambda df: df['Queue'] == 'main' and df['State'] == 'Queue' and df['Rank'] == i)
        if len(propIDs) == 0: continue

        bot.set(('Queue-Proposals', propIDs[0], 'State'), "On Deck")
        bot.set(('Queue-Proposals', propIDs[0], 'Channel'), votingChanGen(init_proposal_val))
        bot.set(('Queue-Proposals', propIDs[0], 'Proposal#'), init_proposal_val)
        init_proposal_val += 1

    judge_props = where(bot, 'Queue-Proposals', lambda df: df['Queue'] == 'judge' and df['State'] == 'Queue')
    for i in range( len(judge_props) ):
        propIDs= where(bot, 'Queue-Proposals', lambda df: df['Queue'] == 'judge' and df['State'] == 'Queue' and df['Rank'] == i)
        if len(propIDs) == 0: continue

        bot.set(('Queue-Proposals', propIDs[0], 'State'), "On Deck")
        bot.set(('Queue-Proposals', propIDs[0], 'Channel'), votingChanGen(init_proposal_val))
        bot.set(('Queue-Proposals', propIDs[0], 'Proposal#'), init_proposal_val)
        init_proposal_val += 1

    # Tarot numbers follow main and judicial proposals at the scheduled 48-hour mark.
    cards = bot.get('Cards')
    now, turn = bot.get('Vars', 'Time'), bot.get('Vars', 'Turn')
    last = cards.get('Last Tarot Deck Scheduled')
    if scheduled_time is not None and now >= scheduled_time and cards.get('Last Tarot Turn') != turn and (last is None or scheduled_time - last >= 7 * bot.day):
        arcana = bot.Modules['Arcana']
        count = 0 if arcana.hasEffect(bot, 'The Hanged Man') else 3 if arcana.hasEffect(bot, 'The Chariot') else 2
        proposals = ranked['tarot']
        for propID in proposals[:count]:
            bot.set(('Queue-Proposals', propID, 'State'), 'On Deck')
            bot.set(('Queue-Proposals', propID, 'Channel'), votingChanGen(init_proposal_val))
            bot.set(('Queue-Proposals', propID, 'Proposal#'), init_proposal_val)
            init_proposal_val += 1
        bot.set(('Cards', 'Last Tarot Turn'), turn)
        if proposals[:count]:
            bot.set(('Cards', 'Last Tarot Deck Scheduled'), scheduled_time)

    if init_proposal_val != bot.get('Vars', 'Next Proposal Number'):
        bot.set(('Vars', 'Next Proposal Number'), init_proposal_val)

async def popProposalJudge(bot):
    bot.log('Pop Proposal Judge')
    rank_queue(bot)
    
    init_proposal_val = bot.get('Vars', 'Next Proposal Number')
    # Sort and emojinize   
    judge_props = where(bot, 'Queue-Proposals', lambda df: df['Queue'] == 'judge' and df['State'] == 'Queue')
    for i in range( len(judge_props) ):
        propIDs= where(bot, 'Queue-Proposals', lambda df: df['Queue'] == 'judge' and df['State'] == 'Queue' and df['Rank'] == i)
        if len(propIDs) == 0: continue

        bot.set(('Queue-Proposals', propIDs[0], 'State'), "On Deck")
        bot.set(('Queue-Proposals', propIDs[0], 'Channel'), votingChanGen(init_proposal_val))
        bot.set(('Queue-Proposals', propIDs[0], 'Proposal#'), init_proposal_val)
        init_proposal_val += 1

    bot.set(('Vars', 'Next Proposal Number'), init_proposal_val)



async def yay(bot, PID, propID):
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Yay'})
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Yay'})

async def nay(bot, PID, propID):
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Nay'})
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Nay'})

async def abstain(bot, PID, propID):
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Abstain'})
    bot.set(('User-Proposal-Votes', f"{PID}-{propID}"), kwargs={'PID-Voter':PID,'Proposal-ID':propID,'Vote':'Abstain'})



async def on_reaction(bot, reaction):
    chan = reaction['MSG']['Channel']
    mid = reaction['MSG']['MID']
    pid = reaction['Reactor PID']
    if 'CardGame' in bot.Modules and bot.Modules['CardGame'].blockedAction(bot, pid):
        return await bot.Modules['Discord_Module'].return_resp(bot, pid, 'Roll for the Random spell with !card random before any other action, including voting.')

    # if Vote endorsing
    propID = where(bot, 'Queue-Proposals', lambda df: df['Channel'] == chan)
    if len(propID) == 1 and reaction['Mode'] == 'add': # Fixed
        propID = propID[0]

        if not await bot.Modules['Activity'].attemptActivate(bot, pid):
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '❌' )
        else:
            if   reaction['Emoji'] in yayEmojis:     await yay(bot, pid, propID)
            elif reaction['Emoji'] in nayEmojis:     await nay(bot, pid, propID)
            elif reaction['Emoji'] in abstainEmojis: await abstain(bot, pid, propID)
            else: return
    
    # If Queue reaction
    propID = where(bot, 'Queue-Proposals', lambda df: df['Endorse-MID'] == mid and df['State']=='Queue')
    bot.log(f'propID {propID}')
    if len(propID) == 1 and "-queue" in chan and reaction['Mode'] == 'add':
        propID = propID[0]
        await bot.Modules['Discord_Module'].remove_reaction(bot, chan, mid, reaction['Emoji'], pid)
        if not bot.Modules['Discord_Module'].isPlayer(bot, pid):
            await bot.Modules['Discord_Module'].return_resp(bot, pid, "You are not a player and thus cannot endorse proposals")
            return
        if not bot.Modules['Discord_Module'].isActive(bot, pid):
            await bot.Modules['Discord_Module'].return_resp(bot, pid, "You are inactive and thus cannot endorse proposals")
            return 
        
        # Proposal Owener From Encoded ID in File Name        
        if reaction['Emoji'] == '👍':
            bot.set(('User-Proposal-Endorsement', f"{pid}-{propID}"), {
                'PID':pid,'Proposal-ID':propID
            })
        elif reaction['Emoji'] == '👎':
            bot.remove('User-Proposal-Endorsement', f"{pid}-{propID}")
        elif reaction['Emoji'] == 'ℹ️':
            # List Create MSG Header
            msg = f"------\n **{bot.get('Players', bot.get('Queue-Proposals', propID, 'PID'), 'Name')}'s Proposal Info:**\n"
            # Create Supporters
            msg += f"```Supporters:"
            for p in where(bot, 'User-Proposal-Endorsement', lambda df: df['Proposal-ID']==propID): msg += '\n - ' + bot.get('Players', bot.get('User-Proposal-Endorsement',p,'PID'),'Name')
            msg += "```"
            await bot.Modules['Discord_Module'].return_resp(bot, pid, msg)
            await bot.Modules['Discord_Module'].return_resp(bot, pid, f"**Proposal:**\n{bot.get('Queue-Proposals', propID, 'Body')}")
        else: return
  
async def on_message(bot, message):
    chan = message['Channel']
    mid  = message['MID']
    pid  = message['Author PID']
    if 'CardGame' in bot.Modules and bot.Modules['CardGame'].blockedAction(bot, pid): return

    propID = where(bot, 'Queue-Proposals', lambda df: df['Channel'] == chan)
    if len(propID) == 1 and message['Category'] == 'ACTIVE-VOTES': # Fixed        
        propID = propID[0]
        if not await bot.Modules['Activity'].attemptActivate(bot, pid):
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '❌' )
        else:
            vote = message['Content'].lower().strip()
            if   vote in yayVotes:     await yay(bot, pid, propID)
            elif vote in nayVotes:    await nay(bot, pid, propID)
            elif vote in abstainVotes: await abstain(bot, pid, propID)
            else: 
                await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '❌' )
                await bot.Modules['Discord_Module'].return_resp(bot, pid, "Your vote is ambigious, Please use appropriate yay, nay, or withdraw text." )
                return
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '✅' )
            
    # If a proposal is submitted to a proposal submitting channel: Nomi 7
    if message['Category'] == 'BUSINESS' and "-proposals" in chan:
        print(' | Saving Proposal', message['Content'])        
        # Skip if is inactive
        if not bot.Modules['Discord_Module'].isActive(bot, pid):
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '❌' )
            return
        
        # Load the message contents or the attachments if attachment is given
        text = ""
        if len(message['Content']) > 1: text = message['Content']
        for k, filestr in message['Attachments'].items():

            if  '.txt' in k: 
                safe_text = "\n\n"
                safe_text += '\n'.join(
                    [m['Content'] for m in await bot.Modules['Discord_Module'].send(bot, "bot-spam", filestr.decode(encoding="utf-8", errors="strict"))]
                )
                text += safe_text
                # text += '\n\n' + filestr.decode(encoding="utf-8", errors="strict")
        for k, d in message['Attachments'].items():
            if  '.txt' not in k: text += f"\nAttachment: { message['Attachment Links'][k] }"
        
        if chan == 'tarot-proposals':
            arcana = bot.Modules['Arcana']
            old_props = where(bot, 'Queue-Proposals', lambda p: p['PID'] == pid and p['Queue'] == 'tarot' and p['State'] == 'Queue')
            if text.strip() in ['.', '']:
                for op in old_props: bot.remove('Queue-Proposals', op)
                return await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '📬')
            try:
                name, effect = arcana.tarotText(bot, text)
                limit = 2 if arcana.hasEffect(bot, 'Two of Wands') else 1
            except ValueError as error:
                return await bot.Modules['Discord_Module'].return_resp(bot, message, str(error))
            old_props.sort(key=lambda p: bot.get('Queue-Proposals', p, 'DOB'))
            for op in old_props[:max(0, len(old_props) - limit + 1)]: bot.remove('Queue-Proposals', op)
            propid = f"{pid}-{bot.get('Vars', 'Time')}"
            bot.set(('Queue-Proposals', propid), {
                'DOB': bot.get('Vars', 'Time'), 'PID': pid, 'Body': text,
                'Arcana': name, 'Arcana Effect': effect,
                'State': 'Queue', 'Queue': 'tarot', 'Link': message['Link'],
                'Proposal#': None, 'Vote Close Time': None, 'Vote Start Time': None,
                'Channel': None, 'Endorse-MID': None, 'Rank': None,
            })
            bot.set(('User-Proposal-Endorsement', f'{pid}-{propid}'), {'PID': pid, 'Proposal-ID': propid})
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '📬')

        if chan.replace("-proposals", "") == 'main':
            tarot = {}
            arcana = bot.Modules['Arcana']
            if text.partition(':')[0].strip() in arcana.arcana or text.startswith('Amend Rule 302 by setting the following Arcana Effect:'):
                try:
                    name, effect = arcana.tarotText(bot, text)
                    tarot = {'Arcana': name, 'Arcana Effect': effect}
                except ValueError as error:
                    return await bot.Modules['Discord_Module'].return_resp(bot, message, str(error))
            old_props = where(bot, 'Queue-Proposals', lambda df: (df['PID'] == pid and df['Queue']=='main' and df['State']=='Queue')) 
            for op in old_props: bot.remove('Queue-Proposals',op)
            propid = f"{pid}-{bot.get('Vars', 'Time')}"
            bot.set(('Queue-Proposals', propid), {
                'DOB':bot.get('Vars', 'Time'),
                'PID':pid,
                'Body':text,
                'State':'Queue',
                'Queue': 'main',
                **tarot,
                'Link': message['Link'],
                'Proposal#': None, 'Vote Close Time': None, 'Vote Start Time': None, 'Channel': None, 'Endorse-MID': None, 'Rank': None,
            })
            bot.set(('User-Proposal-Endorsement', f"{pid}-{propid}"), {
                'PID':pid,'Proposal-ID':propid
            })
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '📬' )

        
        if chan.replace("-proposals", "") == 'judge':
            isJudge = bot.Modules['Discord_Module'].isJudge(bot, pid)
            if not isJudge: return await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '❌' )

            old_props = where(bot, 'Queue-Proposals', lambda df: (df['PID'] == pid and df['Queue']=='judge' and df['State']=='Queue') )
            for op in old_props: bot.remove('Queue-Proposals',op)
            propid = f"{pid}-{bot.get('Vars', 'Time')}"
            bot.set(('Queue-Proposals', propid), {
                'DOB':bot.get('Vars', 'Time'),
                'PID':pid,
                'Body':text,
                'State':'Queue',
                'Queue': 'judge',
                'Link': message['Link'],
                'Proposal#': None, 'Vote Close Time': None, 'Vote Start Time': None, 'Channel': None, 'Endorse-MID': None, 'Rank': None,
            })
            bot.set(('User-Proposal-Endorsement', f"{pid}-{propid}"), {
                'PID':pid,'Proposal-ID':propid
            })
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '✅' )

        bot.add_Task(rank_queue)


    # If a proposal is on deck
    if chan == 'deck-edits':
        print(' | Updating Deck Proposal')

        deck_propIDs = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'On Deck' and df['PID'] == pid)
        
        if len(deck_propIDs) == 0:
            await bot.Modules['Discord_Module'].return_resp(bot, chan,"There are no decks that can be edited by you at this time.")
            return
        if len(deck_propIDs) == 1:
            propID = deck_propIDs[0]
            text = ""
            if len(message['Content']) > 1: text = message['Content']
            for k, filestr in message['Attachments'].items():
                if  '.txt' not in k: continue
                safe_text = "\n\n"
                safe_text += '\n'.join(
                    [m['Content'] for m in await bot.Modules['Discord_Module'].send(bot, "bot-spam", filestr.decode(encoding="utf-8", errors="strict"))]
                )
                text += safe_text
            for k, d in message['Attachments'].items():
                if  '.txt' not in k: text += f"\nAttachment: { message['Attachment Links'][k] }"
            
            if not await validateDeckEdit(bot, message, propID, text): return
            bot.set(('Queue-Proposals', propID, 'Body'), text)
            await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '✅' )
            all_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID)) 
            for vote in all_votes: bot.remove('User-Proposal-Votes',vote)


        if len(deck_propIDs) >  1:
            text = ""
            if len(message['Content']) > 1: text = '\n'.join(message['Content'].split('\n')[1:])
            for k, filestr in message['Attachments'].items():
                if  '.txt' not in k: continue
                safe_text = "\n\n"
                safe_text += '\n'.join(
                    [m['Content'] for m in await bot.Modules['Discord_Module'].send(bot, "bot-spam", filestr.decode(encoding="utf-8", errors="strict"))]
                )
                text += safe_text
            for k, d in message['Attachments'].items():
                if  '.txt' not in k: text += f"\nAttachment: { message['Attachment Links'][k] }"
            
            num = int(''.join([char for char in message['Content'].split('\n')[0] if char.isdigit()]))
            deck_propIDs = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'On Deck' and df['PID'] == pid and df['Proposal#'] == num)

            if len(deck_propIDs) == 1:
                propID = deck_propIDs[0]
                if not await validateDeckEdit(bot, message, propID, text): return
                bot.set(('Queue-Proposals', propID, 'Body'), text)
                all_votes = where(bot, 'User-Proposal-Votes', lambda df: (df['Proposal-ID'] == propID)) 

                await bot.Modules['Discord_Module'].add_reaction(bot, chan, mid, '✅' )
                for vote in all_votes: bot.remove('User-Proposal-Votes',vote)
            else:
                await bot.Modules['Discord_Module'].return_resp(bot, chan, "Please have the proposal number in the first line of the deck edit so I know which proposal to add it to. The proposal will not include that line.")
            
    
  
async def validateDeckEdit(bot, message, propID, text):
    if not bot.has('Queue-Proposals', propID, 'Arcana'):
        # A normal proposal may become a Tarot Proposal through a deck edit.
        arcana = bot.Modules['Arcana']
        if text.partition(':')[0].strip() not in arcana.arcana and not text.startswith('Amend Rule 302 by setting the following Arcana Effect:'): return True
        try: name, effect = arcana.tarotText(bot, text)
        except ValueError as error:
            await bot.Modules['Discord_Module'].return_resp(bot, message, str(error))
            return False
        bot.set(('Queue-Proposals', propID, 'Arcana'), name)
        bot.set(('Queue-Proposals', propID, 'Arcana Effect'), effect)
        return True
    try:
        name, effect = bot.Modules['Arcana'].tarotText(bot, text)
        if name != bot.get('Queue-Proposals', propID, 'Arcana'):
            raise ValueError('A deck edit must target the same Arcana.')
    except ValueError as error:
        await bot.Modules['Discord_Module'].return_resp(bot, message, str(error))
        return False
    bot.set(('Queue-Proposals', propID, 'Arcana Effect'), effect)
    return True


"""
Update Function Called Every 10 Seconds (Done)
"""
async def update(bot):
    rank_queue(bot)

    for endorsement in bot.keys('User-Proposal-Endorsement'):
        end_prop = bot.get('User-Proposal-Endorsement', endorsement, 'Proposal-ID')
        if type(end_prop) is list:
            bot.remove('User-Proposal-Endorsement', endorsement)

        if not bot.has('Queue-Proposals', end_prop):
            bot.log('remove end', endorsement)
            bot.remove('User-Proposal-Endorsement', endorsement)

    for prop in bot.keys('Queue-Proposals'):
        if bot.get('Queue-Proposals',prop,'Body') in ['.', '', ' ',None]:
            bot.remove('Queue-Proposals',prop)
            bot.log('remove prop', prop)
            
    


"""
Update the QUEUE
"""

lastqupdatetime = time.time()
def rank_queue(bot):
    # Sort aand rank proposals
    ranked = {}
    for source in Queues:
        propIDs= where(bot, 'Queue-Proposals', lambda df: df['Queue'] == source and df['State'] == 'Queue')
        propEnds = [where(bot, 'User-Proposal-Endorsement', lambda df: df['Proposal-ID'] == propID and bot.Modules['Discord_Module'].isActive(bot, df['PID'])) for propID in propIDs]
        propEndsCnt = [len(l) for l in propEnds]
        propDOB = [bot.get('Queue-Proposals', propID, 'DOB') for propID in propIDs]
        propRank = [ float(f"{int(9999999-propEndsCnt[i])}.{int(propDOB[i].timestamp()*1000)}") for i in range(len(propIDs))]

        # Sorted list of player IDs In order of Suporters, then Age
        sorted_queued_props = [x for _, x in sorted(zip(propRank, propIDs))]
        if source == 'tarot':
            sorted_queued_props.sort(key=lambda p: -bot.get('Queue-Proposals', p).get('Tarot Priority', 0))
        for i, propID in enumerate(sorted_queued_props):
            if bot.get('Queue-Proposals', propID, 'Rank') != i: bot.set(('Queue-Proposals', propID, 'Rank'), i)
        ranked[source] = sorted_queued_props
    return ranked
       
async def update_display(bot): 

    # Quese proposal display
    for source in Queues:
        propIDs  = where(bot, 'Queue-Proposals', lambda df: df['Queue'] == source and df['State'] == 'Queue')
        propRank = [bot.get('Queue-Proposals', propID, 'Rank') for propID in propIDs]     
        sort_propIDs = [x for _, x in sorted(zip(propRank, propIDs))][::-1]


        propRank = [bot.get('Queue-Proposals', propID, 'Rank') for propID in sort_propIDs]   
        propBlurb = [bot.get('Queue-Proposals', propID, 'Body') for propID in sort_propIDs]   
        propBlurb = [ i.split('\n')[0][ :min(len(i.split('\n')[0]), 30) ] for i in propBlurb]     
        propEnds = [where(bot, 'User-Proposal-Endorsement', lambda df: df['Proposal-ID'] == propID and bot.Modules['Discord_Module'].isActive(bot, df['PID'])) for propID in sort_propIDs]
        propEndsCnt = [len(l) for l in propEnds]
        propLink = [bot.get('Queue-Proposals', propID, 'Link') for propID in sort_propIDs]   

        msgDicts = []
        for i, propID in enumerate(sort_propIDs):
            msgDicts.append({
                'Content': f"**#{propRank[i] +1}** - { bot.get('Players', bot.get('Queue-Proposals', propID, 'PID'), 'Name') }'s Proposal: (Supporters: {propEndsCnt[i]}) Link:{propLink[i]}```{propBlurb[i]}...```",
                'Files'  : {},
                'Reactions' : ['👍', '👎', 'ℹ️']
            })
            if source == 'tarot': msgDicts[-1]['Content'] += f'\nID: `{propID}`'
        padding = max(0, len(bot.keys('Players')) - len(msgDicts))
        msgDictsEx = [ {'Content':'.'},]*padding + msgDicts
        msgids = await bot.Modules['Discord_Module'].display(bot, queueChanGen(source), msgDictsEx)
        msgids = msgids[padding:]
        for mid, propID in zip(msgids, sort_propIDs):
            if bot.get('Queue-Proposals', propID, 'Endorse-MID') != mid: bot.set(('Queue-Proposals', propID, 'Endorse-MID'), mid)

    chanMade = False
    propIDs  = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'On Deck')
    for propID in propIDs:
        chan = bot.get('Queue-Proposals', propID, 'Channel')
        text = proposalText(bot, propID)
        if not bot.has('Text Channels', chan):
            await bot.Modules['Discord_Module'].create_channel(bot, chan, 'ACTIVE-VOTES', 'On Deck')
            chanMade = True
        else: 
            await bot.Modules['Discord_Module'].set_channel_perms(bot, chan, 'On Deck')
            splitText = bot.Modules['Discord_Module']._splitText(text)
            msgDicts = [{'Content':b} for b in splitText]
            await bot.Modules['Discord_Module'].display(bot, chan, msgDicts)


    propIDs  = where(bot, 'Queue-Proposals', lambda df: df['State'] == 'Voting')
    for propID in propIDs:
        chan = bot.get('Queue-Proposals', propID, 'Channel')
        text = proposalText(bot, propID)
        if not bot.has('Text Channels', chan):
            await bot.Modules['Discord_Module'].create_channel(bot, chan, 'ACTIVE-VOTES' , 'Voting')
            chanMade = True
        else: 
            await bot.Modules['Discord_Module'].set_channel_perms(bot, chan, 'Voting')
            msgDicts = [{'Content':b} for b in bot.Modules['Discord_Module']._splitText(text)]
            await bot.Modules['Discord_Module'].display(bot, chan, msgDicts)
    if chanMade: bot.add_Task( update_display )
