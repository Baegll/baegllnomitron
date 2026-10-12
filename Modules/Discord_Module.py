
from __future__ import annotations

import sys, os,datetime, random, inspect, numpy, re, asyncio, difflib
from shutil import copyfile
from typing import Any, Dict, List, Optional, Union
import discord

Bot = Any
Payload = Dict[str, Any]
DiscordTarget = Union[int, str, discord.User, discord.Member, discord.TextChannel]


moderatorRole  = "Moderator"
PlayerRole     = "Player"
botRole        = "Nomitron"
InactiveRole   = "Inactive"
JudgeRole      = 'Judge'
JudgeOptInRole = "Judge Opt In"
DefaultRole    = 'Default'

def permissionSet(bot: Bot) -> Dict[str, Dict[Any, discord.PermissionOverwrite]]:
    return {
    'Player Only':{
        bot.get_Ref('Roles',botRole): discord.PermissionOverwrite(send_messages=True),
        bot.get_Ref('Roles',PlayerRole): discord.PermissionOverwrite(send_messages=True),
        bot.get_Ref('Roles',DefaultRole): discord.PermissionOverwrite(send_messages=False),
    },
    'Voting':{              
        bot.get_Ref('Roles',botRole): discord.PermissionOverwrite(read_messages=True,  send_messages=True),                    
        bot.get_Ref('Roles',PlayerRole): discord.PermissionOverwrite(read_messages=True,  send_messages=True),                    
        bot.get_Ref('Roles',DefaultRole): discord.PermissionOverwrite(read_messages=True,  send_messages=False),
    },
    'On Deck':{               
        bot.get_Ref('Roles',botRole): discord.PermissionOverwrite(read_messages=True,  send_messages=True),                    
        bot.get_Ref('Roles',PlayerRole): discord.PermissionOverwrite(read_messages=True,  send_messages=False),                    
        bot.get_Ref('Roles',DefaultRole): discord.PermissionOverwrite(read_messages=True,  send_messages=False),
    },
    'Locked':{
        bot.get_Ref('Roles',botRole): discord.PermissionOverwrite(send_messages=True),
        bot.get_Ref('Roles',PlayerRole): discord.PermissionOverwrite(send_messages=False),
        bot.get_Ref('Roles',DefaultRole): discord.PermissionOverwrite(send_messages=False),
    }
    }

logChan = 'nomitron-log'

file_path  = os.path.realpath(os.path.abspath(inspect.getfile(inspect.currentframe())))
path  = os.path.realpath(os.path.abspath(os.path.join(file_path, os.pardir,)))+'/'


permProfileSet = {}
"""
Get Player From Mention (Updated to Nomitron 6)
"""
def player_from_mention(bot: Bot, PID: Union[int, str]) -> discord.Member:
    if len(str(PID)) == 0: raise Exception("PID is empty")
    else:
        player = user_from_PID(bot, int(re.search(r'\d+', str(PID)).group()))
        if player is not None: return player
        else: 
            raise Exception(f"Cannot find player with mention and id {PID}")

def user_from_PID(bot: Bot, PID: int) -> discord.Member:
    return bot.get_Ref('Players', PID)

def chan_from_Name(bot: Bot, Name: str) -> discord.TextChannel:
    return bot.get_Ref('Text Channels', Name)

def chan_from_ID(bot: Bot, TID: int) -> discord.TextChannel:
    chans = bot.where(('Text Channels', '*'), lambda db: db['TID'] == TID)
    return chan_from_Name(bot, chans[0][1])



"""
Message Functions. (Updated to Nomitron 6)
"""

def _splitText(text: str, lenBlock: int = 1900) -> List[str]:
    blocks = []
    msg = ""
    # while '\n\n' in text: text = text.replace('\n\n', '\n')
    for line in text.split('\n'):
        line += '\n'

        if len(msg + line) < lenBlock: 
            msg += line 
            continue
        elif len(msg) > 0: 
            blocks.append(msg)
            msg = ""
        
        if len(msg + line) < lenBlock: 
            msg += line
            continue
        else:
            while len(line) > lenBlock:
                msgend = line[lenBlock:].find(' ')
                blocks.append(line[:min(lenBlock+msgend, lenBlock+99)])
                line = line[min(lenBlock+msgend, lenBlock+99):]
            msg = str(line)
    if len(msg) > 0: 
        blocks.append(msg)
    return [b.strip() for b in blocks]
 
async def _direct_msg(bot: Bot, pid: Union[int, Any], msg: str, files: Optional[List[Any]] = None, ephemeral: bool = False) -> discord.Message:
    if files is None:
        files = []
    if isinstance(pid, int): player = user_from_PID(bot, pid)
    else:                    player = pid
    
    try:     
        if ephemeral: return await player.send(msg, files=files, delete_after=5*60)
        else: return await player.send(msg, files=files)
    except:  raise Exception(f'Failed to DM', player.name)

async def send(bot: Bot, target: Optional[DiscordTarget], content: str,
               wrap: List[str] = ['', ''], files: Optional[List[Any]] = None,
               ephemeral: bool = False, silent: bool = False) -> Optional[List[Payload]]:
    
    if type(content) in [list, tuple] and len(content) >= 1: 
        msgs = []
        for c in content[:-1]: 
            msgs.append( await send(bot, target, c, wrap=wrap, files=[], ephemeral=ephemeral, silent=silent) )
        msgs.append( await send(bot, target, content[-1], wrap=wrap, files=files, ephemeral=ephemeral, silent=silent) )
        return msgs

    
    if files is None:
        files = []
    if target is None: return
    isDM = isinstance(target, bot.discord.User) or isinstance(target, bot.discord.Member)
    if isinstance(target, int): target = user_from_PID(bot,target)
    if isinstance(target, str): target = chan_from_Name(bot,target)
    blocks = _splitText(content)
    msgs = []
    for block in blocks:
        files_to_send = files if block == blocks[-1] else []
        block = wrap[0] + block + wrap[-1]
        if ephemeral:
            if isDM: m = await _direct_msg(bot, target, block, ephemeral=True, files=files_to_send, silent=silent)
            else:    m = await target.send(block, delete_after=5*60,files=files_to_send, silent=silent)
        else:
            if isDM: m = await _direct_msg(bot, target, block, files=files_to_send, silent=silent) 
            else:    m = await target.send(block, files=files_to_send, silent=silent) 
        msgs.append( await messageDict(bot, m) )
    return msgs

async def return_resp(bot: Bot, interaction: Union[Payload, int, str, Any], text: str,
                      wrap: List[str] = ['', ''], files: Optional[List[Any]] = None,
                      ephemeral: bool = False) -> None:
    if type(interaction) is dict:
        if interaction['Category'] == 'DM':            
            await send( bot, interaction['Author PID'], content=text, wrap=wrap, files=files, ephemeral=ephemeral)
        else:
            await send( bot, interaction['Channel'], content=text, wrap=wrap, files=files, ephemeral=ephemeral)
    elif type(interaction) is int:
            await send( bot, interaction, content=text, wrap=wrap, files=files, ephemeral=ephemeral)
    elif type(interaction) is str:
            await send( bot, interaction, content=text, wrap=wrap, files=files, ephemeral=ephemeral)
    else: 
        await interaction.response.send_message(wrap[0] + text + wrap[-1], files=files, ephemeral=ephemeral)



"""
Convert message data To Easier Message Payload. (Updated to Nomitron 6)
"""   
async def messageDict(bot: Bot, message: discord.Message) -> Payload:
    payload = {}
    payload['MID']    = message.id
    payload['Author'] = message.author.nick if hasattr( message.author, 'nick') and message.author.nick is not None else message.author.name
    payload['Author PID'] = message.author.id
    chanType = message.channel.type
    
    if chanType in [bot.discord.ChannelType.private, bot.discord.ChannelType.group]:
        payload['Channel'] = message.author.id
        payload['Category'] = "DM"
    else:
        payload['Channel']  = message.channel.name
        payload['Category'] = message.channel.category.name if message.channel.category else None

    payload['Content'] = message.system_content.strip().replace('  ',' ')
    if len(payload['Content'] ) == 0: payload['Content'] ='.'
    payload['Attachments'] = {}
    payload['Attachment Links'] = {}
    payload['Reactions'] = {}
    payload['Link'] = message.jump_url

    for react in message.reactions:
        emoji = react.emoji
        emoji = emoji.name if hasattr(emoji, 'name') else str(emoji)
        payload['Reactions'][str(emoji)] = react.count

    for f in message.attachments:  
        payload['Attachments'][f.filename] = await f.read()
        payload['Attachment Links'][f.filename] = f.proxy_url.replace("media.discordapp.net","cdn.discordapp.com")
    

    # bot.log('   MSG--'+ payload['Content']+ '-----')
    return payload

async def reactionDict(bot: Bot, reaction: discord.RawReactionActionEvent, mode: str) -> Payload:
    payload = {}

    user    = user_from_PID(bot, reaction.user_id)
    if reaction.guild_id is None:
        channel = reaction.user_id
    else:
        channel = chan_from_ID(bot, reaction.channel_id)
    if reaction.guild_id is None:  msg = await    user.fetch_message(reaction.message_id)
    else:                          msg = await channel.fetch_message(reaction.message_id)

    # Create Payload
    payload['MSG']     = await messageDict(bot, msg)
    payload['Mode']    = mode
    payload['Reactor PID'] = reaction.user_id
    payload['Reactor'] = user.nick if hasattr( user, 'nick') and user.nick is not None else user.name
    payload['Emoji']   = reaction.emoji.name if hasattr(reaction.emoji, 'name') else str(reaction.emoji)
    return payload

async def roleDict(bot: Bot, role: discord.Role, player: discord.Member, mode: str) -> Payload:
    payload = {
        'PID': player.id,
        'Nick': player.nick,
        'Role': role.name,
        'Color': role.color.value,
        'Mode': mode
    }

    return payload

async def memberDict(bot: Bot, player: discord.Member) -> Payload:
    payload = {
        'PID':player.id,
        'Nick':player.nick,
    }
    return payload

async def typingDict(bot: Bot, payload: discord.RawTypingEvent) -> Payload:
    channel = chan_from_ID(bot, payload.channel_id)
    start   = payload.timestamp
    
    # Create Payload
    typingPayload = {}
    typingPayload['time']    = payload.timestamp
    typingPayload['Channel'] = channel.name if hasattr(channel, 'name') else payload.channel_id
    typingPayload['PID']     = payload.user_id
    typingPayload['Start Time'] = start

    return typingPayload



""" 
All Event Handlers (Updated to Nomitron 5)
"""

async def setup(bot: Bot) -> None:
    await reload_references(bot)

async def on_join(bot: Bot, member: Payload) -> None: pass

async def on_message(bot: Bot, message: Payload) -> None: pass

async def on_reaction(bot: Bot, reaction: Payload) -> None:
    mode = reaction['Mode']
    if mode == 'add' and reaction['Emoji'] == str('🔄') and isModerator(bot, reaction['Reactor PID']): 
        await bot.wrap( 
            remove_reaction, dict(
                bot=bot, 
                dm_pid_or_channel_name = reaction['MSG']['Channel'], 
                msgid = reaction['MSG']['MID'], 
                emoji = reaction['Emoji'], 
                PID = reaction['Reactor PID'])
        )
        await on_message_event(bot, reaction['MSG'])

async def on_role_lost(bot: Bot, role: Payload) -> None:
    if hasRole(bot, role['PID'], role['Role']): bot.stage(('Players', role['PID'], 'Roles'), '.remove', role['Role'])

async def on_role_gain(bot: Bot, role: Payload) -> None:
    if not hasRole(bot, role['PID'], role['Role']): bot.stage(('Players', role['PID'], 'Roles'), 'append', role['Role'])

async def on_typing(bot: Bot, event: Payload) -> None: pass




async def load_slash_commands(bot: Bot, list_of_slash_commands: list) -> None:

    for s in bot.client.guilds:
        if bot.ServerName != s.name: continue
        bot.commandTree.clear_commands( guild = s)

    for cmd in list_of_slash_commands:
        await _registerCommand(bot, cmd)
        
    # Push Commands
    for s in bot.client.guilds:     
        if bot.ServerName != s.name: continue  
        bot.log(f"Loaded Commands:")
        bot.log([i.name for i in await bot.commandTree.fetch_commands()])
        bot.log([i.name for i in bot.commandTree.get_commands()])

        await bot.wrap( bot.commandTree.sync, kwargs=dict(guild=s) ) 
        await bot.wrap( bot.commandTree.sync ) 
        await bot.wrap( bot.commandTree.sync, kwargs=dict(guild=discord.Object(id=s.id)) ) 

async def _registerCommand(bot: Bot, settings: Payload) -> None:
    server = bot.get_Ref('Servers', bot.ServerName)

    command = bot.discord.app_commands.Command(**{k:v for k,v in settings.items() if k != 'checks'} )
    if type(settings.get('checks')) is str:  command.add_check( bot.Modules['Commands'].checks[settings.get('checks')] )
    if type(settings.get('checks')) is list: 
        for check in settings.get('checks'):
            command.add_check( bot.Modules['Commands'].checks[check] )

    bot.commandTree.add_command( command , guild = server )
    bot.Commands[settings['name']] = settings



async def reload_references(bot: Bot) -> None:
    
    for s in bot.client.guilds:
        if bot.ServerName != s.name: continue
        bot.log( '\t Found Server: '+s.name)



        # Create Server Refs
        bot.update_nested_dict(('Servers', s.name), {
            'SID': s.id,
            'Owner PID': s.owner.id
        })
        bot.set_ObjRef('Servers', s.name, s)
        


        # Create member Refs
        for member in s.members:
            bot.update_nested_dict(('Players', member.id), {
                'Name': member.nick if member.nick else member.name,
                'Items':[],
                'Roles':[],
            })
            bot.set(('Players', member.id, 'Roles'), kwargs=[])
            bot.set_ObjRef('Players', member.id, member)
           


        # Create Role Refs
        if bot.has('Roles'):
            for i in bot.keys('Roles'):
                bot.remove_ObjRef('Roles', i)
        
        for role in await s.fetch_roles(): 
            bot.update_nested_dict(('Roles', role.name), {
                    'RID': role.id,
                    'Color': role.color.value,
            })
            bot.set_ObjRef('Roles', role.name, role)


            for member in role.members:
                # if role.name in bot.get('Players', member.id, 'Roles'): continue
                bot.stage(nested_key=('Players', member.id, 'Roles'), method='append', args=[role.name])
        
        ER = s.default_role
        bot.update_nested_dict(('Roles', ER.name), {
                'RID': ER.id,
                'Color': ER.color.value,
        })
        bot.set_ObjRef('Roles', 'Default', ER)



        # Create Channels
        categories = set()
        if bot.has('Text Channels'):
            for i in bot.keys('Text Channels'):
                bot.remove('Text Channels', i, )
                bot.remove_ObjRef('Text Channels', i)
        if bot.has('Channel Catagories'):
            for i in bot.keys('Channel Catagories'):
                bot.remove('Channel Catagories', i, )
                bot.remove_ObjRef('Channel Catagories', i)
        for c in await s.fetch_channels():
            if type(c) == discord.TextChannel: 
                cat = c.category
                categories.add(cat)
                bot.update_nested_dict(('Text Channels', c.name), {
                    'TID':c.id,
                    'Catagory CID':c.category_id,
                })
                bot.set_ObjRef('Text Channels', c.name, c)
            if type(c) == discord.CategoryChannel:
                bot.update_nested_dict(('Channel Catagories', c.name), {
                    'CID': c.id,
                })
                bot.set_ObjRef('Channel Catagories', c.name, c)           




        # Setup Perm Profiles for server
        if bot.has('Permission Sets'):
            for i in bot.keys('Permission Sets'):
                bot.remove_ObjRef('Permission Sets', i)
        for permSet, perms in permissionSet(bot).items():            
            bot.set_ObjRef('Permission Sets', permSet, perms)     







# Discord Event Handlers
async def on_message_event(bot: Bot, payload: Union[Payload, discord.Message]) -> None: # Nomitorn 6
    if type(payload) != dict:         
        if payload.author.id == bot.client.user.id: return
        payload = await messageDict(bot, payload)
        
    if payload['Author PID'] == bot.client.user.id: return

    await send(bot, logChan, f"Player {payload['Author']} MSG in {payload['Channel']} {payload['Content']}",silent=True)
    bot.schedule( 
        method_name = 'passToModule',
        module_name = 'Nomitron',
        Key=['Vars', 'Time'],
        Mode='>=',
        Trigger_Value=bot.now()-bot.sec, 
        kwargs={'function_name':'on_message', 'kwargs':{'message':payload}},
        name = payload['MID'], 
        sequential_only=True,
    )

async def on_raw_reaction_event(bot: Bot, payload: Union[Payload, discord.RawReactionActionEvent], mode: str) -> None: # Nomitorn 6
    if type(payload) != dict: 
        if payload.user_id == bot.client.user.id: return
        payload = await reactionDict(bot, payload, mode)
    if payload['Reactor PID'] == bot.client.user.id: return

    await send(bot, logChan, f"Player {payload['Reactor']} React {mode} : {payload['Emoji'] } on MSG {payload['MSG']['Content']} in {payload['MSG']['Channel']}",silent=True)
    bot.schedule( 
        method_name = 'passToModule',
        module_name = 'Nomitron',
        kwargs={'function_name':'on_reaction', 'kwargs':{'reaction':payload}},
        Key=['Vars', 'Time'],
        Mode='>',
        Trigger_Value=bot.now()-bot.sec, 
        name = f"{bot.now()} React-- {payload['Reactor PID']} {mode} {payload['Emoji']}", 
        sequential_only=True,
    )

async def on_member_update_event(bot: Bot, before: Any, after: discord.Member) -> None: # Nomitorn 6
    bot.log('Role Member Update')
    if bot.get('Servers',bot.ServerName,'SID') != before.guild.id: return
    if before.id == bot.client.user.id: return

    for role in before.roles:
        if role in after.roles: continue
        payload = await roleDict(bot, role=role, player=after, mode='Remove')

        await send(bot, logChan, f'Role {payload["Mode"]} {payload["Nick"]} {payload["Role"]}',silent=True)
        bot.schedule( 
            method_name = 'passToModule',
            module_name = 'Nomitron',
            kwargs={'function_name':'on_role_lost', 'kwargs':{'role':payload}},
            Key=['Vars', 'Time'],
            Mode='>',
            Trigger_Value=bot.now(), 
            name = f'{bot.now()} Role Lost {after.nick} {role.name}--',
            sequential_only=True,
        )

    for role in after.roles:
        if role in before.roles: continue
        payload = await roleDict(bot, role=role, player=after, mode='Add')

        await send(bot, logChan, f'Role {payload["Mode"]} {payload["Nick"]} {payload["Role"]}',silent=True)
        bot.schedule( 
            method_name = 'passToModule',
            module_name = 'Nomitron',
            kwargs={'function_name':'on_role_gain', 'kwargs':{'role':payload}},
            Key=['Vars', 'Time'],
            Mode='>',
            Trigger_Value=bot.now(), 
            name = f'{bot.now()} Role Gain {after.nick} {role.name}--',
            sequential_only=True,
        )

async def on_member_join_event(bot: Bot, member: discord.Member) -> None: # Nomitorn 6
    payload = await memberDict(bot, member)
    
    bot.log(f'   Member Join {member.nick}-------')
    bot.schedule( 
        method_name = 'passToModule',
        module_name = 'Nomitron',
        kwargs={'function_name':'on_join', 'kwargs':{'member':payload}},
        Key=['Vars', 'Time'],
        Mode='>',
        Trigger_Value=bot.now()-bot.sec, 
        name = f'{bot.now()} Member Join {member.nick}-------',
        sequential_only=True,
    )
    
async def on_raw_typing(bot: Bot, payload: discord.RawTypingEvent) -> None: # Nomitorn 6
    if payload.user_id == bot.client.user.id: return
    if bot.get('Servers',bot.ServerName,'SID') != payload.guild_id: return
    if not isPlayer(bot, payload.user_id): return  

    event = await typingDict(bot, payload) 
    # bot.schedule( 
    #     method_name = 'passToModule',
    #     module_name = 'Nomitron',
    #     kwargs={'function_name':'on_typing', 'kwargs':{'event': event}},
    #     Key=['Vars', 'Time'],
    #     Mode='>',
    #     Trigger_Value=bot.now()-bot.sec, 
    #     name = f"Typing Event {bot.now()} {payload.user_id}", 
    #     sequential_only=True,
    # )

async def on_guild_channel_mkrm(bot: Bot, channel: discord.abc.GuildChannel, mode: str) -> None:
    if bot.get('Servers',bot.ServerName,'SID') != channel.guild_id: return
    await reload_references(bot)
    
async def on_guild_channel_edit(bot: Bot, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> None:
    if bot.get('Servers',bot.ServerName,'SID') != before.guild_id: return
    await reload_references(bot)




# Channel and Catagory Methods
async def move_channel_catagory(bot: Bot, text_channel_name: str, catagory_name: str,
                                pos: int = 0) -> None:
    chan     = bot.get_Ref('Text Channels', text_channel_name)
    catagory = bot.get_Ref('Channel Catagories', catagory_name)
    await chan.edit(category= catagory, position = pos)

async def set_channel_perms(bot: Bot, text_channel_name: str, permSetName: str) -> None:
    chan = bot.get_Ref('Text Channels', text_channel_name)

    edit= False
    for r,perm in bot.get_Ref('Permission Sets', permSetName).items():
        if chan.overwrites.get(r) != perm: edit=True
    if edit: await chan.edit(overwrites= bot.get_Ref('Permission Sets', permSetName))

async def create_channel(bot: Bot, text_channel_name: str, catagory_name: str,
                         permSetName: str = 'Player Only') -> None:
    server = bot.get_Ref('Servers', bot.ServerName)
    if bot.has('Text Channels', text_channel_name): return
    bot.log(f'Creating Text Channel {text_channel_name} in {catagory_name} with perms {permSetName}')
    catagory = bot.get_Ref('Channel Catagories', catagory_name)
    perms    = bot.get_Ref('Permission Sets', permSetName)

    c = await server.create_text_channel(name = text_channel_name, overwrites=perms, category= catagory)
    if c is None: return
    bot.update_nested_dict(('Text Channels', c.name), {
                'TID':c.id,
                'Catagory CID':c.category_id,
            })
    bot.set_ObjRef('Text Channels', c.name, c)
    bot.log(' Added Channel:', text_channel_name)
  
async def create_category(bot: Bot, catagory_name: str) -> None:
    server = bot.get_Ref('Servers', bot.ServerName)
    if bot.has('Channel Catagories', catagory_name): return
    cat = await server.create_category_channel(catagory_name)
    if cat is None: return
    bot.update_nested_dict(('Channel Catagories', cat.name), {
            'CID': cat.id,
        })
    bot.set_ObjRef('Channel Catagories', cat.name, cat)
    bot.log(' Added Category:', catagory_name)
  



# Reaction Methods
async def remove_reaction(bot: Bot, dm_pid_or_channel_name: Union[int, str],
                          msgid: int, emoji: str, PID: int) -> None:
    if type(dm_pid_or_channel_name) == str: src = chan_from_Name(bot, dm_pid_or_channel_name)
    else:                      src = user_from_PID(bot, dm_pid_or_channel_name)
    msg = await src.fetch_message(msgid)
    await msg.remove_reaction(emoji, user_from_PID(bot, PID))

async def add_reaction(bot: Bot, dm_pid_or_channel_name: Union[int, str],
                       msgid: int, emoji: str) -> None:
    if type(dm_pid_or_channel_name) == str:
        src = chan_from_Name(bot, dm_pid_or_channel_name)
    else:
        src = await user_from_PID(bot, dm_pid_or_channel_name).create_dm()
    await src.get_partial_message(msgid).add_reaction(emoji)
    


# Role Methods
async def create_role(bot: Bot, roleName: str) -> None:
    server = bot.get_Ref('Servers', bot.ServerName)
    playerRole = bot.get_Ref('Roles', PlayerRole)
    role = await server.create_role(name=roleName,
            permissions =   playerRole.permissions,
            color       =   playerRole.color,
            hoist       =   playerRole.hoist,
            mentionable =   playerRole.mentionable
        )
    if role is None: return
    bot.update_nested_dict(('Roles', role.name), {
                'RID': role.id,
                'Color': role.color.value,
        })
    bot.set_ObjRef('Roles', role.name, role)

async def addRole(bot: Bot, PID: int, RoleName: str) -> Any:
    player = bot.get_Ref('Players', PID)
    role   = bot.get_Ref('Roles', RoleName)
    return await player.add_roles(role)

async def removeRole(bot: Bot, PID: int, RoleName: str) -> Any:
    player = bot.get_Ref('Players', PID)
    role   = bot.get_Ref('Roles', RoleName)
    return await player.remove_roles(role)
 
def hasRole(bot: Bot, PID: int, RoleName: str) -> bool:
    return RoleName in bot.get('Players', PID, 'Roles')

def isActive(bot: Bot, PID: int) -> bool:
    return not hasRole(bot, PID, InactiveRole)

def isPlayer(bot: Bot, PID: int) -> bool:
    return hasRole(bot, PID, PlayerRole)

def isJudge(bot: Bot, PID: int) -> bool:
    return hasRole(bot, PID, JudgeRole)

def isModerator(bot: Bot, PID: int) -> bool:
    return hasRole(bot, PID, moderatorRole)

def usersWithRole(bot: Bot, roleName: str) -> List[int]:
    if not bot.has('Players'):
        return []
    return [pid for pid in bot.keys('Players') if hasRole(bot, pid, roleName)]





async def getBotMsgs(bot: Bot, channel_name: str) -> List[discord.Message]:
    chanObj = chan_from_Name(bot, channel_name)
    bot_user_id = bot.client.user.id
    bot_messages = []

    # Fetch message history in the channel
    async for message in chanObj.history(limit=150):
        if message.author.id == bot_user_id:
            bot_messages.append(message)
    return bot_messages[::-1]

async def display(bot: Bot, channel_name: str, list_of_msgDict: List[Payload]) -> List[int]:
    if not bot.has('Text Channels', channel_name): 
        await create_channel(bot, channel_name, 'BUSINESS', 'Locked')
        bot.add_Task( display, dict(channel_name=channel_name, list_of_msgDict=list_of_msgDict))
        return
    
    msgs = await getBotMsgs(bot, channel_name)
    chanObj = chan_from_Name(bot, channel_name)
    if len(msgs) < len(list_of_msgDict): 
        await chanObj.purge(limit = 150, check = lambda m: m.author.id == bot.client.user.id)
        msgs = [await chanObj.send('.', silent=True) for i in range(len(list_of_msgDict) + 10)]
    
    list_of_msgDict_exp = list(list_of_msgDict)
    for i in range(len(msgs) - len(list_of_msgDict)):
        list_of_msgDict_exp = [{
            'Content':'.',
            'Attachments':{},
            'Reactions':[],
        },] + list_of_msgDict_exp
    
    msgids = [m.id for m in msgs]        

    for msg, msgSet in zip(msgs, list_of_msgDict_exp):
        msgSet['Content'] = msgSet['Content'].replace('* *','**').strip()


        msgDict = await messageDict(bot, msg)
        edit = False
        if msgDict['Content'] != msgSet['Content']: edit = True
        if 'Attachments' in msgSet:
            for filename in msgSet['Attachments'].keys():
                if filename not in msgDict['Attachments'].keys(): edit = True
        if edit: 
            bot.log('edit'+ msgSet['Content'][:min(100, len( msgSet['Content'] ))])
            await msg.edit(content = msgSet['Content'], attachments = list(msgSet.get('Attachments', {}).values()))

        for emoji in msgSet.get('Reactions',[]):
            if emoji not in msgDict.get('Reactions',{}).keys():
                await msg.add_reaction(emoji)
        for emoji in msgDict.get('Reactions',{}).keys():
            if emoji not in msgSet.get('Reactions',[]):
                await msg.clear_reaction(emoji)
    if len(list_of_msgDict) == 0: return []
    return msgids[-len(list_of_msgDict):]
