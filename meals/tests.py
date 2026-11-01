import copy
from unittest.mock import patch

import anthropic
import httpx2

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Meal
from .services.ai import FAKE_RESPONSE, AnalysisError, analyze_text, validate


def good_answer():
    return copy.deepcopy(FAKE_RESPONSE)


class ValidateTests(TestCase):
    def test_good_answer_passes(self):
        data = validate(good_answer())
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(len(data['items']), 4)

    def test_grams_rounded_to_5(self):
        answer = good_answer()
        answer['items'][0]['grams'] = 302
        self.assertEqual(validate(answer)['items'][0]['grams'], 300)

    def test_unknown_unit_becomes_serving(self):
        answer = good_answer()
        answer['items'][0]['unit'] = 'bucket'
        self.assertEqual(validate(answer)['items'][0]['unit'], 'serving')

    def test_bad_answers_raise(self):
        def broken(change):
            answer = good_answer()
            change(answer)
            return answer

        cases = {
            'min > max': lambda a: a['items'][0].update(kcal_min=900, kcal_max=100),
            'unknown confidence': lambda a: a['items'][0].update(confidence='maybe'),
            'unsure without reason': lambda a: a['items'][3].update(reason=' '),
            'no items': lambda a: a.update(items=[]),
            'negative number': lambda a: a['items'][0].update(fat_min=-1),
            'text as number': lambda a: a['items'][0].update(grams='300'),
            'unknown status': lambda a: a.update(status='maybe'),
        }
        for label, change in cases.items():
            with self.subTest(label), self.assertRaises(AnalysisError):
                validate(broken(change))

    def test_no_food(self):
        data = validate({'status': 'no_food', 'no_food_reason': 'That looks like a shoe.'})
        self.assertEqual(data['items'], [])
        self.assertEqual(data['no_food_reason'], 'That looks like a shoe.')


@override_settings(ZALAK_AI_FAKE=False)
class AnalyzeTextTests(TestCase):
    @patch('meals.services.ai._ask_model')
    def test_returns_validated_answer(self, ask_model):
        ask_model.return_value = good_answer()
        data = analyze_text('tavče gravče')
        ask_model.assert_called_once_with('tavče gravče')
        self.assertEqual(data['title'], FAKE_RESPONSE['title'])

    @patch('meals.services.ai._ask_model', side_effect=AnalysisError('down'))
    def test_failure_propagates(self, ask_model):
        with self.assertRaises(AnalysisError):
            analyze_text('tavče gravče')

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''})
    def test_missing_key_is_an_analysis_error(self):
        with self.assertRaises(AnalysisError), self.assertLogs('meals.services.ai', 'WARNING'):
            analyze_text('tavče gravče')


class StaticVersionTests(TestCase):
    @override_settings(STATIC_VERSION='42')
    def test_own_css_and_js_carry_the_version(self):
        html = self.client.get(reverse('text_input')).content.decode()
        self.assertIn('css/zalak.css?v=42', html)
        self.assertIn('js/chips.js?v=42', html)
        self.assertIn('js/analyzing.js?v=42', html)


class FakeAITests(TestCase):
    """ZALAK_AI_FAKE answers without the API; ZALAK_AI_FAKE_DELAY makes it wait first."""

    @override_settings(ZALAK_AI_FAKE=True, ZALAK_AI_FAKE_DELAY=4)
    @patch('meals.services.ai.time.sleep')
    def test_fake_waits_for_the_delay(self, sleep):
        data = analyze_text('anything')
        sleep.assert_called_once_with(4)
        self.assertEqual(data['title'], FAKE_RESPONSE['title'])

    @override_settings(ZALAK_AI_FAKE=True, ZALAK_AI_FAKE_DELAY=0)
    @patch('meals.services.ai.time.sleep')
    def test_no_delay_answers_at_once(self, sleep):
        analyze_text('anything')
        sleep.assert_not_called()


@override_settings(ZALAK_AI_FAKE=False)
class TextInputViewTests(TestCase):
    url = reverse('text_input')

    @patch('meals.services.ai._ask_model')
    def test_analysis_redirects_to_result(self, ask_model):
        ask_model.return_value = good_answer()
        response = self.client.post(self.url, {'text': 'tavče gravče, bread', 'slot': 'lunch'})
        meal = Meal.objects.get()
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(meal.items.count(), 4)
        self.assertEqual(meal.status, 'draft')

    @patch('meals.services.ai._ask_model', side_effect=AnalysisError('down'))
    def test_failure_goes_to_error_page_and_keeps_the_text(self, ask_model):
        response = self.client.post(self.url, {'text': 'tavče gravče', 'slot': 'lunch'}, follow=True)
        meal = Meal.objects.get()
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]) + '?why=failed')
        self.assertContains(response, "Couldn't analyze this")
        self.assertContains(response, 'tavče gravče')                # the input is shown (FR29)
        self.assertEqual(meal.text, 'tavče gravče')                   # and kept in the draft

    @patch('meals.services.ai._ask_model', side_effect=AnalysisError('offline', kind='connection'))
    def test_connection_failure_says_so(self, ask_model):
        response = self.client.post(self.url, {'text': 'tavče gravče', 'slot': 'lunch'}, follow=True)
        self.assertContains(response, 'Connection lost')

    @patch('meals.services.ai._ask_model')
    def test_no_food_page(self, ask_model):
        ask_model.return_value = NO_FOOD
        response = self.client.post(self.url, {'text': 'my shoe', 'slot': 'lunch'}, follow=True)
        meal = Meal.objects.get()
        self.assertRedirects(response, reverse('no_food', args=[meal.id]))
        self.assertContains(response, 'That looks like a shoe.')
        self.assertEqual(meal.items.count(), 0)

    @patch('meals.services.ai._ask_model')
    def test_other_session_gets_404(self, ask_model):
        ask_model.return_value = good_answer()
        self.client.post(self.url, {'text': 'tavče gravče', 'slot': 'lunch'})
        meal = Meal.objects.get()

        self.client.cookies.clear()   # a different guest
        response = self.client.get(reverse('result', args=[meal.id]))
        self.assertEqual(response.status_code, 404)


NO_FOOD = {'status': 'no_food', 'no_food_reason': 'That looks like a shoe.',
           'title': '', 'description': '', 'items': []}


@override_settings(ZALAK_AI_FAKE=False)
class RecoveryTests(TestCase):
    """Chunk 6: Try again, Edit the text, and the error / no food pages."""

    def make_failed_draft(self):
        with patch('meals.services.ai._ask_model', side_effect=AnalysisError('down')):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče', 'slot': 'lunch'})
        return Meal.objects.get()

    @patch('meals.services.ai._ask_model')
    def test_try_again_works_on_the_same_draft(self, ask_model):
        meal = self.make_failed_draft()
        ask_model.return_value = good_answer()
        response = self.client.post(reverse('retry', args=[meal.id]))
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(Meal.objects.count(), 1)
        self.assertEqual(meal.items.count(), 4)

    @patch('meals.services.ai._ask_model', side_effect=AnalysisError('down'))
    def test_try_again_can_fail_again(self, ask_model):
        meal = self.make_failed_draft()
        response = self.client.post(reverse('retry', args=[meal.id]))
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]) + '?why=failed')

    @patch('meals.services.ai._ask_model')
    def test_try_again_needs_a_post(self, ask_model):
        meal = self.make_failed_draft()
        response = self.client.get(reverse('retry', args=[meal.id]))
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]))
        ask_model.assert_not_called()

    @patch('meals.services.ai._ask_model')
    def test_edit_the_text_updates_the_same_draft(self, ask_model):
        meal = self.make_failed_draft()
        page = self.client.get(reverse('edit_text', args=[meal.id]))
        self.assertContains(page, 'tavče gravče')                     # the form is prefilled

        ask_model.return_value = good_answer()
        response = self.client.post(reverse('edit_text', args=[meal.id]),
                                    {'text': 'tavče gravče and bread', 'slot': 'lunch'})
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(Meal.objects.count(), 1)
        meal.refresh_from_db()
        self.assertEqual(meal.text, 'tavče gravče and bread')
        ask_model.assert_called_once_with('tavče gravče and bread')

    def test_edit_the_text_of_a_logged_meal_is_404(self):
        meal = self.make_failed_draft()
        Meal.objects.filter(id=meal.id).update(status='logged')
        response = self.client.get(reverse('edit_text', args=[meal.id]))
        self.assertEqual(response.status_code, 404)

    def test_result_of_a_failed_draft_goes_to_error_page(self):
        meal = self.make_failed_draft()
        response = self.client.get(reverse('result', args=[meal.id]))
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]))

    def test_unknown_why_reads_as_failed(self):
        meal = self.make_failed_draft()
        response = self.client.get(reverse('analysis_error', args=[meal.id]) + '?why=<b>')
        self.assertContains(response, "Couldn't analyze this")

    @patch('meals.services.ai._ask_model')
    def test_pages_are_404_for_another_guest(self, ask_model):
        meal = self.make_failed_draft()
        self.client.cookies.clear()   # a different guest
        for name in ('analysis_error', 'no_food', 'edit_text', 'retry'):
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name, args=[meal.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('retry', args=[meal.id])).status_code, 404)
        ask_model.assert_not_called()


@override_settings(ZALAK_AI_FAKE=False)
@patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
class AskModelErrorTests(TestCase):
    """The SDK's errors become AnalysisError with the right kind (the client is patched)."""

    def call_with(self, error):
        with patch('meals.services.ai.anthropic.Anthropic') as client_class, \
                self.assertLogs('meals.services.ai', 'WARNING'):
            client_class.return_value.messages.create.side_effect = error
            with self.assertRaises(AnalysisError) as caught:
                analyze_text('tavče gravče')
        return caught.exception

    def test_connection_error(self):
        request = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
        self.assertEqual(self.call_with(anthropic.APIConnectionError(request=request)).kind, 'connection')

    def test_timeout_is_a_connection_error(self):
        request = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
        self.assertEqual(self.call_with(anthropic.APITimeoutError(request=request)).kind, 'connection')

    def test_other_api_error(self):
        request = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
        response = httpx2.Response(401, request=request)
        error = anthropic.AuthenticationError('bad key', response=response, body=None)
        self.assertEqual(self.call_with(error).kind, 'failed')
