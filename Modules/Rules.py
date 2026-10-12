"""
Main Run Function On Messages
"""
import sys, urllib, discord, io # type: ignore

async def find(bot, payload:dict, *args):
    text = payload['Content'][6:]
    query = text.lower()
    ret_msg = []

    if query[ :1] == '"': query = query[1:  ]
    if query[-1:] == '"': query = query[ :-1]

    if len(query) <= 2: return await bot.Modules['Discord_Module'].send(bot=bot, target=payload['Channel'], content=f"Must Search Words Longer Then 2 Letters", silent=True)  
    else:
        rulecount = 5
        list_of_rules = bot.where(['Rules', '*', "Text"], lambda x: query in x.lower())
        if len(list_of_rules) <= 0: return await bot.Modules['Discord_Module'].send(bot=bot, target=payload['Channel'], content=f"No rules found containing that text", silent=True)  
        for rule_key in list_of_rules:
            rule_key = rule_key[1]
            head = bot.get('Rules', rule_key, "Header")
            body = bot.get('Rules', rule_key, "Text")
            low  = body.lower()

            if rulecount <= 0: break
            else:
                rulecount-=1
                count = 2
                initIndex = 0
                msg = '`'+str(head)+':`\n'
                while count > 0:
                    if query not in low[initIndex:]: break
                    index = low[initIndex:].index(query)
                    index += initIndex

                    initIndex = index + len(query)

                    boundLower = index - 40
                    if boundLower < 0:boundLower = 0

                    boundUpper = index + 120
                    if boundUpper >= len(low): boundUpper = len(low)-1

                    msg +=( ('\t...' if boundLower > 0 else '')\
                            +body[boundLower:index]\
                            +'**'+ body[index:index+len(query)]\
                            +'**'+ body[index+len(query):boundUpper]\
                            +'...').replace('\n','  ')+'\n\n'
                
                    count -= 1
                if count <= 0:
                    msg += '...and more in this rule...'
                ret_msg.append(msg)
    
    
    return await bot.Modules['Discord_Module'].send(bot=bot, target=payload['Channel'], content=ret_msg, silent=True)  

async def rule(bot, payload:dict, *args):
    rulenum = payload['Content'][6:].strip()

    if not rulenum.isdigit() or not bot.has('Rules', int(rulenum)):
        return await bot.Modules['Discord_Module'].send(bot=bot, target=payload['Channel'], content="I couldn't find that rule.", silent=True)
    body = bot.get('Rules', int(rulenum), 'Text')
    bot.log(f"Found Rule {rulenum}")
    body = body.replace('\\xe2\\x95\\x9e', ' ')
    body = body.replace('\\xe2\\x95\\x90', ' ')
    body = body.replace('\\xe2\\x95\\xa1', ' ')
    body = body.replace('\\xe2\\x94\\x80', ' ')
    
    return await bot.Modules['Discord_Module'].send(bot=bot, target=payload['Channel'], content=body, silent=True)  

"""
Setup Log Parameters and Channel List And Whatever You Need to Check on a Bot Reset.
Handles Change In Server Structure and the like. Probably Can Leave Alone.
"""
async def reload_references(bot):
    # Do Stuff Here
    
    rule_found = []
    if bot.has('Rules'):
        for rule in bot.keys('Rules'):
            if rule not in rule_found: bot.remove('Rules', rule)

    with urllib.request.urlopen('https://gitlab.com/nomicgame/nomic-ix/-/raw/master/rules.md?ref_type=heads') as response:
        rules = response.read().decode("utf-8").replace('&nbsp;~','').replace('\r','').replace('\n ','\n').replace('\n\n ','\n')
        ruletxt = rules.split("\n## ")[1:]
        for rule in ruletxt:
            try:
                header = rule.split('\n',1)[0]
                body   = rule.split('\n',1)[1]
                rulenum = header.split(' ')[0]
                
                rule = str(rule) #markdownify.markdownify( rule, heading_style = "ATX", escape_asterisks=False))
                rule_found.append(int(rulenum))
                bot.set(('Rules', int(rulenum)), kwargs={
                    'Header': header, 
                    'Text': body, 
                    'Is Mutable': 'IMMUTABLE' in header
                })
            except Exception as e:
                bot.log('ERROR Importing Rules.', e, rule)
        
async def setup(bot):
    bot.Modules['Commands'].add_command(bot,
            name= 'find',
            description= "search all the rules for specific text",
            callback = find,
            checks = ['isSpam'])
    
    bot.Modules['Commands'].add_command(bot,
            name= 'rule',
            description= "get a rule from it's number",
            callback = rule,
            checks = ['isSpam'])
    
