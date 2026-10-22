import ast
import datetime
import io
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
# Exercise the real deferred data API without starting Discord or loading credentials.
source = ast.parse((root / 'Core/Nomitron.py').read_text(encoding='utf-8'))
botClass = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'DiscordNomicBot')
methods = {'stage', 'get', 'set', 'remove', 'update_nested_dict', '_data_value_at',
           '_without_flags', '_parent_and_key', '_apply_data_change', 'keys', 'has', 'where'}
botClass.body = [n for n in botClass.body if isinstance(n, ast.FunctionDef) and n.name in methods]
namespace = {'deepcopy': deepcopy, 'SAVE_TO_FOLDER': '_SAVE TO FOLDER SAVE FLAG', 'OIK': 'Object Index Key'}
exec(compile(ast.Module(body=[botClass], type_ignores=[]), 'Core/Nomitron.py', 'exec'), namespace)
Bot = namespace['DiscordNomicBot']
sys.modules.setdefault('discord', SimpleNamespace(Interaction=object))
from Modules import Arcana, Voting, ItemsAndTeams, Schedules, Rules


class ArcanaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = bot = Bot()
        bot.Data, bot.Data_Changes, bot.stage_source = {}, [], 'test'
        bot.Data = {
            'Vars': {'Turn': 4, 'Day': 2, 'Weekday': 'Tuesday', 'Time': datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc), 'Next Proposal Number': 312},
            'Players': {p: {'Name': str(p), 'Intrinsic': {'Luck': 1, 'Crystals': 4}} for p in [1, 2, 3]},
            'Resources': {'Intrinsic': ['Luck', 'Pockets']},
            'Queue-Proposals': {}, 'User-Proposal-Endorsement': {}, 'User-Proposal-Votes': {},
        }
        discord = SimpleNamespace(isPlayer=lambda b, p: p in b.Data['Players'],
            isActive=lambda b, p: p != 3, send=AsyncMock(), return_resp=AsyncMock(),
            create_channel=AsyncMock(), add_reaction=AsyncMock())
        self.drawn = AsyncMock()
        bot.Modules = {'Discord_Module': discord, 'Commands': SimpleNamespace(add_command=lambda *a, **k: None),
            'Arcana': Arcana, 'Voting': Voting, 'ItemsAndTeams': ItemsAndTeams,
            'DrawEffects': SimpleNamespace(on_card_draw=self.drawn),
            'Nomitron': SimpleNamespace(startDate=bot.Data['Vars']['Time'])}
        bot.day, bot.hr = datetime.timedelta(days=1), datetime.timedelta(hours=1)
        bot.log = lambda *a: None
        self.tasks = []
        bot.add_Task = lambda callback, *a, **kw: self.tasks.append(callback)
        bot.get_Ref = lambda *a: 'actions'
        bot.schedule = lambda **kw: None
        bot.wrap = lambda callback, kwargs: callback(**kwargs)
        await Arcana.setup(bot)
        self.commit()

    def commit(self):
        for change in self.bot.Data_Changes: self.bot._apply_data_change(self.bot.Data, change)
        self.bot.Data_Changes.clear()

    def payload(self, content='', pid=1):
        return {'Content': content, 'Author PID': pid, 'Channel': 'actions'}

    def proposal(self, key, queue='tarot', pid=1, state='Queue', number=None):
        self.bot.Data['Queue-Proposals'][key] = {
            'Queue': queue, 'PID': pid, 'State': state, 'Rank': 0, 'DOB': self.bot.Data['Vars']['Time'],
            'Body': 'Wheel of Fortune: Every active player gains 2 Luck.', 'Proposal#': number,
            'Arcana': 'Wheel of Fortune', 'Arcana Effect': 'Every active player gains 2 Luck.',
            'Channel': None, 'Link': 'link', 'Endorse-MID': None,
            'Vote Start Time': self.bot.Data['Vars']['Time'] - 2*self.bot.hr,
        }
        if queue != 'tarot':
            for field in ['Arcana', 'Arcana Effect']: self.bot.Data['Queue-Proposals'][key].pop(field)

    async def promote(self, scheduled_time=None):
        await Voting.popProposalMain(self.bot, scheduled_time=scheduled_time or self.bot.Data['Vars']['Time'])

    async def test_seed_and_restart(self):
        cards = self.bot.Data['Cards']
        self.assertEqual(len(cards['Definitions']), 78)
        cards['Definitions']['The Fool']['Effect'] = 'Some text.'
        cards['Seen'] = ['The Fool']
        await Arcana.setup(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['The Fool']['Effect'], 'Some text.')
        self.assertEqual(self.bot.Data['Cards']['Seen'], ['The Fool'])

    async def test_weights_and_outside_zones(self):
        cards = self.bot.get('Cards')
        self.assertEqual(Arcana.weight(cards, 'The Fool'), 0)
        self.assertEqual(Arcana.weight(cards, 'The Fool', True), 6)
        self.assertEqual(Arcana.weight(cards, 'The Chariot', True), 2)
        name = 'Two of Cups'
        cards['Outside'] = [{'Name': name, 'Owner': 1, 'Zone': zone} for zone in ['Private Hand', 'Personal Deck', 'Play Area']]
        self.assertEqual(Arcana.weight(cards, name), 0.125)
        cards['Previous Turn Cards'] = [name]
        self.assertEqual(Arcana.weight(cards, name, True), 0)
        cards['Outside'].append({'Name': 'The Fool', 'Owner': 1, 'Zone': 'Public Hand'})
        self.assertEqual(Arcana.weight(cards, 'The Fool', True), 0)

    async def test_turn_draw_and_return_do_not_trigger_draw_effects(self):
        with patch.object(Arcana, 'choose', return_value='Wheel of Fortune'):
            await Arcana.onTurnStart(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['Luck'], 2)
        self.assertEqual(self.bot.Data['Players'][3]['Intrinsic']['Luck'], 1)
        self.drawn.assert_not_awaited()
        await Arcana.onTurnEnd(self.bot)
        self.commit()
        self.assertIsNone(self.bot.Data['Cards']['Turn Card'])
        self.assertEqual(self.bot.Data['Cards']['Previous Turn Cards'], ['Wheel of Fortune'])
        self.assertFalse(self.bot.Data['Cards']['Outside'])

    async def test_non_arcana_turn_card_draws_for_eligible_active_player(self):
        self.bot.Data['Cards']['Definitions']['Other'] = {'Count': 1, 'Weight': 1, 'Effect': ''}
        self.bot.Data['Cards']['Turn Card'] = 'Other'
        self.bot.Data['Players'][1]['Can Draw Cards'] = False
        await Arcana.onTurnEnd(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Outside'], [{'Name': 'Other', 'Owner': 2, 'Zone': 'Private Hand'}])
        self.drawn.assert_awaited_once()

    async def test_crystal_draw_limit_and_failed_draw(self):
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 2)
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 1)
        self.bot.Data['Players'][2]['Can Draw Cards'] = False
        await Arcana.crystalDraw(self.bot, self.payload(pid=2))
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 2), 4)

    async def test_tarot_edit_distance_eligibility_and_deck_edits(self):
        self.assertEqual(Arcana.wordChanges('A B C', 'A X C D'), 2)
        with self.assertRaises(ValueError): Arcana.tarotText(self.bot, 'The Fool: Anything.')
        self.bot.Data['Cards']['Seen'].append('The Fool')
        self.assertEqual(Arcana.tarotText(self.bot, 'The Fool: A fragment'), ('The Fool', 'A fragment'))
        self.proposal('t', state='On Deck')
        self.assertTrue(await Voting.validateDeckEdit(self.bot, self.payload(), 't', 'Wheel of Fortune: Every active player gains 2 Luck.'))
        self.commit()
        self.assertFalse(await Voting.validateDeckEdit(self.bot, self.payload(), 't', 'Wheel of Fortune: Every inactive person loses 2 Luck.'))
        self.assertFalse(await Voting.validateDeckEdit(self.bot, self.payload(), 't', 'The Chariot: ' + Arcana.effects['The Chariot']))

    async def test_submission_limit_and_two_wands(self):
        msg = self.payload('Wheel of Fortune: Every active player gains 2 Luck.') | {
            'Channel': 'tarot-proposals', 'Category': 'BUSINESS', 'MID': 123, 'Link': 'link', 'Attachments': {}}
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.bot.Data['Vars']['Time'] += self.bot.hr
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertEqual(len(self.bot.Data['Queue-Proposals']), 1)
        self.bot.Data['Cards']['Turn Card'] = 'Two of Wands'
        self.bot.Data['Vars']['Time'] += self.bot.hr
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertEqual(len(self.bot.Data['Queue-Proposals']), 2)

    async def test_promotion_order_cooldown_and_effects(self):
        for effect, expected in [(None, 2), ('The Chariot', 3), ('The Hanged Man', 0)]:
            with self.subTest(effect=effect):
                self.bot.Data['Queue-Proposals'] = {}
                self.bot.Data['Cards']['Turn Card'] = effect
                self.bot.Data['Cards']['Last Tarot Deck'] = None
                self.bot.Data['Cards'].pop('Last Tarot Deck Scheduled', None)
                self.bot.Data['Cards'].pop('Last Tarot Turn', None)
                for i in range(3): self.proposal(f't{i}')
                self.proposal('main', 'main')
                self.proposal('judge', 'judge')
                start = self.bot.Data['Vars']['Next Proposal Number']
                await self.promote()
                self.commit()
                promoted = [p for p in self.bot.Data['Queue-Proposals'].values() if p['Queue'] == 'tarot' and p['State'] == 'On Deck']
                self.assertEqual(len(promoted), expected)
                self.assertEqual([p['Proposal#'] for p in promoted], list(range(start+2, start+2+expected)))
        self.bot.Data['Cards']['Turn Card'] = None
        self.bot.Data['Cards']['Last Tarot Turn'] = 3
        self.bot.Data['Cards']['Last Tarot Deck'] = self.bot.Data['Vars']['Time'] - 6*self.bot.day
        self.bot.Data['Cards'].pop('Last Tarot Deck Scheduled', None)
        await self.promote()
        self.commit()
        self.assertTrue(all(p['State'] == 'Queue' for p in self.bot.Data['Queue-Proposals'].values() if p['Queue'] == 'tarot'))
        self.bot.Data['Vars']['Time'] += self.bot.day
        await self.promote()
        self.commit()
        self.assertEqual(sum(p['State'] == 'On Deck' and p['Queue'] == 'tarot' for p in self.bot.Data['Queue-Proposals'].values()), 2)

    async def test_paid_priority_survives_ranking(self):
        self.proposal('first')
        self.proposal('second')
        self.bot.Data['User-Proposal-Endorsement']['e'] = {'PID': 2, 'Proposal-ID': 'first'}
        await Arcana.tarotTop(self.bot, self.payload('!tarot-top second'))
        self.commit()
        await self.promote()
        self.commit()
        self.assertLess(self.bot.Data['Queue-Proposals']['second']['Proposal#'], self.bot.Data['Queue-Proposals']['first']['Proposal#'])
        self.assertEqual(Arcana.crystals(self.bot, 1), 2)

    async def test_tally_rewards_once_and_multiple_passes_accumulate(self):
        for key in ['a', 'b']:
            self.proposal(key, state='Voting', number=312 if key == 'a' else 313)
            for pid in [1, 2]:
                self.bot.Data['User-Proposal-Votes'][f'{pid}-{key}'] = {'PID-Voter': pid, 'Proposal-ID': key, 'Vote': 'Yay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 6)
        self.assertEqual(Arcana.crystals(self.bot, 2), 6)
        self.assertEqual(Arcana.crystals(self.bot, 3), 4)
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], 'Every active player gains 2 Luck.')
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 6)

    async def test_opening_spread_once_and_claim_expiry(self):
        payload = self.payload('!opening-spread 1 2 : 1')
        await Arcana.openingSpread(self.bot, payload)
        self.commit()
        await Arcana.openingSpread(self.bot, payload)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 3), 6)
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 1)
        await Arcana.openingDraw(self.bot, self.payload())
        self.commit()
        await Arcana.openingDraw(self.bot, self.payload())
        self.commit()
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 2)
        self.bot.Data['Vars']['Turn'] += 1
        await Arcana.openingDraw(self.bot, self.payload(pid=2))
        self.commit()
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 2)

    async def test_crystal_resource_migration_and_nonnegative(self):
        await ItemsAndTeams.setup(self.bot)
        self.commit()
        self.assertIn('Crystals', self.bot.Data['Resources']['Intrinsic'])
        # The moderator amount command must enforce the same lower bound.
        with patch.object(ItemsAndTeams, 'pidFrom', return_value=1):
            await ItemsAndTeams.setAmount(self.bot, self.payload('!set-amount 1 -1 Crystals'))
            self.commit()
            self.assertEqual(Arcana.crystals(self.bot, 1), 4)

    async def test_turn_end_preserves_passed_effect_before_card_return(self):
        self.bot.Data['Cards']['Turn Card'] = 'Wheel of Fortune'
        self.proposal('t', state='Voting', number=312)
        self.bot.Data['User-Proposal-Votes']['v'] = {'PID-Voter': 2, 'Proposal-ID': 't', 'Vote': 'Yay'}
        await Schedules.onTurnEnd(self.bot)
        self.commit()
        self.assertIn(Arcana.onTurnEnd, self.tasks)
        await self.tasks.pop()(self.bot)
        self.commit()
        self.assertIsNone(self.bot.Data['Cards']['Turn Card'])
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], 'Every active player gains 2 Luck.')
        self.assertEqual(Arcana.crystals(self.bot, 1), 5)

    async def test_failed_tarot_does_not_reward_or_change_effect(self):
        self.proposal('t', state='Voting', number=312)
        self.bot.Data['User-Proposal-Votes']['v'] = {'PID-Voter': 2, 'Proposal-ID': 't', 'Vote': 'Nay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 4)
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], Arcana.effects['Wheel of Fortune'])

    async def test_queue_display_handles_two_tarots_per_player(self):
        for i in range(4): self.proposal(f't{i}')
        discord = self.bot.Modules['Discord_Module']
        async def display(bot, channel, messages): return list(range(len(messages)))
        discord.display = display
        await Voting.update_display(self.bot)
        self.commit()
        self.assertEqual([self.bot.Data['Queue-Proposals'][f't{i}']['Endorse-MID'] for i in range(4)], [3, 2, 1, 0])

    async def test_complete_seed_sentence_with_fragment_still_applies(self):
        self.bot.Data['Cards']['Turn Card'] = 'The Chariot'
        self.bot.Data['Cards']['Definitions']['The Chariot']['Effect'] += ' A fragment'
        self.assertTrue(Arcana.hasEffect(self.bot, 'The Chariot'))

    async def test_hand_is_private_and_excludes_other_owners_and_zones(self):
        self.bot.Data['Cards']['Outside'] = [
            {'Name': name, 'Owner': owner, 'Zone': zone}
            for name, owner, zone in [('The Fool', 1, 'Private Hand'),
                ('The Star', 1, 'Public Hand'), ('The Moon', 2, 'Private Hand'),
                ('The Sun', 1, 'Play Area')]]
        await Arcana.showHand(self.bot, self.payload())
        self.bot.Modules['Discord_Module'].send.assert_awaited_once_with(
            self.bot, 1, 'Your hand:\nThe Fool\nThe Star')
        self.bot.Modules['Discord_Module'].return_resp.assert_not_awaited()
        await Arcana.showHand(self.bot, self.payload(pid=3))
        self.assertEqual(self.bot.Modules['Discord_Module'].send.call_args.args[2], 'Your hand:\n(empty)')

    async def test_arcana_display_preserves_fragments(self):
        self.bot.Data['Cards']['Definitions']['The Fool']['Effect'] = 'Unfinished thought'
        await Arcana.showArcana(self.bot, self.payload())
        text = self.bot.Modules['Discord_Module'].return_resp.call_args.args[2]
        self.assertIn('Turn Card: none', text)
        self.assertIn('The Fool: Unfinished thought', text)
        self.assertIn('The World: (empty)', text)

    async def test_unclaimed_global_card_does_not_stop_future_turn_card_draws(self):
        cards = self.bot.Data['Cards']
        cards['Definitions']['Other'] = {'Count': 1, 'Weight': None, 'Effect': ''}
        cards['Turn Card'] = 'Other'
        for player in self.bot.Data['Players'].values(): player['Can Draw Cards'] = False
        await Arcana.onTurnEnd(self.bot)
        self.commit()
        self.assertIsNone(self.bot.Data['Cards']['Turn Card'])
        self.assertEqual(self.bot.Data['Cards']['Outside'], [{'Name': 'Other', 'Owner': None, 'Zone': 'Global'}])
        self.drawn.assert_not_awaited()
        with patch.object(Arcana, 'choose', return_value='The Fool') as choose:
            await Arcana.onTurnStart(self.bot)
            self.commit()
            choose.assert_called_once()
        self.assertEqual(self.bot.Data['Cards']['Turn Card'], 'The Fool')
        self.drawn.assert_not_awaited()

    async def test_finite_and_empty_deck_draws(self):
        cards = self.bot.Data['Cards']
        cards['Definitions'] = {'Other': {'Count': 1, 'Weight': None, 'Effect': ''}}
        self.assertEqual(Arcana.weight(cards, 'Other'), 1)
        self.assertEqual(await Arcana.draw(self.bot, cards, 1), 'Other')
        self.assertEqual(Arcana.weight(cards, 'Other'), 0)
        self.assertIsNone(Arcana.choose(cards))
        self.assertIsNone(await Arcana.draw(self.bot, cards, 1))
        self.drawn.assert_awaited_once()
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 4)
        self.assertNotIn('Crystal Draw Turn', self.bot.Data['Players'][1])

    async def test_crystal_draw_needs_funds_and_resets_next_turn(self):
        self.bot.Data['Players'][1]['Intrinsic']['Crystals'] = 1
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        self.assertFalse(self.bot.Data['Cards']['Outside'])
        self.assertEqual(Arcana.crystals(self.bot, 1), 1)
        self.bot.Data['Players'][1]['Intrinsic']['Crystals'] = 4
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        self.bot.Data['Vars']['Turn'] += 1
        await Arcana.crystalDraw(self.bot, self.payload())
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 0)
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 2)

    async def test_tarot_actions_reject_unowned_undecked_and_missing_targets_without_spending(self):
        self.proposal('other', pid=2)
        self.proposal('deck', state='On Deck')
        self.proposal('main', queue='main')
        for callback in [Arcana.tarotTop, Arcana.tarotRemove]:
            for key in ['other', 'deck', 'main', 'missing', '']:
                with self.subTest(command=callback.__name__, key=key):
                    before = self.bot.get('Queue-Proposals')
                    await callback(self.bot, self.payload(f'!command {key}'))
                    self.commit()
                    self.assertEqual(self.bot.get('Queue-Proposals'), before)
                    self.assertEqual(Arcana.crystals(self.bot, 1), 4)

    async def test_tarot_remove_cleans_endorsements_and_unfunded_boost_does_not_reorder(self):
        self.proposal('mine')
        self.bot.Data['User-Proposal-Endorsement']['e'] = {'PID': 2, 'Proposal-ID': 'mine'}
        self.bot.Data['Players'][1]['Intrinsic']['Crystals'] = 1
        await Arcana.tarotTop(self.bot, self.payload('!tarot-top mine'))
        self.commit()
        self.assertNotIn('Tarot Priority', self.bot.Data['Queue-Proposals']['mine'])
        self.assertEqual(Arcana.crystals(self.bot, 1), 1)
        await Arcana.tarotRemove(self.bot, self.payload('!tarot-remove mine'))
        self.commit()
        await Voting.update(self.bot)
        self.commit()
        self.assertFalse(self.bot.Data['Queue-Proposals'])
        self.assertFalse(self.bot.Data['User-Proposal-Endorsement'])

    async def test_invalid_tarot_format_and_word_change_boundaries(self):
        for text in ['The Fool', 'Not a card: Something.', ': Something.']:
            with self.subTest(text=text), self.assertRaises(ValueError): Arcana.tarotText(self.bot, text)
        for old, new, distance in [('one two', '', 2), ('', 'one two', 2),
                ('one two', 'three four', 2), ('one two', 'one two', 0),
                ('one two three', 'four five six', 3)]:
            self.assertEqual(Arcana.wordChanges(old, new), distance)
        self.bot.Data['Cards']['Definitions']['The Fool']['Effect'] = 'One two.'
        self.assertEqual(Arcana.tarotText(self.bot, 'The Fool: '), ('The Fool', ''))

    async def test_opening_spread_invalid_inputs_have_no_side_effects(self):
        for content in ['!opening-spread', '!opening-spread 999 :', '!opening-spread : 999']:
            with self.subTest(content=content):
                before = self.bot.get('Players')
                await Arcana.openingSpread(self.bot, self.payload(content))
                self.commit()
                self.assertEqual(self.bot.get('Players'), before)
                self.assertIsNone(self.bot.Data['Cards']['Opening Spread'])
        self.bot.Data['Players'][1]['Can Draw Cards'] = False
        await Arcana.openingSpread(self.bot, self.payload('!opening-spread 2 : 1'))
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 4)
        self.assertIsNone(self.bot.Data['Cards']['Opening Spread'])

    async def test_opening_claim_restrictions_do_not_consume_entitlement(self):
        await Arcana.openingDraw(self.bot, self.payload())
        self.commit()
        self.assertFalse(self.bot.Data['Cards']['Outside'])
        await Arcana.openingSpread(self.bot, self.payload('!opening-spread <@1> <@1> : 2 2'))
        self.commit()
        self.assertEqual(len(self.bot.Data['Cards']['Outside']), 1)
        self.assertEqual(self.bot.Data['Cards']['Opening Spread']['Eligible'], [1])
        self.bot.Data['Players'][1]['Can Draw Cards'] = False
        await Arcana.openingDraw(self.bot, self.payload())
        self.commit()
        await Arcana.openingDraw(self.bot, self.payload(pid=3))
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Opening Spread']['Claimed'], [])
        self.bot.Data['Players'][1]['Can Draw Cards'] = True
        await Arcana.openingDraw(self.bot, self.payload())
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Opening Spread']['Claimed'], [1])

    async def test_only_global_turn_card_activates_effects(self):
        self.bot.Data['Cards']['Outside'] = [{'Name': 'The Chariot', 'Owner': 1, 'Zone': 'Play Area'}]
        self.assertFalse(Arcana.hasEffect(self.bot, 'The Chariot'))
        self.bot.Data['Cards']['Turn Card'] = 'The Chariot'
        self.bot.Data['Cards']['Definitions']['The Chariot']['Effect'] = 'This turn, the top three Tarot Proposals'
        self.assertFalse(Arcana.hasEffect(self.bot, 'The Chariot'))

    async def test_start_schedule_uses_initial_end_for_tarot_and_next_day_voting(self):
        scheduled = []
        self.bot.schedule = lambda **kwargs: scheduled.append(kwargs)
        with patch.object(Arcana, 'choose', return_value='The Fool'):
            await Schedules.onTurnStart(self.bot)
        self.commit()
        end = self.bot.Modules['Nomitron'].startDate + 3*self.bot.day
        deck = next(s for s in scheduled if s['name'] == 'On Deck')
        vote = next(s for s in scheduled if s['name'] == 'Vote Starts')
        self.assertEqual((deck['module_name'], deck['method_name']), ('Voting', 'popProposalMain'))
        self.assertEqual(deck['Trigger_Value'], end - 2*self.bot.day)
        self.assertEqual(deck['kwargs']['scheduled_time'], deck['Trigger_Value'])
        self.assertEqual(vote['Trigger_Value'], end - self.bot.day)
        self.assertEqual(self.bot.Data['Cards']['Turn Card'], 'The Fool')
        self.assertIn('The Fool', self.bot.Data['Cards']['Seen'])
        self.proposal('t')
        self.bot.Data['Vars']['Time'] = deck['Trigger_Value'] + datetime.timedelta(milliseconds=200)
        await Voting.popProposalMain(self.bot, **deck['kwargs'])
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['t']['State'], 'On Deck')

    async def test_tarot_deck_edits_use_single_and_numbered_message_paths(self):
        self.proposal('tarot', state='On Deck', number=312)
        msg = self.payload('Wheel of Fortune: Every active player gains 2 Luck.') | {
            'Channel': 'deck-edits', 'Category': 'BUSINESS', 'MID': 123, 'Attachments': {}}
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['tarot']['Arcana Effect'], 'Every active player gains 2 Luck.')
        self.proposal('main', queue='main', state='On Deck', number=313)
        msg['Content'] = '312\nWheel of Fortune: Every active player gains 3 Luck.'
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['tarot']['Arcana Effect'], 'Every active player gains 3 Luck.')
        before = self.bot.get('Queue-Proposals', 'tarot')
        msg['Content'] = '312\nWheel of Fortune: Every inactive person loses 4 Luck.'
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertEqual(self.bot.get('Queue-Proposals', 'tarot'), before)

    async def test_tarot_ties_award_nothing_and_deck_opens_to_voting(self):
        self.proposal('t', state='On Deck', number=312)
        await Voting.PutToVote(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['t']['State'], 'Voting')
        self.bot.Data['Vars']['Time'] += 2*self.bot.hr
        for pid, vote in [(1, 'Yay'), (2, 'Nay')]:
            self.bot.Data['User-Proposal-Votes'][str(pid)] = {'PID-Voter': pid, 'Proposal-ID': 't', 'Vote': vote}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 4)
        self.assertFalse(self.bot.Data['Queue-Proposals'])

    async def test_proposal_display_describes_only_the_arcana_amendment(self):
        self.proposal('t', state='On Deck', number=312)
        text = Voting.proposalText(self.bot, 't')
        self.assertIn('Proposal #312', text)
        self.assertIn('Amend Rule 302 by setting the following Arcana Effect:', text)
        self.assertIn('Wheel of Fortune: Every active player gains 2 Luck.', text)
        self.proposal('main', queue='main', state='On Deck', number=313)
        self.assertNotIn('Amend Rule 302 by setting', Voting.proposalText(self.bot, 'main'))

    async def test_tarot_promotion_does_not_repeat_in_same_turn_or_consume_empty_cooldown(self):
        await self.promote()
        self.commit()
        self.assertIsNone(self.bot.Data['Cards']['Last Tarot Deck'])
        self.bot.Data['Vars']['Turn'] += 1
        for i in range(3): self.proposal(f't{i}')
        await self.promote()
        self.commit()
        nextNumber = self.bot.Data['Vars']['Next Proposal Number']
        await self.promote()
        self.commit()
        self.assertEqual(self.bot.Data['Vars']['Next Proposal Number'], nextNumber)
        self.assertEqual(sum(p['State'] == 'On Deck' for p in self.bot.Data['Queue-Proposals'].values()), 2)

    async def test_same_arcana_conflict_is_rechecked_in_number_order_and_held_without_rewards(self):
        first = 'Every inactive person gains 1 Luck.'
        second = 'Every active player loses 2 Luck.'
        self.assertEqual(Arcana.wordChanges(Arcana.effects['Wheel of Fortune'], first), 2)
        self.assertEqual(Arcana.wordChanges(Arcana.effects['Wheel of Fortune'], second), 2)
        self.assertEqual(Arcana.wordChanges(first, second), 4)
        # Insert out of order to prove proposal numbers govern application order.
        for key, number, owner, effect in [('second', 313, 2, second), ('first', 312, 1, first)]:
            self.proposal(key, state='Voting', number=number, pid=owner)
            self.bot.Data['Queue-Proposals'][key]['Arcana Effect'] = effect
            self.bot.Data['User-Proposal-Votes'][key] = {'PID-Voter': 3, 'Proposal-ID': key, 'Vote': 'Yay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], first)
        self.assertNotIn('first', self.bot.Data['Queue-Proposals'])
        self.assertIn('second', self.bot.Data['Queue-Proposals'])
        self.assertIn('second', self.bot.Data['User-Proposal-Votes'])
        self.assertIn('Arcana Conflict', self.bot.Data['Queue-Proposals']['second'])
        self.assertEqual([Arcana.crystals(self.bot, pid) for pid in [1, 2, 3]], [5, 4, 5])
        announcements = self.bot.Modules['Discord_Module'].send.await_count
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(self.bot.Modules['Discord_Module'].send.await_count, announcements)
        self.assertEqual(Arcana.crystals(self.bot, 3), 5)

    async def test_scheduled_seven_day_gap_ignores_execution_jitter(self):
        scheduled = self.bot.Data['Vars']['Time']
        self.proposal('first')
        self.bot.Data['Vars']['Time'] += datetime.timedelta(microseconds=500000)
        await self.promote(scheduled)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Last Tarot Deck Scheduled'], scheduled)
        self.bot.Data['Queue-Proposals'].clear()
        self.bot.Data['Vars']['Turn'] += 3
        self.bot.Data['Vars']['Time'] = scheduled + 7*self.bot.day
        self.proposal('nextweek')
        await self.promote(scheduled + 7*self.bot.day)
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['nextweek']['State'], 'On Deck')

    async def test_early_and_manual_pop_cannot_promote_tarot(self):
        self.proposal('t')
        await Voting.popProposalMain(self.bot)
        self.commit()
        await self.promote(self.bot.Data['Vars']['Time'] + self.bot.hr)
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['t']['State'], 'Queue')
        self.assertNotIn('Last Tarot Turn', self.bot.Data['Cards'])

    async def test_official_effect_refresh_updates_manual_corrections_without_reverting_pending_passes(self):
        initial = '### List of Arcana Effects\nWheel of Fortune: Every active player gains 1 Luck.'
        await Arcana.syncEffects(self.bot, initial)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['The Chariot']['Effect'], '')
        self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'] = 'Every active player gains 2 Luck.'
        await Arcana.syncEffects(self.bot, initial)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], 'Every active player gains 2 Luck.')
        corrected = '### List of Arcana Effects\n**Wheel of Fortune:** Every active player gains 3 Luck.\n- The Fool: A fragment\ncontinuing here'
        await Arcana.syncEffects(self.bot, corrected)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], 'Every active player gains 3 Luck.')
        self.assertEqual(self.bot.Data['Cards']['Definitions']['The Fool']['Effect'], 'A fragment\ncontinuing here')
        await Arcana.syncEffects(self.bot, 'List of Arcana Effects\n')
        self.commit()
        self.assertTrue(all(d['Effect'] == '' for d in self.bot.Data['Cards']['Definitions'].values()))

    async def test_invalid_official_list_warns_without_replacing_cache(self):
        before = self.bot.get('Cards')
        await Arcana.syncEffects(self.bot, 'No effect list in this older rule.')
        await Arcana.syncEffects(self.bot, 'List of Arcana Effects\nUnrecognized table format')
        self.commit()
        self.assertEqual(self.bot.get('Cards'), before)
        self.assertIn('Could not parse', self.bot.Modules['Discord_Module'].send.call_args.args[2])

    async def test_rules_reload_schedules_effect_sync_after_rule_import(self):
        jobs = []
        self.bot.add_Task = lambda callback, kwargs: jobs.append((callback, kwargs))
        text = '\n## 302 MDoMA\nList of Arcana Effects\nWheel of Fortune: Every active player gains 4 Luck.\n'
        with patch.object(Rules.urllib.request, 'urlopen', return_value=io.BytesIO(text.encode())):
            await Rules.reload_references(self.bot)
        self.commit()
        self.assertIn('4 Luck.', self.bot.Data['Rules'][302]['Text'])
        for callback, kwargs in jobs: await callback(self.bot, **kwargs)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'], 'Every active player gains 4 Luck.')

    async def test_unrecognized_turn_effect_explicitly_requests_adjudication(self):
        self.bot.Data['Cards']['Definitions']['Wheel of Fortune']['Effect'] = 'Every active player gains 2 Luck.'
        with patch.object(Arcana, 'choose', return_value='Wheel of Fortune'):
            await Arcana.onTurnStart(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Players'][1]['Intrinsic']['Luck'], 1)
        self.assertIn('Manual adjudication required', self.bot.Modules['Discord_Module'].send.call_args.args[2])

    async def test_tarot_replacement_and_dot_removal_match_main_queue(self):
        msg = self.payload('Wheel of Fortune: Every active player gains 2 Luck.') | {
            'Channel': 'tarot-proposals', 'Category': 'BUSINESS', 'MID': 123, 'Link': 'link', 'Attachments': {}}
        await Voting.on_message(self.bot, msg)
        self.commit()
        old = next(iter(self.bot.Data['Queue-Proposals']))
        self.bot.Data['Vars']['Time'] += self.bot.hr
        msg['Content'] = 'Wheel of Fortune: Every active player gains 3 Luck.'
        await Voting.on_message(self.bot, msg)
        self.commit()
        self.assertNotIn(old, self.bot.Data['Queue-Proposals'])
        self.assertEqual(len(self.bot.Data['Queue-Proposals']), 1)
        msg['Content'] = '.'
        await Voting.on_message(self.bot, msg)
        self.commit()
        await Voting.update(self.bot)
        self.commit()
        self.assertFalse(self.bot.Data['Queue-Proposals'])
        self.assertFalse(self.bot.Data['User-Proposal-Endorsement'])

    async def test_main_queue_canonical_arcana_amendment_receives_tarot_rewards(self):
        msg = self.payload('Wheel of Fortune: Every active player gains 2 Luck.') | {
            'Channel': 'main-proposals', 'Category': 'BUSINESS', 'MID': 123, 'Link': 'link', 'Attachments': {}}
        await Voting.on_message(self.bot, msg)
        self.commit()
        key = next(iter(self.bot.Data['Queue-Proposals']))
        proposal = self.bot.Data['Queue-Proposals'][key]
        self.assertEqual(proposal['Queue'], 'main')
        proposal.update({'State': 'Voting', 'Proposal#': 312, 'Vote Start Time': self.bot.Data['Vars']['Time'] - 2*self.bot.hr})
        self.bot.Data['User-Proposal-Votes']['v'] = {'PID-Voter': 2, 'Proposal-ID': key, 'Vote': 'Yay'}
        await Voting.TallyVotes(self.bot)
        self.commit()
        self.assertEqual(Arcana.crystals(self.bot, 1), 5)
        self.assertEqual(Arcana.crystals(self.bot, 2), 5)

    async def test_team_hands_and_visibility_use_entity_membership(self):
        self.bot.Data['Teams'] = {'Tea': {'Members': [1, 2]}}
        cards = self.bot.get('Cards')
        await Arcana.draw(self.bot, cards, ['Teams', 'Tea'], name='The Fool')
        self.bot.Data['Cards'] = cards
        self.assertEqual([call.args[1] for call in self.bot.Modules['Discord_Module'].send.await_args_list], [1, 2])
        card = cards['Outside'][0]
        self.assertTrue(Arcana.visible(self.bot, card, 2))
        self.assertFalse(Arcana.visible(self.bot, card, 3))
        await Arcana.showHand(self.bot, self.payload('!hand Tea', pid=2))
        self.assertIn('The Fool', self.bot.Modules['Discord_Module'].send.call_args.args[2])
        await Arcana.showHand(self.bot, self.payload('!hand Tea', pid=3))
        self.assertIn('not a member', self.bot.Modules['Discord_Module'].send.call_args.args[2])
        card['Zone'] = 'Public Hand'
        self.assertTrue(Arcana.visible(self.bot, card, 3))
        await Arcana.showCards(self.bot, self.payload(pid=3))
        self.assertIn('The Fool', self.bot.Modules['Discord_Module'].send.call_args.args[2])
        self.assertIsNone(await Arcana.draw(self.bot, cards, ['Teams', 'Missing'], name='The Fool'))

    async def test_edition_sticker_metadata_survives_turn_card_handoff_without_draw_trigger(self):
        async def decorate(bot, card):
            card.update({'Edition': 'Foil', 'Stickers': ['A unique sticker']})
        self.bot.Modules['Editions'] = SimpleNamespace(on_card_created=decorate)
        self.bot.Data['Cards']['Definitions']['Other'] = {'Count': 1, 'Weight': 1, 'Effect': ''}
        with patch.object(Arcana, 'choose', return_value='Other'):
            await Arcana.onTurnStart(self.bot)
        self.commit()
        self.assertEqual(self.bot.Data['Cards']['Turn Card Details']['Edition'], 'Foil')
        self.drawn.assert_not_awaited()
        await Arcana.showCards(self.bot, self.payload())
        self.assertIn('Foil', self.bot.Modules['Discord_Module'].send.call_args.args[2])
        await Arcana.onTurnEnd(self.bot)
        self.commit()
        card = self.bot.Data['Cards']['Outside'][0]
        self.assertEqual((card['Edition'], card['Stickers']), ('Foil', ['A unique sticker']))
        self.assertEqual(self.drawn.await_count, 1)

    async def test_invalid_replacements_leave_existing_proposals_intact(self):
        for queue in ['main', 'tarot']:
            with self.subTest(queue=queue):
                self.bot.Data['Queue-Proposals'].clear()
                self.proposal('existing', queue=queue)
                before = self.bot.get('Queue-Proposals')
                msg = self.payload('Wheel of Fortune: Every inactive person loses 4 Luck.') | {
                    'Channel': queue + '-proposals', 'Category': 'BUSINESS', 'MID': 123, 'Link': 'link', 'Attachments': {}}
                await Voting.on_message(self.bot, msg)
                self.commit()
                self.assertEqual(self.bot.get('Queue-Proposals'), before)

    async def test_normal_deck_edit_becomes_tarot_and_rejects_invalid_conversion(self):
        self.proposal('main', queue='main', state='On Deck', number=312)
        prefix = 'Amend Rule 302 by setting the following Arcana Effect:\n\n'
        self.assertFalse(await Voting.validateDeckEdit(self.bot, self.payload(), 'main', prefix + 'The Fool: An unseen card.'))
        self.commit()
        self.assertNotIn('Arcana', self.bot.Data['Queue-Proposals']['main'])
        self.assertTrue(await Voting.validateDeckEdit(self.bot, self.payload(), 'main', prefix + 'Wheel of Fortune: Every active player gains 2 Luck.'))
        self.commit()
        self.assertEqual(self.bot.Data['Queue-Proposals']['main']['Arcana'], 'Wheel of Fortune')
        self.assertEqual(self.bot.Data['Queue-Proposals']['main']['Arcana Effect'], 'Every active player gains 2 Luck.')


if __name__ == '__main__': unittest.main()
