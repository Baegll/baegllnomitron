import ast
import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import test_arcana as harness
from Modules import Arcana, CardGame, ItemsAndTeams, Voting


class CardGameTests(unittest.IsolatedAsyncioTestCase):
    commit = harness.ArcanaTests.commit
    payload = harness.ArcanaTests.payload
    proposal = harness.ArcanaTests.proposal
    allCards = harness.ArcanaTests.allCards

    def clearCards(self):
        Arcana.saveOutside(self.bot, [])
        self.commit()

    async def asyncSetUp(self):
        await harness.ArcanaTests.asyncSetUp(self)
        self.bot.Modules['CardGame'] = CardGame
        self.bot.Modules['Discord_Module'].isModerator = lambda b, p: p == 3
        await ItemsAndTeams.setup(self.bot)
        self.commit()
        await CardGame.initialize(self.bot)
        self.commit()
        await ItemsAndTeams.update(self.bot)
        self.commit()

    async def card(self, name, owner=1, zone='Private Hand', **properties):
        card = await Arcana.newCard(self.bot, name, owner, zone)
        card.update(properties)
        if zone == 'Global' or owner is None: self.bot.Data['Cards']['Outside'].append(card)
        elif isinstance(owner, int): self.bot.Data['Players'][owner].setdefault('Hand', []).append(card)
        else: self.bot.Data[owner[0]][owner[1]].setdefault('Hand', []).append(card)
        return card

    async def runCommand(self, text, pid=1):
        response = self.bot.Modules['Discord_Module'].return_resp
        response.reset_mock()
        await CardGame.command(self.bot, self.payload(text, pid))
        self.commit()
        return response.call_args.args[2] if response.call_args else ''

    def byId(self, card):
        stored = self.bot.Data['Cards']['Outside'] + [c for table in ['Players', 'Teams'] for entity in self.bot.Data.get(table, {}).values() for c in entity.get('Hand', [])]
        return next((c for c in stored if c['ID'] == card['ID']), None)

    def hp(self, pid): return self.bot.Data['Players'][pid]['Intrinsic']['HP']

    def history(self, voter=1):
        self.bot.Data['Card Game']['History'] = [{'Number': n, 'Voters': [voter]} for n in range(301, 306)]

    async def test_equip_capacity_move_limit_and_private_visibility(self):
        cards = [await self.card('Uno Reverse') for _ in range(4)]
        for card in cards[:3]: await self.runCommand('!card equip ' + card['ID'])
        self.assertIn('capacity', await self.runCommand('!card equip ' + cards[3]['ID']))
        self.assertFalse(Arcana.visible(self.bot, self.byId(cards[0]), 2))
        self.assertIn('already moved', await self.runCommand('!card unequip ' + cards[0]['ID']))
        self.bot.Data['Vars']['Turn'] += 1
        await self.runCommand('!card unequip ' + cards[0]['ID'])
        self.assertEqual(self.byId(cards[0])['Zone'], 'Private Hand')
        self.assertIn('already moved', await self.runCommand('!card equip ' + cards[0]['ID']))

    async def test_equip_permissions_staff_inactive_and_upgraded_capacity(self):
        staff = await self.card('Staff of Nin')
        self.assertIn('permit equipping', await self.runCommand('!card equip ' + staff['ID']))
        self.assertIn('inactive outside play', await self.runCommand('!card use ' + staff['ID']))
        self.bot.Data['Cards']['Definitions']['Uno Reverse']['Potency'] = 2
        uno = await self.card('Uno Reverse')
        second = await self.card('Uno Reverse')
        await self.runCommand('!card equip ' + uno['ID'])
        self.assertIn('capacity', await self.runCommand('!card equip ' + second['ID']))
        self.bot.Data['Players'][1]['Intrinsic']['DeckCapacity'] = 4
        await self.runCommand('!card equip ' + second['ID'])
        self.assertEqual(self.byId(second)['Zone'], 'Personal Deck')

    async def test_summon_cost_floor_and_paying_life_from_owned_summon(self):
        stoat = await self.card('Stoat')
        self.bot.Data['Players'][1]['Intrinsic']['HP'] = 1
        self.assertIn('cannot pay', await self.runCommand('!card summon ' + stoat['ID']))
        rock = await self.card('Ordinary Rock', zone='Play Area')
        await self.runCommand(f'!card summon {stoat["ID"]} {rock["ID"]}')
        self.assertEqual(self.byId(rock)['Life'], 4)
        self.assertEqual(self.byId(stoat)['Zone'], 'Play Area')
        self.assertEqual(self.hp(1), 1)
        self.assertIn('cannot be traded', await self.runCommand('!card give ' + stoat['ID'] + ' 2'))

    async def test_summon_from_self_and_consumption_of_last_summon_life(self):
        stoat = await self.card('Stoat')
        await self.runCommand('!card summon ' + stoat['ID'])
        self.assertEqual(self.hp(1), 99)
        rock = await self.card('Ordinary Rock')
        self.bot.Data['Cards']['Definitions']['Ordinary Rock']['Cost'] = 1
        self.byId(stoat)['Life'] = 1
        await self.runCommand(f'!card summon {rock["ID"]} {stoat["ID"]}')
        self.assertIsNone(self.byId(stoat))
        self.assertEqual(self.byId(rock)['Zone'], 'Play Area')

    async def test_trade_ownership_and_in_play_exclusions(self):
        card = await self.card('Uno Reverse', zone='Personal Deck')
        self.assertIn('cannot be traded', await self.runCommand('!card give ' + card['ID'] + ' 2'))
        self.byId(card)['Zone'] = 'Private Hand'
        self.assertIn('not your card', await self.runCommand('!card give ' + card['ID'] + ' 1', pid=2))
        await self.runCommand('!card give ' + card['ID'] + ' 2')
        self.assertEqual(self.byId(card)['Owner'], 2)
        self.assertFalse(self.bot.Data['Players'][1]['Hand'])
        self.assertEqual(self.bot.Data['Players'][2]['Hand'][0]['ID'], card['ID'])
        self.assertFalse(self.bot.Data['Cards']['Outside'])

    async def test_exploding_kitten_automatic_damage_floor_and_return(self):
        self.bot.Data['Players'][1]['Intrinsic']['HP'] = 15
        pot = await self.card('Pot of Greed')
        with patch.object(Arcana, 'choose', return_value='Exploding Kitten'):
            await self.runCommand('!card use ' + pot['ID'])
        self.assertEqual(self.hp(1), 1)
        self.assertFalse(self.allCards())
        self.assertEqual(Arcana.weight(self.bot.Data['Cards'], 'Exploding Kitten'), 1)

    async def test_kitten_turn_card_has_no_damage_until_handoff(self):
        with patch.object(Arcana, 'choose', return_value='Exploding Kitten'):
            await Arcana.onTurnStart(self.bot)
        self.commit()
        self.assertEqual([self.hp(p) for p in [1, 2]], [100, 100])
        with patch.object(Arcana.random, 'choice', return_value=1):
            await Arcana.onTurnEnd(self.bot)
        self.commit()
        self.assertEqual(self.hp(1), 90)
        self.assertFalse(self.allCards())

    async def test_multiple_external_kitten_draws_accumulate_deferred_hp(self):
        cards = self.bot.get('Cards')
        await Arcana.draw(self.bot, cards, 1, name='Exploding Kitten')
        await Arcana.draw(self.bot, cards, 1, name='Exploding Kitten')
        self.commit()
        self.assertEqual(self.hp(1), 80)
        self.assertFalse(cards['Outside'])

    async def test_curse_blocks_all_draw_paths_and_evidence_is_moderated(self):
        apple = await self.card('The Cursed Apple')
        await self.runCommand('!card use ' + apple['ID'] + ' 2')
        self.assertIsNone(self.byId(apple))
        self.assertFalse(Arcana.canDraw(self.bot, 2))
        await Arcana.crystalDraw(self.bot, self.payload(pid=2))
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 2), 4)
        await self.runCommand('!card-admin curse-result 2 failure', pid=3)
        self.assertIn('following turn', await self.runCommand('!card-admin curse-result 2 success 1', pid=3))
        self.bot.Data['Vars']['Turn'] += 1
        await self.runCommand('!card-admin curse-result 2 success 1', pid=3)
        self.assertTrue(Arcana.canDraw(self.bot, 2))
        self.assertEqual(len(self.allCards()), 1)

    async def test_curse_deadlock_and_third_party_requirement(self):
        self.bot.Data['Card Game']['Curses'][2] = ['curse']
        self.assertIn('different player', await self.runCommand('!card-admin curse-result 2 success 2', pid=3))
        await self.runCommand('!card-admin curse-result 2 deadlock', pid=3)
        self.assertTrue(Arcana.canDraw(self.bot, 2))

    async def test_high_standing_month_boundary_empty_hand_and_explicit_abstain(self):
        self.history()
        with patch.object(Arcana, 'choose', return_value='Two of Cups'):
            self.assertIn('claimed', await self.runCommand('!card fund'))
            self.clearCards()
            self.assertIn('this month', await self.runCommand('!card fund'))
            self.bot.Data['Vars']['Time'] = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)
            self.assertIn('claimed', await self.runCommand('!card fund'))
        self.clearCards()
        self.proposal('voting', state='Voting', number=306)
        self.assertIn('High Standing', await self.runCommand('!card fund', pid=2))
        self.bot.Data['User-Proposal-Votes']['v'] = {'PID-Voter': 2, 'Proposal-ID': 'voting', 'Vote': 'Abstain'}
        self.bot.Data['Card Game']['History'] = [{'Number': n, 'Voters': [2]} for n in range(301, 306)]
        self.assertIn('claimed', await self.runCommand('!card fund', pid=2))

    async def test_fund_rejects_in_play_hand_and_curse_without_consuming_claim(self):
        self.history()
        uno = await self.card('Uno Reverse', zone='Personal Deck')
        self.assertIn('empty', await self.runCommand('!card fund'))
        self.clearCards()
        self.bot.Data['Card Game']['Curses'][1] = ['curse']
        self.assertIn('cannot draw', await self.runCommand('!card fund'))
        self.assertNotIn(1, self.bot.Data['Card Game']['Fund Claims'])

    async def test_random_spell_mana_cost_and_all_six_results(self):
        for outcome in range(1, 7):
            with self.subTest(outcome=outcome):
                self.bot.Data['Card Game']['Random Rolls'].clear()
                self.bot.Data['Card Game']['Toads'].clear()
                self.bot.Data['Players'][2]['Intrinsic'].update({'HP': 100, 'Luck': 3})
                randomCard = await self.card('Random')
                await self.card('Two of Cups', owner=2)
                inplay = await self.card('Uno Reverse', owner=2, zone='Personal Deck')
                await self.runCommand('!card use ' + randomCard['ID'] + ' 2')
                self.assertTrue(CardGame.blockedAction(self.bot, 2))
                with patch.object(CardGame.random, 'randint', return_value=outcome):
                    self.assertIn(f'1d6 = {outcome}', await self.runCommand('!card random', pid=2))
                self.assertFalse(CardGame.blockedAction(self.bot, 2))
                self.assertIsNotNone(self.byId(inplay))
                if outcome == 1:
                    self.assertFalse(CardGame.canGainCards(self.bot, 2))
                    self.bot.Data['Vars']['Turn'] += 3
                    self.assertTrue(CardGame.canGainCards(self.bot, 2))
                if outcome == 2: self.assertEqual(self.bot.Data['Players'][2]['Intrinsic']['Luck'], 0)
                if outcome == 3: self.assertTrue(all(c['Zone'] in CardGame.inPlay for c in self.allCards() if c['Owner'] == 2))
                if outcome == 4: self.assertEqual(self.hp(2), 90)
                if outcome == 5: self.assertEqual(self.hp(2), 120)
                if outcome == 6: self.assertEqual(self.bot.Data['Players'][2]['Intrinsic']['Luck'], 5)
        self.bot.Data['Resources']['Intrinsic'].append('Mana')
        randomCard = await self.card('Random')
        self.assertIn('cannot pay', await self.runCommand('!card use ' + randomCard['ID'] + ' 2'))
        self.assertIsNotNone(self.byId(randomCard))

    async def test_random_blocks_commands_and_vote_messages_and_reactions(self):
        self.bot.Data['Card Game']['Random Rolls'][1] = 'pending'
        self.proposal('vote', state='Voting', number=312)
        self.bot.Data['Queue-Proposals']['vote']['Channel'] = 'proposal-312'
        msg = self.payload('yay') | {'Channel': 'proposal-312', 'Category': 'ACTIVE-VOTES', 'MID': 123}
        await Voting.on_message(self.bot, msg)
        await Voting.on_reaction(self.bot, {'MSG': {'Channel': 'proposal-312', 'MID': 123}, 'Reactor PID': 1, 'Mode': 'add'})
        self.commit()
        self.assertFalse(self.bot.Data['User-Proposal-Votes'])
        source = ast.parse((harness.root / 'Modules/Commands.py').read_text(encoding='utf-8'))
        handler = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'on_message')
        namespace = {}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'Modules/Commands.py', 'exec'), namespace)
        await namespace['on_message'](self.bot, self.payload('!card fund'))
        self.assertIn('Random', self.bot.Modules['Discord_Module'].return_resp.call_args.args[2])

    async def test_toad_drops_pickup_limits_and_nomitron_receives_unclaimed(self):
        self.bot.Data['Resources']['Tradeable'] = ['Stone']
        self.bot.Data['Players'][1]['Pockets'] = {'Stone': 2}
        loose = await self.card('Two of Cups')
        equipped = await self.card('Uno Reverse', zone='Personal Deck')
        self.bot.Data['Card Game']['Random Rolls'][1] = 'pending'
        with patch.object(CardGame.random, 'randint', return_value=1): await self.runCommand('!card random')
        self.assertIsNone(self.byId(loose)['Owner'])
        self.assertEqual(self.byId(equipped)['Owner'], 1)
        self.assertFalse(CardGame.tradeableGainAllowed(self.bot, 1, 'Stone'))
        drop = self.bot.Data['Card Game']['Drops'][0]
        await self.runCommand(f'!card pickup {drop["ID"]} Stone 1', pid=2)
        self.assertEqual(self.bot.Data['Players'][2]['Pockets']['Stone'], 1)
        self.bot.Data['Vars']['Turn'] += 1
        await CardGame.onTurnEnd(self.bot)
        self.commit()
        self.assertEqual(self.byId(loose)['Owner'], 'Nomitron')
        self.assertEqual(self.bot.Data['Card Game']['Drops'][0]['Owner'], 'Nomitron')

    async def test_elevens_draw_ten_or_freeze_and_choose_exactly_four(self):
        eleven = [await self.card(name) for name in CardGame.elevens]
        with patch.object(Arcana, 'choose', return_value='Two of Cups'):
            await self.runCommand('!card use ' + eleven[0]['ID'] + ' draw')
        self.assertEqual(len(self.allCards()), 10)
        self.clearCards()
        eleven = [await self.card(name) for name in CardGame.elevens]
        victims = [await self.card('Two of Cups', owner=2) for _ in range(5)]
        protected = await self.card('Uno Reverse', owner=2, zone='Personal Deck')
        await self.runCommand('!card use ' + eleven[0]['ID'] + ' steal 2')
        request = self.bot.Data['Card Game']['Steals'][0]
        self.assertFalse(Arcana.canDraw(self.bot, 2))
        self.assertIn('frozen', await self.runCommand('!card give ' + victims[0]['ID'] + ' 1', pid=2))
        self.assertNotIn(protected['ID'], request['Eligible'])
        self.assertIn('exactly', await self.runCommand('!card respond ' + request['ID'] + ' ' + victims[0]['ID'], pid=2))
        await self.runCommand('!card respond ' + request['ID'] + ' ' + ' '.join(c['ID'] for c in victims[:4]), pid=2)
        self.assertFalse(self.bot.Data['Card Game']['Steals'])
        self.assertEqual(sum(c['Owner'] == 1 for c in self.allCards()), 4)
        self.assertEqual(self.byId(protected)['Owner'], 2)

    async def test_elevens_timeout_handles_team_fewer_than_four_and_exact_deadline(self):
        self.bot.Data['Teams'] = {'Tea': {'Members': [2]}}
        eleven = [await self.card(name) for name in CardGame.elevens]
        victims = [await self.card('Two of Cups', owner=['Teams', 'Tea']) for _ in range(2)]
        await self.runCommand('!card use ' + eleven[0]['ID'] + ' steal team:Tea')
        request = self.bot.Data['Card Game']['Steals'][0]
        self.assertEqual(request['Count'], 2)
        self.bot.Data['Vars']['Time'] += self.bot.day
        self.assertIn('deadline', await self.runCommand('!card respond ' + request['ID'] + ' ' + ' '.join(c['ID'] for c in victims), pid=2))
        await CardGame.update(self.bot)
        self.commit()
        self.assertFalse(self.bot.Data['Card Game']['Steals'])
        self.assertTrue(all(self.byId(card)['Owner'] == 1 for card in victims))

    async def test_shiny_rock_forced_visible_trade_and_lucky_conversion(self):
        shiny = await self.card('Shiny Rock')
        hidden = await self.card('Two of Cups', owner=2)
        self.assertIn('visible hand', await self.runCommand(f'!card use {shiny["ID"]} {hidden["ID"]}'))
        target = await self.card('Stoat', owner=2, zone='Play Area')
        with patch.object(CardGame.random, 'choice', return_value='Lucky Rock'):
            await self.runCommand(f'!card use {shiny["ID"]} {target["ID"]}')
        self.assertEqual(self.byId(target)['Owner'], 1)
        self.assertEqual(self.byId(shiny)['Name'], 'Lucky Rock')
        await self.runCommand('!card use ' + shiny['ID'], pid=2)
        self.assertIsNone(self.byId(shiny))
        self.assertEqual(self.bot.Data['Players'][2]['Intrinsic']['Luck'], 2)
        self.assertEqual(Arcana.weight(self.bot.Data['Cards'], 'Shiny Rock'), 1)

    async def test_uno_requires_equipping_same_turn_and_moderator_veto_restores_it(self):
        apple = await self.card('The Cursed Apple')
        uno = await self.card('Uno Reverse', owner=2)
        await self.runCommand('!card use ' + apple['ID'] + ' 2')
        effect = self.bot.Data['Card Game']['Effects'][0]
        self.assertIn('equipped', await self.runCommand(f'!card reverse {uno["ID"]} {effect["ID"]}', pid=2))
        await self.runCommand('!card equip ' + uno['ID'], pid=2)
        self.assertIn('Moderator', await self.runCommand(f'!card reverse {uno["ID"]} {effect["ID"]}', pid=2))
        self.assertIsNone(self.byId(uno))
        await self.runCommand('!card-admin ruling ' + effect['ID'] + ' veto', pid=3)
        self.assertEqual(self.byId(uno)['Zone'], 'Personal Deck')
        self.assertEqual(self.bot.Data['Card Game']['Effects'][0]['Status'], 'Vetoed')

    async def test_attack_protection_overflow_life_destruction_and_once_per_turn(self):
        attacker = await self.card('Stoat', zone='Play Area')
        defender = await self.card('Ordinary Rock', owner=2, zone='Play Area')
        self.bot.Data['Cards']['Definitions']['Stoat']['Attack'] = 7
        self.assertIn('protect', await self.runCommand('!card attack ' + attacker['ID'] + ' player:2'))
        await self.runCommand(f'!card attack {attacker["ID"]} {defender["ID"]} player:2')
        self.assertIsNone(self.byId(defender))
        self.assertEqual(self.hp(2), 98)
        self.assertIn('already attacked', await self.runCommand('!card attack ' + attacker['ID'] + ' player:2'))

    async def test_temporary_destruction_prevents_redraw(self):
        self.bot.Data['Cards']['Definitions']['Stoat']['Keywords'].append('Temporary')
        stoat = await self.card('Stoat', zone='Play Area')
        attacker = await self.card('Ordinary Rock', owner=2, zone='Play Area')
        self.bot.Data['Cards']['Definitions']['Ordinary Rock']['Attack'] = 3
        await self.runCommand(f'!card attack {attacker["ID"]} {stoat["ID"]}', pid=2)
        self.assertIsNone(self.byId(stoat))
        self.assertEqual(Arcana.weight(self.bot.Data['Cards'], 'Stoat'), 0)

    async def test_stoat_sticker_lottery_only_uses_applicable_nonduplicate_unique_stickers(self):
        self.bot.Data['Cards']['Stickers'] = {'valid': {'Cards': ['Stoat'], 'Unique': True}, 'wrong': {'Cards': ['Uno Reverse']}}
        with patch.object(CardGame.random, 'random', return_value=0.005):
            first = await self.card('Stoat')
            second = await self.card('Stoat')
        self.assertEqual(first['Stickers'], ['valid'])
        self.assertNotIn('Stickers', second)

    async def test_passing_309_creates_parallel_amendment_once_and_records_history(self):
        jobs = []
        self.bot.add_Task = lambda callback, kwargs: jobs.append((callback, kwargs))
        self.proposal('309', queue='main', state='Voting', number=309)
        self.bot.Data['Queue-Proposals']['309']['Body'] = 'Rules Card\n---\n' + CardGame.amendment304
        self.bot.Data['User-Proposal-Votes']['v'] = {'PID-Voter': 2, 'Proposal-ID': '309', 'Vote': 'Abstain'}
        self.bot.Data['User-Proposal-Votes']['yes'] = {'PID-Voter': 1, 'Proposal-ID': '309', 'Vote': 'Yay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Card Game']['History'], [{'Number': 309, 'Voters': [1, 2]}])
        for callback, kwargs in jobs: await callback(self.bot, **kwargs)
        self.commit()
        proposal = self.bot.Data['Queue-Proposals']['proposal-309-instant']
        self.assertEqual((proposal['Queue'], proposal['State']), ('parallel', 'On Deck'))
        self.assertEqual(proposal['Body'], CardGame.amendment304)
        self.assertTrue(self.bot.Data['Card Game']['Started 309'])
        nextNumber = self.bot.Data['Vars']['Next Proposal Number']
        await CardGame.start309(self.bot, 1)
        self.commit()
        self.assertEqual(self.bot.Data['Vars']['Next Proposal Number'], nextNumber)

    async def test_instant_effect_split_keeps_rule_text_and_generic_effect_requires_adjudication(self):
        self.assertEqual(CardGame.instantParts('before\n---\nDo it once.\n---\nafter'), ('before\n\nafter', 'Do it once.'))
        self.proposal('p', queue='main', state='Voting', number=314)
        self.bot.Data['Queue-Proposals']['p']['Body'] = 'Rule text\n---\nGain a thing.'
        self.bot.Data['User-Proposal-Votes']['yes'] = {'PID-Voter': 1, 'Proposal-ID': 'p', 'Vote': 'Yay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertIn('immediate moderator adjudication', self.bot.Modules['Discord_Module'].send.call_args.args[2])

    async def test_hp_mod_set_cannot_break_floor_and_card_commands_validate_arguments(self):
        with patch.object(ItemsAndTeams, 'pidFrom', return_value=1):
            await ItemsAndTeams.setAmount(self.bot, self.payload('!set-amount 1 0 HP'))
        self.commit()
        self.assertEqual(self.hp(1), 100)
        self.assertIn('Missing arguments', await self.runCommand('!card use'))
        self.assertIn('Unclosed quote', await self.runCommand('!card use "'))
        self.assertIn('Unknown card', await self.runCommand('!card equip missing'))

    async def test_kitten_entity_without_hp_requests_adjudication_and_returns(self):
        self.bot.Data['Teams'] = {'Tea': {'Members': [1, 2]}}
        cards = self.bot.get('Cards')
        await Arcana.draw(self.bot, cards, ['Teams', 'Tea'], name='Exploding Kitten')
        self.assertFalse(cards['Outside'])
        self.assertIn('Judge', self.bot.Modules['Discord_Module'].send.await_args_list[-2].args[2])
        self.assertEqual(self.hp(1), 100)

    async def test_uno_ruling_acknowledges_manual_swap_and_cannot_reverse_old_turn(self):
        uno = await self.card('Uno Reverse', owner=2, zone='Personal Deck')
        apple = await self.card('The Cursed Apple')
        await self.runCommand('!card use ' + apple['ID'] + ' 2')
        effect = self.bot.Data['Card Game']['Effects'][0]
        await self.runCommand(f'!card reverse {uno["ID"]} {effect["ID"]}', pid=2)
        await self.runCommand('!card-admin ruling ' + effect['ID'] + ' resolved', pid=3)
        result = self.bot.Data['Card Game']['Effects'][0]
        self.assertEqual((result['Owner'], result['Target']), (2, 1))
        self.assertEqual(result['Status'], 'Reversed (moderator applied)')
        self.bot.Data['Vars']['Turn'] += 1
        another = await self.card('Uno Reverse', owner=2, zone='Personal Deck')
        self.assertIn('this turn', await self.runCommand(f'!card reverse {another["ID"]} {effect["ID"]}', pid=2))

    async def test_dropped_card_first_pickup_and_intrinsic_drop_pickup(self):
        card = await self.card('Two of Cups', owner=None, zone='Global', **{'Dropped Turn': self.bot.Data['Vars']['Turn']})
        await self.runCommand('!card pickup ' + card['ID'], pid=2)
        self.assertEqual(self.byId(card)['Owner'], 2)
        self.assertIn('not an unclaimed', await self.runCommand('!card pickup ' + card['ID']))
        self.bot.Data['Card Game']['Drops'].append({'ID': 'drop', 'Turn': 4, 'Owner': None, 'Items': {}, 'Intrinsic': {'Luck': 2}})
        await self.runCommand('!card pickup drop Luck 2', pid=2)
        self.assertEqual(self.bot.Data['Players'][2]['Intrinsic']['Luck'], 3)

    async def test_unresolvable_eleven_timeout_announces_adjudication_once(self):
        victim = await self.card('Two of Cups', owner=2)
        self.bot.Data['Card Game']['Steals'] = [{'ID': 'req', 'Owner': 1, 'Target': 2, 'Eligible': [victim['ID']], 'Count': 1, 'Deadline': self.bot.Data['Vars']['Time']}]
        # Ownership comes from the containing hand, not a parallel owner field.
        self.bot.Data['Players'][2]['Hand'].remove(victim)
        self.bot.Data['Players'][3]['Hand'].append(victim)
        await CardGame.update(self.bot)
        self.commit()
        count = self.bot.Modules['Discord_Module'].send.await_count
        await CardGame.update(self.bot)
        self.commit()
        self.assertEqual(self.bot.Modules['Discord_Module'].send.await_count, count)
        self.assertIn('Adjudication', self.bot.Data['Card Game']['Steals'][0])

    async def test_invalid_overflow_is_atomic_and_unknown_inputs_do_not_spend_cards(self):
        attacker = await self.card('Stoat', zone='Play Area')
        target = await self.card('Ordinary Rock', owner=2, zone='Play Area', Life=1)
        self.bot.Data['Cards']['Definitions']['Stoat']['Attack'] = 3
        self.assertIn('that entity', await self.runCommand(f'!card attack {attacker["ID"]} {target["ID"]} player:3'))
        self.assertEqual(self.byId(target)['Life'], 1)
        self.assertNotIn('Attack Turn', self.byId(attacker))
        self.assertIn('player ID', await self.runCommand('!card give ' + attacker['ID'] + ' nobody'))
        self.assertIn('Card actions', await self.runCommand('!card invalid'))

    async def test_empty_eleven_target_does_not_freeze_and_random_pays_defined_mana(self):
        eleven = [await self.card(name) for name in CardGame.elevens]
        self.assertIn('no hand freeze', await self.runCommand('!card use ' + eleven[0]['ID'] + ' steal 2'))
        self.assertFalse(self.bot.Data['Card Game']['Steals'])
        self.bot.Data['Resources']['Intrinsic'].append('mana')
        self.bot.Data['Players'][1]['Intrinsic']['mana'] = 1
        spell = await self.card('Random')
        await self.runCommand('!card use ' + spell['ID'] + ' 2')
        self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['mana'], 0)
        self.assertTrue(CardGame.blockedAction(self.bot, 2))

    async def test_team_owned_card_effects_keep_cards_with_the_entity_not_the_actor(self):
        self.bot.Data['Teams'] = {'Tea': {'Members': [1]}}
        pot = await self.card('Pot of Greed', owner=['Teams', 'Tea'])
        with patch.object(Arcana, 'choose', return_value='Two of Cups'):
            await self.runCommand('!card use ' + pot['ID'])
        self.assertTrue(all(c['Owner'] == ['Teams', 'Tea'] for c in self.allCards()))
        self.assertEqual(len(self.allCards()), 2)

    async def test_eleven_card_freeze_does_not_block_noncard_resource_pickups(self):
        self.bot.Data['Resources']['Tradeable'] = ['Stone']
        self.bot.Data['Card Game']['Steals'] = [{'Target': 1}]
        self.bot.Data['Card Game']['Drops'] = [{'ID': 'drop', 'Owner': None, 'Items': {'Stone': 1}, 'Intrinsic': {}}]
        self.assertFalse(CardGame.canGainCards(self.bot, 1))
        await self.runCommand('!card pickup drop Stone 1')
        self.assertEqual(self.bot.Data['Players'][1]['Pockets']['Stone'], 1)

    async def test_restart_preserves_player_hand_and_intrinsic_upgrade(self):
        personal = await self.card('Uno Reverse', zone='Personal Deck')
        self.bot.Data['Players'][1]['Intrinsic']['DeckCapacity'] = 7
        await Arcana.setup(self.bot)
        await CardGame.initialize(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Players'][1]['Hand'], [personal])
        self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['DeckCapacity'], 7)
        self.assertEqual(Arcana.weight(Arcana.getCards(self.bot), 'Uno Reverse'), 0.5)

    async def test_deck_capacity_uses_existing_intrinsic_amount_commands(self):
        with patch.object(ItemsAndTeams, 'pidFrom', return_value=1):
            await ItemsAndTeams.setAmount(self.bot, self.payload('!set-amount 1 5 DeckCapacity'))
            self.commit()
            self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['DeckCapacity'], 5)
            await ItemsAndTeams.setAmount(self.bot, self.payload('!set-amount 1 -1 DeckCapacity'))
            self.commit()
            self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['DeckCapacity'], 5)
        self.assertIn('DeckCapacity', self.bot.Data['Resources']['Intrinsic'])

    async def test_two_entry_points_dispatch_through_real_command_permission_checks(self):
        registered = {}
        self.bot.Modules['Commands'].add_command = lambda b, **kwargs: registered.update({kwargs['name']: kwargs})
        await Arcana.setup(self.bot)
        self.commit()
        self.bot.Commands = registered
        source = ast.parse((harness.root / 'Modules/Commands.py').read_text(encoding='utf-8'))
        handler = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'on_message')
        namespace = {'checks': {'isPlayer': AsyncMock(return_value=True), 'isMod': AsyncMock(side_effect=lambda b, p: p['Author PID'] == 3)}}
        exec(compile(ast.Module(body=[handler], type_ignores=[]), 'Modules/Commands.py', 'exec'), namespace)
        msg = self.payload('!card-admin history 300 1') | {'MID': 123}
        await namespace['on_message'](self.bot, msg)
        self.commit()
        self.assertFalse(self.bot.Data['Card Game']['History'])
        await namespace['on_message'](self.bot, msg | {'Author PID': 3})
        self.commit()
        self.assertEqual(self.bot.Data['Card Game']['History'], [{'Number': 300, 'Voters': [1]}])
        await namespace['on_message'](self.bot, msg | {'Content': '!card history 301 1'})
        self.commit()
        self.assertEqual(len(self.bot.Data['Card Game']['History']), 1)

    async def test_arcana_actions_route_through_card_entry_point_and_preserve_draw_guards(self):
        with patch.object(Arcana, 'choose', return_value='Two of Cups'):
            await Arcana.command(self.bot, self.payload('!card crystal-draw'))
        self.commit()
        self.assertEqual(len(self.bot.Data['Players'][1]['Hand']), 1)
        self.assertFalse(self.bot.Data['Cards']['Outside'])
        self.assertEqual(Arcana.crystals(self.bot, 1), 2)
        await Arcana.command(self.bot, self.payload('!card list'))
        self.assertIn('Two of Cups', self.bot.Modules['Discord_Module'].send.call_args.args[2])
        await Arcana.command(self.bot, self.payload('!card crystal-draw') | {'Channel': 'bot-spam'})
        self.assertIn('#actions', self.bot.Modules['Discord_Module'].return_resp.call_args.args[2])
        self.bot.Data['Card Game']['Random Rolls'][1] = 'pending'
        await Arcana.command(self.bot, self.payload('!card list'))
        self.assertIn('!card random', self.bot.Modules['Discord_Module'].return_resp.call_args.args[2])


if __name__ == '__main__': unittest.main()
