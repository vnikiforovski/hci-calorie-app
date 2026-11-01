import copy
from unittest.mock import patch

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
    def test_failure_keeps_the_text(self, ask_model):
        response = self.client.post(self.url, {'text': 'tavče gravče', 'slot': 'lunch'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "couldn&#x27;t analyze")
        self.assertContains(response, 'tavče gravče')
        self.assertEqual(Meal.objects.get().text, 'tavče gravče')   # the draft keeps the input (FR29)

    @patch('meals.services.ai._ask_model')
    def test_no_food_message(self, ask_model):
        ask_model.return_value = {'status': 'no_food', 'no_food_reason': 'That looks like a shoe.',
                                  'title': '', 'description': '', 'items': []}
        response = self.client.post(self.url, {'text': 'my shoe', 'slot': 'lunch'})
        self.assertContains(response, 'That looks like a shoe.')

    @patch('meals.services.ai._ask_model')
    def test_other_session_gets_404(self, ask_model):
        ask_model.return_value = good_answer()
        self.client.post(self.url, {'text': 'tavče gravče', 'slot': 'lunch'})
        meal = Meal.objects.get()

        self.client.cookies.clear()   # a different guest
        response = self.client.get(reverse('result', args=[meal.id]))
        self.assertEqual(response.status_code, 404)
