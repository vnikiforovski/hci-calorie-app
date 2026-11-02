import copy
from datetime import datetime, timedelta
from decimal import Decimal
import os
import shutil
import tempfile
from io import BytesIO
from unittest.mock import patch

import anthropic
import httpx2

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image
from django.urls import reverse
from django.utils import timezone

from .admin import MealAdmin
from .models import Meal, Profile, slot_for_time
from .services.ai import (FAKE_RESPONSE, ITEM_RESPONSE_SCHEMA, AnalysisError, analyze_text, estimate_item,
                          validate)
from .units import format_amount, grams_for, stepper_label
from zalak.settings import env_list


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
        self.assertIn('js/voice.js?v=42', html)


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
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]) + '?why=failed&fresh=1')
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
        self.assertRedirects(response, reverse('no_food', args=[meal.id]) + '?fresh=1')
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


@override_settings(ZALAK_AI_FAKE=False)
class VoiceInputTests(TestCase):
    """Chunk 7: dictated text goes the same way as typed text, only input_method differs."""
    url = reverse('text_input')

    def post(self, **extra):
        data = {'text': 'two eggs and toast', 'slot': 'breakfast', **extra}
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            return self.client.post(self.url, data)

    def test_dictated_meal_is_saved_as_voice(self):
        response = self.post(input_method='voice')
        meal = Meal.objects.get()
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(meal.input_method, 'voice')

    def test_typed_meal_is_saved_as_text(self):
        self.post()
        self.assertEqual(Meal.objects.get().input_method, 'text')

    def test_other_values_count_as_text(self):
        # This page makes only text and voice meals; an odd value never blocks the form
        for value in ['photo', 'junk']:
            response = self.post(input_method=value)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(set(Meal.objects.values_list('input_method', flat=True)), {'text'})

    def test_edit_the_text_keeps_voice(self):
        self.post(input_method='voice')
        meal = Meal.objects.get()
        page = self.client.get(reverse('edit_text', args=[meal.id]))
        self.assertContains(page, 'name="input_method" value="voice"')

    def test_mic_is_hidden_until_the_browser_supports_it(self):
        page = self.client.get(self.url)
        self.assertContains(page, '<div class="z-voice" id="voice" hidden>', html=False)
        self.assertContains(page, 'id="micButton"')
        self.assertContains(page, 'js/voice.js?v=')


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
        self.assertRedirects(response, reverse('analysis_error', args=[meal.id]) + '?why=failed&fresh=1')

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


def jpeg(name='plate.jpg', size=(40, 30)):
    """A small real JPEG, as a phone would upload it."""
    buffer = BytesIO()
    Image.new('RGB', size, (200, 120, 60)).save(buffer, 'JPEG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')


class SeenTests(TestCase):
    def test_seen_is_cleaned_and_capped(self):
        data = validate({'status': 'no_food', 'no_food_reason': 'Too dark.',
                         'seen': [' a dark room ', 'part of a table', '', 'a lamp', 'a cat', 7]})
        self.assertEqual(data['seen'], ['a dark room', 'part of a table', 'a lamp'])

    def test_missing_seen_is_empty(self):
        self.assertEqual(validate(good_answer() | {'seen': 'oops'})['seen'], [])


@override_settings(ZALAK_AI_FAKE=False)
class PhotoInputTests(TestCase):
    """Chunk 8: photo + note, the photo error pages, Take another photo and Describe it instead."""
    url = reverse('photo_input')

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        settings_override = override_settings(MEDIA_ROOT=media)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def post(self, url=None, answer=None, **data):
        data.setdefault('slot', 'lunch')
        with patch('meals.services.ai._ask_model', return_value=answer or good_answer()) as ask_model:
            response = self.client.post(url or self.url, data)
        return response, ask_model

    def test_page_loads(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'Looking at your photo')
        self.assertContains(response, 'js/photo.js?v=')
        self.assertContains(response, 'js/photo_tips.js?v=')
        self.assertContains(response, '<video id="cameraVideo"')

    def test_photo_and_note_go_to_the_ai_together(self):
        response, ask_model = self.post(photo=jpeg(), text='cooked in butter')
        meal = Meal.objects.get()
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(meal.input_method, 'photo')
        self.assertEqual(meal.text, 'cooked in butter')
        self.assertTrue(meal.photo.name.endswith('.jpg'))

        image, note = ask_model.call_args.args[0]
        self.assertEqual(image['type'], 'image')
        self.assertEqual(image['source']['media_type'], 'image/jpeg')
        self.assertEqual(note, {'type': 'text', 'text': 'Note: cooked in butter'})

        result = self.client.get(reverse('result', args=[meal.id]))
        self.assertContains(result, meal.photo.url)

    def test_big_photo_is_shrunk(self):
        self.post(photo=jpeg(size=(3000, 2000)))
        with Image.open(Meal.objects.get().photo.path) as image:
            self.assertEqual(image.size, (1568, 1045))

    def test_not_an_image_is_refused_calmly(self):
        bad = SimpleUploadedFile('menu.txt', b'not a photo', content_type='text/plain')
        response, ask_model = self.post(photo=bad)
        self.assertContains(response, "Zalak can&#x27;t read that file. Try another photo.")
        self.assertFalse(Meal.objects.exists())
        ask_model.assert_not_called()

    def test_no_photo_is_refused(self):
        response, ask_model = self.post(text='just a note')
        self.assertContains(response, 'Take or choose a photo first.')
        self.assertFalse(Meal.objects.exists())

    def test_try_again_sends_the_photo_again(self):
        with patch('meals.services.ai._ask_model', side_effect=AnalysisError('down')):
            self.client.post(self.url, {'photo': jpeg(), 'slot': 'lunch'})
        meal = Meal.objects.get()
        page = self.client.get(reverse('analysis_error', args=[meal.id]))
        self.assertContains(page, 'Describe it instead')
        self.assertContains(page, 'Looking at your photo')

        response, ask_model = self.post(url=reverse('retry', args=[meal.id]))
        self.assertRedirects(response, reverse('result', args=[meal.id]))
        self.assertEqual(ask_model.call_args.args[0][0]['type'], 'image')

    def test_photo_no_food_page(self):
        no_food = NO_FOOD | {'no_food_reason': 'The photo looks too dark to see a plate.',
                             'seen': ['a dark room', 'part of a table']}
        self.post(photo=jpeg(), answer=no_food)
        meal = Meal.objects.get()
        page = self.client.get(reverse('no_food', args=[meal.id]))
        self.assertContains(page, 'a dark room')
        self.assertContains(page, 'For the next photo')
        self.assertContains(page, reverse('edit_photo', args=[meal.id]))
        self.assertContains(page, 'Describe it instead')

    def test_take_another_photo_replaces_the_file(self):
        self.post(photo=jpeg(), answer=NO_FOOD)
        meal = Meal.objects.get()
        old_photo = meal.photo.name

        self.post(url=reverse('edit_photo', args=[meal.id]), photo=jpeg('second.jpg'))
        meal.refresh_from_db()
        self.assertEqual(Meal.objects.count(), 1)              # the same draft
        self.assertNotEqual(meal.photo.name, old_photo)
        self.assertFalse(meal.photo.storage.exists(old_photo))  # no orphan file

    def test_describe_it_instead_makes_a_text_meal(self):
        self.post(photo=jpeg(), answer=NO_FOOD)
        meal = Meal.objects.get()
        photo_name = meal.photo.name

        with patch('meals.services.ai._ask_model', return_value=good_answer()) as ask_model:
            self.client.post(reverse('edit_text', args=[meal.id]),
                             {'text': 'tavče gravče and bread', 'slot': 'lunch'})
        meal.refresh_from_db()
        self.assertEqual(meal.input_method, 'text')
        self.assertFalse(meal.photo)
        self.assertFalse(meal.photo.storage.exists(photo_name))
        self.assertEqual(ask_model.call_args.args[0], 'tavče gravče and bread')

    def test_another_guest_gets_404(self):
        self.post(photo=jpeg(), answer=NO_FOOD)
        meal = Meal.objects.get()
        self.client.cookies.clear()
        response = self.client.get(reverse('edit_photo', args=[meal.id]))
        self.assertEqual(response.status_code, 404)


class PhotoTipsTests(TestCase):
    """Chunk 8b: the tips open by themselves until "Don't show these tips again"."""
    page = reverse('photo_input')
    seen = reverse('photo_tips_seen')

    def test_guest_choice_is_kept_in_the_session(self):
        self.assertContains(self.client.get(self.page), 'data-auto-open')
        response = self.client.post(self.seen)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(self.client.session['seen_photo_tips'])
        self.assertNotContains(self.client.get(self.page), 'data-auto-open')

    def test_signed_in_choice_is_kept_in_the_profile(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(user)
        self.assertContains(self.client.get(self.page), 'data-auto-open')

        self.client.post(self.seen)   # no Profile yet (the signal comes in chunk 12): it is created
        self.assertTrue(Profile.objects.get(user=user).seen_photo_tips)
        self.assertNotContains(self.client.get(self.page), 'data-auto-open')

    def test_only_a_post_stores_it(self):
        self.assertEqual(self.client.get(self.seen).status_code, 405)


class EnvListTests(TestCase):
    """Chunk 8b: ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS take extra values from .env."""

    def test_defaults_alone(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(env_list('HOSTS', ['localhost']), ['localhost'])

    def test_extras_are_added_and_trimmed(self):
        with patch.dict('os.environ', {'HOSTS': ' 192.168.1.183 , ,example.com'}):
            self.assertEqual(env_list('HOSTS', ['localhost']),
                             ['localhost', '192.168.1.183', 'example.com'])

    def test_no_duplicates(self):
        with patch.dict('os.environ', {'HOSTS': 'localhost,127.0.0.1'}):
            self.assertEqual(env_list('HOSTS', ['localhost', '127.0.0.1']), ['localhost', '127.0.0.1'])


def make_draft(user=None, session_key='', **fields):
    """A draft with one item (chicken, 150 g), as an analysis would leave it."""
    meal = Meal.objects.create(user=user, session_key=session_key, input_method='text',
                               text='chicken', title='Chicken', **fields)
    meal.items.create(name='Chicken breast', unit='g', grams=150,
                      kcal_min_100g=150, kcal_max_100g=170,
                      protein_min_100g=28, protein_max_100g=31,
                      carbs_min_100g=0, carbs_max_100g=0,
                      fat_min_100g=3, fat_max_100g=4, confidence='sure')
    return meal


def use_temp_media(test):
    """Point MEDIA_ROOT to a temporary folder for one test, so photos don't land in media/."""
    media = tempfile.mkdtemp()
    test.addCleanup(shutil.rmtree, media, ignore_errors=True)
    settings_override = override_settings(MEDIA_ROOT=media)
    settings_override.enable()
    test.addCleanup(settings_override.disable)


class SignalTests(TestCase):
    """Chunk 9: the slot from the time, the meals_logged counter and the photo cleanup."""

    def setUp(self):
        use_temp_media(self)
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')

    def counter(self):
        return Profile.objects.get(user=self.user).meals_logged

    def test_empty_slot_is_filled_from_the_time(self):
        eaten_at = timezone.make_aware(datetime(2026, 11, 1, 13, 0))
        meal = make_draft(self.user, eaten_at=eaten_at)
        self.assertEqual(meal.slot, 'lunch')

    def test_chosen_slot_is_kept(self):
        eaten_at = timezone.make_aware(datetime(2026, 11, 1, 13, 0))
        meal = make_draft(self.user, eaten_at=eaten_at, slot='snack')
        self.assertEqual(meal.slot, 'snack')

    def test_logging_counts_once(self):
        meal = make_draft(self.user)
        meal.status = 'logged'
        meal.save()
        self.assertEqual(self.counter(), 1)

        meal.title = 'Grilled chicken'   # saving a logged meal again doesn't count
        meal.save()
        self.assertEqual(self.counter(), 1)

    def test_a_draft_does_not_count(self):
        make_draft(self.user).save()
        self.assertFalse(Profile.objects.filter(user=self.user, meals_logged__gt=0).exists())

    def test_undo_takes_it_off_again(self):
        meal = make_draft(self.user)
        for status in ['logged', 'draft', 'logged']:   # log, undo, log
            meal.status = status
            meal.save()
        self.assertEqual(self.counter(), 1)

    def test_logging_from_the_admin_counts(self):
        superuser = User.objects.create_superuser('admin', password='a-long-password')
        request = RequestFactory().post('/admin/')
        request.user = superuser

        meal = make_draft(self.user)
        meal.status = 'logged'
        MealAdmin(Meal, admin.site).save_model(request, meal, form=None, change=True)
        self.assertEqual(self.counter(), 1)

    def test_a_guest_meal_has_no_counter(self):
        meal = make_draft(session_key='guest-session')
        meal.status = 'logged'
        meal.save()
        # Ana's Profile exists (made by the User signal) but nobody's counter moved
        self.assertEqual(Profile.objects.count(), 1)
        self.assertEqual(self.counter(), 0)

    def test_deleting_a_meal_removes_its_photo(self):
        meal = make_draft(self.user, photo=jpeg())
        path = meal.photo.name
        self.assertTrue(meal.photo.storage.exists(path))
        meal.delete()
        self.assertFalse(meal.photo.storage.exists(path))

    def test_bulk_delete_removes_photos_too(self):
        # The admin's "Delete selected meals" deletes a queryset
        meal = make_draft(self.user, photo=jpeg())
        path = meal.photo.name
        Meal.objects.filter(pk=meal.pk).delete()
        self.assertFalse(meal.photo.storage.exists(path))


class LogTests(TestCase):
    """Chunk 9: Log, the toast with Undo, and Just checking."""

    def setUp(self):
        use_temp_media(self)
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.meal = make_draft(self.user, slot='lunch')

    def log(self, **data):
        return self.client.post(reverse('log_meal', args=[self.meal.id]), data)

    def test_result_has_working_buttons(self):
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertContains(page, f'action="{reverse("log_meal", args=[self.meal.id])}"')
        self.assertContains(page, f'action="{reverse("just_checking", args=[self.meal.id])}"')
        self.assertContains(page, 'form="logForm"')
        self.assertContains(page, 'id="logButton">')   # active, not disabled

    def test_log_saves_and_goes_home(self):
        response = self.log(slot='lunch')
        self.assertRedirects(response, reverse('home'))
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.status, 'logged')
        self.assertEqual(Profile.objects.get(user=self.user).meals_logged, 1)

    def test_log_uses_the_chosen_slot(self):
        self.log(slot='dinner')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.slot, 'dinner')

    def test_an_odd_slot_keeps_the_old_one(self):
        self.log(slot='brunch')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.slot, 'lunch')

    def test_toast_shows_once_on_home(self):
        home = self.client.get(self.log(slot='dinner').url)
        self.assertContains(home, 'Logged to dinner')
        self.assertContains(home, reverse('undo_log', args=[self.meal.id]))
        self.assertContains(home, 'js/toast.js?v=')
        self.assertContains(home, 'Chicken')   # the meal is in the temporary list

        again = self.client.get(reverse('home'))
        self.assertNotContains(again, 'Logged to dinner')
        self.assertNotContains(again, 'js/toast.js')

    def test_undo_makes_it_a_draft_again(self):
        self.log(slot='lunch')
        response = self.client.post(reverse('undo_log', args=[self.meal.id]))
        self.assertRedirects(response, reverse('result', args=[self.meal.id]))
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.status, 'draft')
        self.assertEqual(Profile.objects.get(user=self.user).meals_logged, 0)

    def test_undo_of_a_draft_is_404(self):
        response = self.client.post(reverse('undo_log', args=[self.meal.id]))
        self.assertEqual(response.status_code, 404)

    def test_logging_twice_is_404(self):
        self.log(slot='lunch')
        self.assertEqual(self.log(slot='lunch').status_code, 404)
        self.assertEqual(Profile.objects.get(user=self.user).meals_logged, 1)

    def test_logged_meal_opens_meal_detail_without_log(self):
        # Chunk 15: the same URL shows Meal detail once the meal is logged
        self.log(slot='lunch')
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertTemplateUsed(page, 'meals/meal_detail.html')
        self.assertNotContains(page, reverse('log_meal', args=[self.meal.id]))

    def test_only_posts_change_anything(self):
        for name in ['log_meal', 'undo_log', 'just_checking']:
            with self.subTest(name):
                response = self.client.get(reverse(name, args=[self.meal.id]))
                self.assertEqual(response.status_code, 405)

    def test_another_users_meal_is_404(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        theirs = make_draft(other)
        for name in ['log_meal', 'just_checking']:
            with self.subTest(name):
                response = self.client.post(reverse(name, args=[theirs.id]))
                self.assertEqual(response.status_code, 404)
        self.assertTrue(Meal.objects.filter(pk=theirs.pk, status='draft').exists())

    def test_just_checking_deletes_the_draft_and_photo(self):
        meal = make_draft(self.user, photo=jpeg())
        path = meal.photo.name
        response = self.client.post(reverse('just_checking', args=[meal.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(Meal.objects.filter(pk=meal.pk).exists())
        self.assertFalse(meal.photo.storage.exists(path))

    def test_just_checking_a_logged_meal_is_404(self):
        self.log(slot='lunch')
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertEqual(response.status_code, 404)


@override_settings(ZALAK_AI_FAKE=False)
class GuestLogTests(TestCase):
    """Chunk 9: a guest can use Just checking. Chunk 13: a guest's Log opens "Keep this meal?"."""

    def setUp(self):
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče', 'slot': 'lunch'})
        self.meal = Meal.objects.get()

    def test_log_opens_the_keep_sheet_for_a_guest(self):
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertContains(page, 'data-bs-target="#guestSheet"')
        self.assertContains(page, 'id="guestSheet"')
        self.assertContains(page, 'Keep this meal?')
        self.assertNotContains(page, 'id="logButton" disabled')

    def test_a_signed_in_user_gets_no_sheet(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        meal = make_draft(user=user)
        self.client.force_login(user)
        page = self.client.get(reverse('result', args=[meal.id]))
        self.assertNotContains(page, 'id="guestSheet"')

    def test_guest_just_checking(self):
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(Meal.objects.exists())

    def test_another_guest_cannot_discard_it(self):
        self.client.cookies.clear()
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertEqual(response.status_code, 404)


class GuestFlowTests(TestCase):
    """Chunk 13 (T7): a guest checks a meal, taps Log, makes an account or signs in,
    and the same meal is logged, counted once."""

    def setUp(self):
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče', 'slot': 'lunch'})
        self.meal = Meal.objects.get()

    def keep(self, then='signup', slot='dinner'):
        return self.client.post(reverse('log_meal', args=[self.meal.id]), {'slot': slot, 'then': then})

    def sign_up(self):
        return self.client.post(reverse('signup'), {
            'first_name': 'Ana', 'email': 'ana@example.com', 'password': 'tavce-gravce-42', 'agree': 'on'})

    def test_create_account_keeps_the_draft_in_the_chosen_slot(self):
        response = self.keep()
        self.assertRedirects(response, reverse('signup'))
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.status, 'draft')   # nothing is logged before the account exists
        self.assertEqual(self.meal.slot, 'dinner')
        self.assertEqual(self.client.session['guest_meal']['id'], self.meal.id)

    def test_sign_in_from_the_sheet_goes_to_sign_in(self):
        self.assertRedirects(self.keep(then='sign_in'), reverse('sign_in'))

    def test_sign_up_and_sign_in_say_the_meal_is_waiting(self):
        self.keep()
        line = 'Your meal will be logged to dinner once you'
        self.assertContains(self.client.get(reverse('signup')), line)
        self.assertContains(self.client.get(reverse('sign_in')), line)

    def test_no_waiting_line_without_a_kept_meal(self):
        self.assertNotContains(self.client.get(reverse('signup')), 'Your meal will be logged')

    def test_sign_up_logs_the_meal_and_counts_it_once(self):
        self.keep()
        self.assertRedirects(self.sign_up(), reverse('signup_details'))
        user = User.objects.get(email='ana@example.com')
        self.meal.refresh_from_db()
        # Logged at step 1 already, so it is safe even if step 2 is never finished
        self.assertEqual(self.meal.user, user)
        self.assertEqual(self.meal.status, 'logged')
        self.assertEqual(self.meal.session_key, '')
        self.assertEqual(self.meal.slot, 'dinner')
        self.assertEqual(user.profile.meals_logged, 1)

        home = self.client.post(reverse('signup_details'), {'skip': ''}, follow=True)
        self.assertContains(home, 'Welcome to Zalak, Ana · Logged to dinner')
        self.assertContains(home, reverse('undo_log', args=[self.meal.id]))
        self.assertNotIn('guest_meal', self.client.session)

    def test_sign_in_logs_the_meal_with_a_toast(self):
        user = User.objects.create_user('ana@example.com', email='ana@example.com', password='tavce-gravce-42')
        self.keep(then='sign_in')
        home = self.client.post(reverse('sign_in'),
                                {'username': 'ana@example.com', 'password': 'tavce-gravce-42'}, follow=True)
        self.assertContains(home, 'Logged to dinner')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.user, user)
        self.assertEqual(self.meal.status, 'logged')
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.meals_logged, 1)

    def test_undo_after_keeping_brings_the_users_draft_back(self):
        self.keep()
        self.sign_up()
        self.client.post(reverse('undo_log', args=[self.meal.id]))
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.status, 'draft')
        self.assertEqual(Profile.objects.get(user=self.meal.user).meals_logged, 0)

    def test_another_guests_meal_is_never_claimed(self):
        other = make_draft(session_key='someone-else')
        self.keep()
        session = self.client.session
        session['guest_meal'] = {'id': other.id, 'session_key': session.session_key, 'slot': 'lunch'}
        session.save()
        self.sign_up()
        other.refresh_from_db()
        self.assertIsNone(other.user)
        self.assertEqual(other.status, 'draft')

    def test_signing_in_without_a_kept_meal_changes_nothing(self):
        self.sign_up()
        self.meal.refresh_from_db()
        self.assertIsNone(self.meal.user)
        self.assertEqual(self.meal.status, 'draft')

    def test_not_now_discards_the_meal(self):
        self.keep()
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(Meal.objects.exists())
        self.assertNotIn('guest_meal', self.client.session)

    def test_another_guest_cannot_keep_it(self):
        self.client.cookies.clear()
        self.assertEqual(self.keep().status_code, 404)


class GuestDraftCleanupTests(TestCase):
    """Chunk 13: each new draft deletes guest drafts older than 24 h."""

    def backdate(self, meal, hours):
        # created_at is auto_now_add, so only update() can move it
        Meal.objects.filter(id=meal.id).update(created_at=timezone.now() - timedelta(hours=hours))

    def new_draft(self):
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče', 'slot': 'lunch'})

    def test_old_guest_drafts_go_and_the_rest_stay(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        old_guest = make_draft(session_key='old')
        recent_guest = make_draft(session_key='recent')
        old_user_draft = make_draft(user=user)
        old_logged = make_draft(user=user, status='logged')
        self.backdate(old_guest, 25)
        self.backdate(recent_guest, 23)
        self.backdate(old_user_draft, 48)
        self.backdate(old_logged, 48)

        self.new_draft()

        self.assertFalse(Meal.objects.filter(id=old_guest.id).exists())
        for meal in (recent_guest, old_user_draft, old_logged):
            self.assertTrue(Meal.objects.filter(id=meal.id).exists())
        self.assertEqual(Meal.objects.count(), 4)   # the three kept + the new one

    def test_an_old_guest_photo_file_is_removed(self):
        use_temp_media(self)
        meal = make_draft(session_key='old')
        meal.photo.save('plate.jpg', SimpleUploadedFile('plate.jpg', b'not really a jpeg'))
        path = meal.photo.path
        self.assertTrue(os.path.exists(path))
        self.backdate(meal, 30)
        self.new_draft()
        self.assertFalse(os.path.exists(path))


class UnitMathsTests(TestCase):
    """Chunk 10: the grams rule shared by Save changes and portion.js."""

    def test_same_unit_keeps_the_items_own_grams_per_unit(self):
        # The AI's 2 slices are 80 g, so 3 slices are 120 g, not the table's 90 g
        self.assertEqual(grams_for(Decimal('3'), 'slice', [(2, 'slice', 80)]), 120)

    def test_first_known_portion_wins(self):
        # The AI's portion comes first, so small edits don't drift through rounding
        self.assertEqual(grams_for(Decimal('2'), 'slice', [(1, 'slice', 40), (1, 'slice', 30)]), 80)

    def test_a_new_unit_uses_the_table(self):
        self.assertEqual(grams_for(Decimal('1'), 'bowl_l', [(1, 'bowl_m', 350)]), 450)
        self.assertEqual(grams_for(Decimal('0.3'), 'kg', [(150, 'g', 150)]), 300)

    def test_weight_units_always_use_the_table(self):
        # An odd saved portion ("1 g · 150 g") can't make 200 g into 30 kg
        self.assertEqual(grams_for(Decimal('200'), 'g', [(1, 'g', 150)]), 200)

    def test_rounded_to_5_and_at_least_5(self):
        self.assertEqual(grams_for(Decimal('1.5'), 'oz'), 45)     # 42.5 g
        self.assertEqual(grams_for(Decimal('1'), 'pinch'), 5)     # 0.5 g

    def test_format_amount(self):
        cases = {'1.50': '1½', '0.25': '¼', '0.75': '¾', '2.00': '2', '0.30': '0.3', '150': '150'}
        for value, text in cases.items():
            with self.subTest(value):
                self.assertEqual(format_amount(Decimal(value)), text)

    def test_stepper_label(self):
        self.assertEqual(stepper_label('bowl_m', 1), 'medium bowl')
        self.assertEqual(stepper_label('bowl_m', Decimal('1.5')), 'medium bowls')
        self.assertEqual(stepper_label('pinch', 2), 'pinches')
        self.assertEqual(stepper_label('tbsp', 2), 'tbsp')

    def test_portion_on_result(self):
        meal = make_draft()
        item = meal.items.get()
        item.amount, item.unit, item.grams = Decimal('1.5'), 'slice', 45
        self.assertEqual(item.portion, '1½ slices · 45 g')
        item.amount, item.unit, item.grams = Decimal('2'), 'tbsp', 30
        self.assertEqual(item.portion, '2 tbsp · 30 g')


class EditItemTests(TestCase):
    """Chunk 10: Edit item. Chicken is 150 g at 150–170 kcal and 28–31 g protein per 100 g."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.meal = make_draft(self.user, slot='lunch')
        self.item = self.meal.items.get()

    def url(self, item=None, meal=None):
        item = item or self.item
        return reverse('edit_item', args=[(meal or self.meal).id, item.id])

    def save(self, **data):
        data = {'name': 'Chicken breast', 'amount': '150', 'unit': 'g', **data}
        return self.client.post(self.url(), data)

    def add_bread(self):
        return self.meal.items.create(name='Bread', amount=2, unit='slice', grams=60, position=1,
                                      kcal_min_100g=250, kcal_max_100g=280,
                                      protein_min_100g=8, protein_max_100g=9,
                                      carbs_min_100g=48, carbs_max_100g=50,
                                      fat_min_100g=3, fat_max_100g=4, confidence='sure')

    def test_result_pencil_opens_edit_item(self):
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertContains(page, f'href="{self.url()}"')

    def test_page_loads(self):
        page = self.client.get(self.url())
        self.assertContains(page, 'Edit item')
        self.assertContains(page, 'value="Chicken breast"')
        self.assertContains(page, 'id="portionData"')
        self.assertContains(page, 'js/portion.js?v=')
        self.assertContains(page, 'id="unitSheet"')
        self.assertContains(page, '230–260')                  # kcal for 150 g
        self.assertNotContains(page, 'id="resetButton"')      # no AI answer behind this item
        self.assertContains(page, 'This is the only item.')   # so no Delete

    def test_nutrition_is_open_and_there_is_no_unit_row(self):
        page = self.client.get(self.url())
        self.assertContains(page, 'Nutrition for this portion')
        self.assertContains(page, '42–47')                    # protein for 150 g, visible at once
        self.assertNotContains(page, 'data-bs-toggle="collapse"')
        self.assertNotContains(page, 'id="unitRowText"')      # the chip under the number changes the unit
        self.assertContains(page, 'data-bs-target="#unitSheet"', count=1)

    def test_more_chicken_updates_result(self):
        # The chunk's test: 150 g -> 200 g, protein follows (T2)
        response = self.save(amount='200')
        result_url = reverse('result', args=[self.meal.id])
        self.assertRedirects(response, f'{result_url}#item-{self.item.id}', fetch_redirect_response=False)
        self.item.refresh_from_db()
        self.assertEqual(self.item.grams, 200)
        self.assertTrue(self.item.edited_by_user)

        result = self.client.get(result_url)
        self.assertContains(result, '300–340')     # kcal
        self.assertContains(result, '56–62 g')     # protein
        self.assertContains(result, 'Changes saved')

    def test_rename_keeps_the_numbers(self):
        self.save(name='  Turkey breast  ')
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Turkey breast')
        self.assertEqual(self.item.grams, 150)
        self.assertEqual(self.item.kcal_min_100g, 150)
        self.assertEqual(self.item.kcal_max_100g, 170)

    def test_new_unit_uses_the_table(self):
        self.save(amount='1', unit='piece')
        self.item.refresh_from_db()
        self.assertEqual((self.item.amount, self.item.unit, self.item.grams), (1, 'piece', 100))

    def test_grams_never_come_from_the_browser(self):
        self.save(amount='200', grams='999')
        self.item.refresh_from_db()
        self.assertEqual(self.item.grams, 200)

    def test_bad_input_is_explained(self):
        cases = {
            'zero amount': ({'amount': '0'}, 'The amount must be more than 0.'),
            'empty name': ({'name': '   '}, 'Write what the food is'),
            'too much': ({'amount': '6000'}, 'more than 5 kg'),
        }
        for label, (data, message) in cases.items():
            with self.subTest(label):
                response = self.save(**data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self.item.refresh_from_db()
        self.assertEqual(self.item.grams, 150)

    def test_another_users_item_is_404(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        theirs = make_draft(other)
        response = self.client.get(self.url(item=theirs.items.get(), meal=theirs))
        self.assertEqual(response.status_code, 404)

    def test_item_from_another_meal_is_404(self):
        second = make_draft(self.user)
        response = self.client.get(self.url(item=second.items.get(), meal=self.meal))
        self.assertEqual(response.status_code, 404)

    def test_logged_meal_items_can_be_edited(self):
        self.meal.status = 'logged'
        self.meal.save()
        self.save(amount='200')
        self.item.refresh_from_db()
        self.meal.refresh_from_db()
        self.assertEqual(self.item.grams, 200)
        self.assertEqual(self.meal.status, 'logged')
        self.assertEqual(Profile.objects.get(user=self.user).meals_logged, 1)   # counted once

    def test_delete_item(self):
        bread = self.add_bread()
        page = self.client.get(self.url(item=bread))
        delete_url = reverse('delete_item', args=[self.meal.id, bread.id])
        self.assertContains(page, f'action="{delete_url}"')

        response = self.client.post(delete_url)
        self.assertRedirects(response, reverse('result', args=[self.meal.id]), fetch_redirect_response=False)
        self.assertFalse(self.meal.items.filter(pk=bread.pk).exists())
        self.assertContains(self.client.get(response.url), 'Bread removed')

    def test_last_item_stays(self):
        response = self.client.post(reverse('delete_item', args=[self.meal.id, self.item.id]))
        self.assertRedirects(response, self.url())
        self.assertTrue(self.meal.items.filter(pk=self.item.pk).exists())

    def test_delete_needs_a_post(self):
        bread = self.add_bread()
        response = self.client.get(reverse('delete_item', args=[self.meal.id, bread.id]))
        self.assertEqual(response.status_code, 405)


class UndoRemoveItemTests(TestCase):
    """Undo after Delete item: the item comes back exactly as it was."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.meal = make_draft(self.user, slot='lunch')
        self.bread = self.meal.items.create(
            name='Bread', amount=Decimal('1.5'), unit='slice', grams=45, position=1,
            kcal_min_100g=250, kcal_max_100g=280, protein_min_100g=Decimal('8.5'), protein_max_100g=9,
            carbs_min_100g=48, carbs_max_100g=50, fat_min_100g=3, fat_max_100g=4,
            confidence='unsure', reason='Hard to see the slices.', question='How many?',
            edited_by_user=True)
        self.undo_url = reverse('undo_remove_item', args=[self.meal.id])

    def remove_bread(self):
        return self.client.post(reverse('delete_item', args=[self.meal.id, self.bread.id]))

    def test_toast_offers_undo(self):
        result = self.client.get(self.remove_bread().url)
        self.assertContains(result, 'Bread removed')
        self.assertContains(result, f'action="{self.undo_url}"')

    def test_undo_brings_it_back_as_it_was(self):
        totals = (self.meal.kcal_min, self.meal.kcal_max)
        self.remove_bread()
        response = self.client.post(self.undo_url)
        self.assertRedirects(response, reverse('result', args=[self.meal.id]))

        bread = self.meal.items.get(name='Bread')
        self.assertEqual((bread.amount, bread.unit, bread.grams, bread.position), (Decimal('1.5'), 'slice', 45, 1))
        self.assertEqual(bread.protein_min_100g, Decimal('8.5'))
        self.assertEqual((bread.confidence, bread.reason, bread.question), ('unsure', 'Hard to see the slices.', 'How many?'))
        self.assertTrue(bread.edited_by_user)
        self.assertEqual(list(self.meal.items.values_list('name', flat=True)), ['Chicken breast', 'Bread'])
        self.assertEqual((self.meal.kcal_min, self.meal.kcal_max), totals)

    def test_undo_works_once(self):
        self.remove_bread()
        self.client.post(self.undo_url)
        self.client.post(self.undo_url)
        self.assertEqual(self.meal.items.filter(name='Bread').count(), 1)

    def test_undo_without_a_removal_does_nothing(self):
        response = self.client.post(self.undo_url)
        self.assertRedirects(response, reverse('result', args=[self.meal.id]))
        self.assertEqual(self.meal.items.count(), 2)

    def test_undo_on_another_meal_does_nothing(self):
        other_meal = make_draft(self.user)
        self.remove_bread()
        self.client.post(reverse('undo_remove_item', args=[other_meal.id]))
        self.assertEqual(other_meal.items.count(), 1)              # nothing landed there
        self.client.post(self.undo_url)
        self.assertTrue(self.meal.items.filter(name='Bread').exists())   # still waiting for its own meal

    def test_another_users_meal_is_404(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        theirs = make_draft(other)
        response = self.client.post(reverse('undo_remove_item', args=[theirs.id]))
        self.assertEqual(response.status_code, 404)

    def test_undo_needs_a_post(self):
        self.remove_bread()
        self.assertEqual(self.client.get(self.undo_url).status_code, 405)
        self.assertFalse(self.meal.items.filter(name='Bread').exists())

    def test_result_cards_have_no_delete_button(self):
        # Removing an item stays one level down, on Edit item (Figma's card has only the pencil)
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertNotContains(page, reverse('delete_item', args=[self.meal.id, self.bread.id]))
        self.assertContains(page, 'aria-label="Edit Bread"')


@override_settings(ZALAK_AI_FAKE=False)
class EditAIItemTests(TestCase):
    """Chunk 10: items with an AI answer behind them scale by the AI's grams and can be Reset."""

    def setUp(self):
        answer = good_answer()
        answer['items'][1].update(grams=80)   # the AI's 2 slices of bread weigh 80 g
        with patch('meals.services.ai._ask_model', return_value=answer):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče, bread', 'slot': 'lunch'})
        self.meal = Meal.objects.get()
        self.bread = self.meal.items.get(name='White bread')
        self.url = reverse('edit_item', args=[self.meal.id, self.bread.id])

    def test_reset_is_offered_with_zalaks_values(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'id="resetButton"')
        self.assertContains(page, '"ai": {"name": "White bread", "amount": 2, "unit": "slice"}')

    def test_more_slices_use_the_ais_slice_weight(self):
        self.client.post(self.url, {'name': 'White bread', 'amount': '3', 'unit': 'slice'})
        self.bread.refresh_from_db()
        self.assertEqual(self.bread.grams, 120)

    def test_reset_values_bring_back_the_ais_grams(self):
        # Change the unit and save, then save Zalak's values again (what Reset fills in)
        self.client.post(self.url, {'name': 'Bread', 'amount': '100', 'unit': 'g'})
        self.client.post(self.url, {'name': 'White bread', 'amount': '2', 'unit': 'slice'})
        self.bread.refresh_from_db()
        self.assertEqual((self.bread.name, self.bread.grams), ('White bread', 80))

    def test_a_guest_can_edit_their_own_item(self):
        self.client.post(self.url, {'name': 'White bread', 'amount': '1', 'unit': 'slice'})
        self.bread.refresh_from_db()
        self.assertEqual(self.bread.grams, 40)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(self.url).status_code, 404)


ITEM_ANSWER = {'status': 'ok', 'no_food_reason': '', 'item': {
    'name': 'Coffee with milk', 'amount': 1, 'unit': 'cup', 'grams': 250,
    'kcal_min': 60, 'kcal_max': 90, 'protein_min': 3, 'protein_max': 4,
    'carbs_min': 5, 'carbs_max': 7, 'fat_min': 3, 'fat_max': 5,
    'confidence': 'likely', 'reason': '', 'question': ''}}


def item_answer(**changes):
    """estimate_item's raw answer for one item, with some fields changed."""
    answer = copy.deepcopy(ITEM_ANSWER)
    answer['item'].update(changes)
    return answer


@override_settings(ZALAK_AI_FAKE=False)
class EstimateItemTests(TestCase):
    """Chunk 11: one small AI call for one item (Add and Re-estimate)."""

    @patch('meals.services.ai._ask_model')
    def test_returns_a_validated_item(self, ask_model):
        ask_model.return_value = item_answer(grams=252)
        answer = estimate_item('coffee with milk')
        self.assertEqual(answer['status'], 'ok')
        self.assertEqual(answer['item']['grams'], 250)   # rounded to 5 like every item

    @patch('meals.services.ai._ask_model')
    def test_portion_and_meal_go_in_the_message(self, ask_model):
        ask_model.return_value = item_answer()
        estimate_item('Rye bread', Decimal('2'), 'slice', 'Tavče gravče with bread')
        text = ask_model.call_args.args[0]
        self.assertIn('Item: Rye bread', text)
        self.assertIn('Portion (fixed): 2 slice', text)
        self.assertIn('The meal: Tavče gravče with bread', text)
        self.assertEqual(ask_model.call_args.kwargs['schema'], ITEM_RESPONSE_SCHEMA)

    @patch('meals.services.ai._ask_model')
    def test_name_only_has_no_portion(self, ask_model):
        ask_model.return_value = item_answer()
        estimate_item('coffee')
        self.assertNotIn('Portion', ask_model.call_args.args[0])

    @patch('meals.services.ai._ask_model')
    def test_no_food(self, ask_model):
        ask_model.return_value = {'status': 'no_food', 'no_food_reason': 'That is a shoe.', 'item': {}}
        answer = estimate_item('my shoe')
        self.assertEqual((answer['status'], answer['item']), ('no_food', None))
        self.assertEqual(answer['no_food_reason'], 'That is a shoe.')

    def test_bad_answers_raise(self):
        bad_answers = [item_answer(confidence='maybe'), item_answer(kcal_min=200, kcal_max=100),
                       item_answer(confidence='unsure', reason=''), {'status': 'ok'}, 'text']
        for bad in bad_answers:
            with self.subTest(bad=str(bad)[:50]), patch('meals.services.ai._ask_model', return_value=bad):
                with self.assertRaises(AnalysisError):
                    estimate_item('coffee')

    @override_settings(ZALAK_AI_FAKE=True, ZALAK_AI_FAKE_DELAY=0)
    def test_fake_keeps_the_name_and_portion(self):
        item = estimate_item('Rye bread', Decimal('2'), 'slice')['item']
        self.assertEqual((item['name'], item['amount'], item['unit']), ('Rye bread', 2.0, 'slice'))


class AnalyzedMealMixin:
    """A signed-in user with the fake meal analyzed: tavče gravče (0), bread (1), salad (2), oil (3)."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče, bread, salad', 'slot': 'lunch'})
        self.meal = Meal.objects.get()
        self.result_url = reverse('result', args=[self.meal.id])

    def card_url(self, item):
        return f'{self.result_url}#item-{item.id}'


@override_settings(ZALAK_AI_FAKE=False)
class AddItemTests(AnalyzedMealMixin, TestCase):
    """Chunk 11: "Add something Zalak missed"."""

    def add(self, name='coffee with milk', answer=None, error=None, meal=None):
        url = reverse('add_item', args=[(meal or self.meal).id])
        with patch('meals.services.ai._ask_model', return_value=answer or item_answer(),
                   side_effect=error) as ask_model:
            response = self.client.post(url, {'name': name})
        return response, ask_model

    def test_result_has_the_add_row(self):
        page = self.client.get(self.result_url)
        self.assertContains(page, f'action="{reverse("add_item", args=[self.meal.id])}"')
        self.assertContains(page, 'placeholder="Add something Zalak missed"')
        self.assertContains(page, 'js/add_item.js?v=')

    def test_added_at_the_end(self):
        response, ask_model = self.add()
        coffee = self.meal.items.get(name='Coffee with milk')
        self.assertRedirects(response, self.card_url(coffee), fetch_redirect_response=False)
        self.assertEqual(coffee.position, 4)
        self.assertEqual((coffee.kcal_min, coffee.kcal_max), (60, 90))
        self.assertIn('The meal: Tavče gravče with bread and salad', ask_model.call_args.args[0])

        self.meal.refresh_from_db()
        self.assertEqual(self.meal.ai_response['items'][4]['name'], 'Coffee with milk')
        self.assertEqual(coffee.ai_estimate['grams'], 250)   # so Reset works on it too

        page = self.client.get(self.result_url)
        self.assertContains(page, 'Coffee with milk added')
        self.assertContains(page, '60–90 kcal')

    def test_positions_stay_apart_after_a_removal(self):
        bread = self.meal.items.get(name='White bread')
        self.client.post(reverse('delete_item', args=[self.meal.id, bread.id]))
        self.add()
        self.assertEqual(self.meal.items.get(name='Coffee with milk').position, 4)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.ai_response['items'][1]['name'], 'White bread')   # still there for Undo

    def test_failure_keeps_the_name(self):
        response, ask_model = self.add(error=AnalysisError('down'))
        self.assertRedirects(response, f'{self.result_url}#add-item', fetch_redirect_response=False)
        self.assertEqual(self.meal.items.count(), 4)

        page = self.client.get(self.result_url)
        self.assertContains(page, 'value="coffee with milk"')
        self.assertContains(page, 'Try again')
        self.assertContains(page, 'role="alert"')
        self.assertContains(page, 'estimate that just now')

        again = self.client.get(self.result_url)   # shown once
        self.assertNotContains(again, 'Try again')

    def test_connection_failure_says_so(self):
        self.add(error=AnalysisError('offline', kind='connection'))
        self.assertContains(self.client.get(self.result_url), 'Connection lost.')

    def test_no_food_shows_the_reason(self):
        self.add(name='my shoe', answer={'status': 'no_food', 'no_food_reason': 'That is a shoe.', 'item': {}})
        page = self.client.get(self.result_url)
        self.assertContains(page, 'That is a shoe.')
        self.assertContains(page, 'value="my shoe"')
        self.assertEqual(self.meal.items.count(), 4)

    def test_empty_name_is_ignored(self):
        response, ask_model = self.add(name='   ')
        self.assertRedirects(response, self.result_url, fetch_redirect_response=False)
        ask_model.assert_not_called()

    def test_meal_without_an_ai_answer(self):
        # An admin-made meal: chicken at position 0 and no ai_response
        meal = make_draft(self.user)
        self.add(meal=meal)
        coffee = meal.items.get(name='Coffee with milk')
        self.assertEqual(coffee.position, 1)
        meal.refresh_from_db()
        self.assertIsNone(meal.ai_response['items'][0])        # the chicken has no AI answer
        self.assertIsNone(meal.items.get(name='Chicken breast').ai_estimate)
        self.assertEqual(coffee.ai_estimate['name'], 'Coffee with milk')

    def test_logged_meal_can_get_items(self):
        self.meal.status = 'logged'
        self.meal.save()
        self.add()
        self.assertTrue(self.meal.items.filter(name='Coffee with milk').exists())

    def test_another_users_meal_is_404(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        response, ask_model = self.add(meal=make_draft(other))
        self.assertEqual(response.status_code, 404)
        ask_model.assert_not_called()

    def test_needs_a_post(self):
        self.assertEqual(self.client.get(reverse('add_item', args=[self.meal.id])).status_code, 405)


@override_settings(ZALAK_AI_FAKE=False)
class ReEstimateTests(AnalyzedMealMixin, TestCase):
    """Chunk 11: "Re-estimate with Zalak" on Edit item (bread: 2 slices, 60 g)."""

    def setUp(self):
        super().setUp()
        self.bread = self.meal.items.get(name='White bread')
        self.url = reverse('re_estimate_item', args=[self.meal.id, self.bread.id])

    def re_estimate(self, answer=None, error=None, **data):
        data = {'name': 'Rye bread', 'amount': '3', 'unit': 'slice', **data}
        answer = answer or item_answer(name='Rye bread', amount=2, unit='slice', grams=105,
                                       kcal_min=230, kcal_max=270, confidence='sure')
        with patch('meals.services.ai._ask_model', return_value=answer, side_effect=error) as ask_model:
            response = self.client.post(self.url, data)
        return response, ask_model

    def test_edit_item_has_the_button_next_to_save(self):
        page = self.client.get(reverse('edit_item', args=[self.meal.id, self.bread.id])).content.decode()
        actions = page[page.index('class="z-edit-actions"'):]
        self.assertIn(f'formaction="{self.url}"', actions)
        self.assertLess(actions.index('Re-estimate'), actions.index('Save changes'))   # Re-estimate | Save
        self.assertNotIn('Delete item', actions[:actions.index('</form>')])            # Delete stays apart

    def test_reset_has_an_icon(self):
        page = self.client.get(reverse('edit_item', args=[self.meal.id, self.bread.id]))
        self.assertContains(page, 'class="z-reset-btn" id="resetButton"')
        self.assertContains(page, 'bi-arrow-counterclockwise')

    def test_new_numbers_keep_the_users_portion(self):
        response, ask_model = self.re_estimate()
        self.assertRedirects(response, self.card_url(self.bread), fetch_redirect_response=False)
        self.assertIn('Portion (fixed): 3 slice', ask_model.call_args.args[0])

        self.bread.refresh_from_db()
        self.assertEqual((self.bread.name, self.bread.amount, self.bread.unit), ('Rye bread', 3, 'slice'))
        self.assertEqual(self.bread.grams, 105)                  # Zalak's grams for 3 slices
        self.assertEqual((self.bread.kcal_min, self.bread.kcal_max), (230, 270))
        self.assertEqual(self.bread.confidence, 'sure')
        self.assertFalse(self.bread.edited_by_user)
        self.assertContains(self.client.get(self.result_url), 'Rye bread re-estimated')

    def test_reset_follows_the_new_estimate(self):
        self.re_estimate()
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.ai_response['items'][1]['name'], 'Rye bread')
        page = self.client.get(reverse('edit_item', args=[self.meal.id, self.bread.id]))
        self.assertContains(page, '"ai": {"name": "Rye bread", "amount": 3.0, "unit": "slice"}')

    def test_failure_keeps_what_was_typed(self):
        response, ask_model = self.re_estimate(error=AnalysisError('offline', kind='connection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Rye bread"')
        self.assertContains(response, 'Connection lost.')
        # Save changes from this page still goes to Edit item, not to re-estimate
        self.assertContains(response, f'action="{reverse("edit_item", args=[self.meal.id, self.bread.id])}"')
        self.bread.refresh_from_db()
        self.assertEqual((self.bread.name, self.bread.grams), ('White bread', 60))

    def test_no_food_says_why(self):
        response, ask_model = self.re_estimate(
            answer={'status': 'no_food', 'no_food_reason': 'That is a shoe.', 'item': {}}, name='shoe')
        self.assertContains(response, 'That is a shoe.')
        self.bread.refresh_from_db()
        self.assertEqual(self.bread.name, 'White bread')

    def test_bad_form_doesnt_ask_zalak(self):
        response, ask_model = self.re_estimate(amount='0')
        self.assertContains(response, 'The amount must be more than 0.')
        ask_model.assert_not_called()

    def test_another_visitor_gets_404(self):
        self.client.logout()
        response, ask_model = self.re_estimate()
        self.assertEqual(response.status_code, 404)
        ask_model.assert_not_called()

    def test_needs_a_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class AnswerQuestionTests(AnalyzedMealMixin, TestCase):
    """Chunk 11: A little / About that / A lot on the unsure oil (Zalak: 1 tbsp, 10 g, 20–60 kcal)."""

    def setUp(self):
        with override_settings(ZALAK_AI_FAKE=False):
            super().setUp()
        self.oil = self.meal.items.get(name='Cooking oil')
        self.url = reverse('answer_question', args=[self.meal.id, self.oil.id])

    def answer(self, value):
        response = self.client.post(self.url, {'answer': value})
        self.oil.refresh_from_db()
        return response

    def test_chips_show_on_the_unsure_item_only(self):
        page = self.client.get(self.result_url)
        self.assertContains(page, f'action="{self.url}"')
        self.assertContains(page, 'name="answer" value="lot"', count=1)

    def test_a_lot(self):
        response = self.answer('lot')
        self.assertRedirects(response, self.card_url(self.oil), fetch_redirect_response=False)
        self.assertEqual((self.oil.amount, self.oil.unit, self.oil.grams), (Decimal('1.5'), 'tbsp', 15))
        self.assertEqual((self.oil.kcal_min, self.oil.kcal_max), (30, 90))

    def test_answered_question_goes_away(self):
        self.answer('lot')
        self.assertEqual(self.oil.confidence, 'likely')   # the user answered Zalak's question
        self.assertTrue(self.oil.edited_by_user)
        self.assertFalse(self.oil.can_ask)

        page = self.client.get(self.result_url)
        self.assertNotContains(page, 'name="answer"')          # no chips left
        self.assertNotContains(page, 'Oil is hard to see')     # no reason box either
        self.assertContains(page, '1½ tbsp · 15 g')            # no "about" any more: not unsure

    def test_a_little(self):
        self.answer('little')
        self.assertEqual((self.oil.amount, self.oil.grams), (Decimal('0.5'), 5))

    def test_a_second_answer_is_404(self):
        self.answer('lot')
        response = self.client.post(self.url, {'answer': 'little'})
        self.assertEqual(response.status_code, 404)
        self.oil.refresh_from_db()
        self.assertEqual(self.oil.grams, 15)

    def test_amount_can_still_change_on_edit_item(self):
        self.answer('lot')
        self.client.post(reverse('edit_item', args=[self.meal.id, self.oil.id]),
                         {'name': 'Cooking oil', 'amount': '2', 'unit': 'tbsp'})
        self.oil.refresh_from_db()
        self.assertEqual(self.oil.grams, 20)   # Zalak's 10 g per tbsp

    def test_odd_answer_changes_nothing(self):
        self.answer('huge')
        self.assertEqual((self.oil.grams, self.oil.edited_by_user, self.oil.confidence), (10, False, 'unsure'))

    def test_item_without_a_question_is_404(self):
        bread = self.meal.items.get(name='White bread')
        response = self.client.post(reverse('answer_question', args=[self.meal.id, bread.id]), {'answer': 'lot'})
        self.assertEqual(response.status_code, 404)

    def test_needs_a_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class AccountTests(TestCase):
    """Chunk 12: Welcome, Create account (2 steps), Sign in and Sign out."""

    def sign_up(self, **changes):
        data = {'first_name': 'Ana', 'email': 'Ana@Example.com', 'password': 'tavce-gravce-42', 'agree': 'on'}
        data.update(changes)
        return self.client.post(reverse('signup'), data)

    def test_a_new_user_gets_a_profile(self):
        # The post_save signal, for every way of making a user (here: like createsuperuser)
        user = User.objects.create_superuser('boss', password='a-long-password')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_saving_a_user_again_keeps_one_profile(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        user.first_name = 'Ana'
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)

    def test_guest_gets_welcome(self):
        page = self.client.get(reverse('home'))
        self.assertTemplateUsed(page, 'meals/welcome.html')
        self.assertContains(page, 'Try it without an account')
        self.assertContains(page, reverse('signup'))
        self.assertContains(page, reverse('sign_in'))

    def test_signed_in_user_gets_home(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(user)
        page = self.client.get(reverse('home'))
        self.assertTemplateUsed(page, 'meals/home.html')

    def test_sign_up_makes_the_account_and_signs_in(self):
        response = self.sign_up()
        self.assertRedirects(response, reverse('signup_details'))

        user = User.objects.get()
        self.assertEqual(user.username, 'ana@example.com')   # the e-mail, lowercased
        self.assertEqual(user.email, 'ana@example.com')
        self.assertEqual(user.first_name, 'Ana')
        self.assertTrue(user.check_password('tavce-gravce-42'))   # hashed, not plain text
        self.assertNotEqual(user.password, 'tavce-gravce-42')
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), user.id)

    def test_the_same_email_twice_is_refused(self):
        User.objects.create_user('ana@example.com', email='ana@example.com', password='a-long-password')
        page = self.sign_up(email='ANA@example.com')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'There is already an account with this e-mail.')
        self.assertContains(page, 'Sign in instead')
        self.assertEqual(User.objects.count(), 1)

    def test_the_checkbox_is_required(self):
        page = self.sign_up(agree='')
        self.assertContains(page, 'Tick this box to continue.')
        self.assertFalse(User.objects.exists())

    def test_weak_passwords_are_refused_with_what_to_do(self):
        cases = {
            'short': 'Use at least 8 characters.',
            '12345678901': 'Add some letters, not only numbers.',
            'password123': 'Lots of people use this password.',
            'ana@example.com': 'Make it less like your name or e-mail.',
        }
        for password, message in cases.items():
            page = self.sign_up(password=password)
            self.assertContains(page, message, msg_prefix=password)
            self.assertContains(page, 'aria-invalid="true"')
        self.assertFalse(User.objects.exists())

    def test_empty_fields_get_calm_messages(self):
        page = self.sign_up(first_name='  ', email='', password='')
        self.assertContains(page, 'Write your name')
        self.assertContains(page, 'Write your e-mail')
        self.assertContains(page, 'Choose a password')

    def test_step_2_saves_the_details(self):
        self.sign_up()
        response = self.client.post(reverse('signup_details'),
                                    {'height_cm': '182', 'weight_kg': '78', 'activity_level': 'medium'})
        # Not fetched here: that visit would show (and use up) the one-time toast
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        profile = Profile.objects.get()
        self.assertEqual((profile.height_cm, profile.weight_kg, profile.activity_level), (182, 78, 'medium'))

        home = self.client.get(reverse('home'))
        self.assertContains(home, 'Welcome to Zalak, Ana')   # the toast

    def test_step_2_can_stay_empty(self):
        self.sign_up()
        response = self.client.post(reverse('signup_details'), {'height_cm': '', 'weight_kg': ''})
        self.assertRedirects(response, reverse('home'))
        profile = Profile.objects.get()
        self.assertIsNone(profile.height_cm)
        self.assertEqual(profile.activity_level, '')

    def test_step_2_checks_the_numbers(self):
        self.sign_up()
        page = self.client.post(reverse('signup_details'), {'height_cm': '18', 'weight_kg': '780'})
        self.assertContains(page, 'Check the height')
        self.assertContains(page, 'Check the weight')
        self.assertIsNone(Profile.objects.get().height_cm)

    def test_skip_saves_nothing(self):
        self.sign_up()
        response = self.client.post(reverse('signup_details'), {'height_cm': '18', 'skip': '1'})
        self.assertRedirects(response, reverse('home'))
        self.assertIsNone(Profile.objects.get().height_cm)

    def test_step_2_needs_an_account(self):
        response = self.client.get(reverse('signup_details'))
        self.assertRedirects(response, reverse('sign_in') + '?next=' + reverse('signup_details'))

    def test_sign_in_with_any_case(self):
        User.objects.create_user('ana@example.com', password='a-long-password')
        response = self.client.post(reverse('sign_in'), {'username': ' Ana@Example.COM ', 'password': 'a-long-password'})
        self.assertRedirects(response, reverse('home'))

    def test_an_admin_made_username_with_capitals_can_sign_in(self):
        User.objects.create_superuser('Viktor', password='a-long-password')
        response = self.client.post(reverse('sign_in'), {'username': 'viktor', 'password': 'a-long-password'})
        self.assertRedirects(response, reverse('home'))

    def test_wrong_password_gets_a_calm_message(self):
        User.objects.create_user('ana@example.com', password='a-long-password')
        page = self.client.post(reverse('sign_in'), {'username': 'ana@example.com', 'password': 'nope'})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'That e-mail and password don&#x27;t match.')
        self.assertNotIn('_auth_user_id', self.client.session)
        # The e-mail is kept and the cursor goes to the password
        form = page.context['form']
        self.assertEqual(form['username'].value(), 'ana@example.com')
        self.assertIn('autofocus', form.fields['password'].widget.attrs)
        self.assertNotIn('autofocus', form.fields['username'].widget.attrs)

    def test_personal_pages_send_a_guest_to_sign_in(self):
        for name in ['diary', 'statistics', 'profile']:
            response = self.client.get(reverse(name))
            self.assertRedirects(response, reverse('sign_in') + '?next=' + reverse(name))

    def test_sign_in_returns_to_the_page_asked_for(self):
        User.objects.create_user('ana@example.com', password='a-long-password')
        response = self.client.post(reverse('sign_in'), {
            'username': 'ana@example.com', 'password': 'a-long-password', 'next': reverse('diary'),
        })
        self.assertRedirects(response, reverse('diary'))

    def test_signed_in_user_skips_the_account_pages(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('sign_in')), reverse('home'))
        self.assertRedirects(self.client.get(reverse('signup')), reverse('home'))

    def test_sign_out(self):
        user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('profile')), 'Sign out')

        self.assertEqual(self.client.get(reverse('sign_out')).status_code, 405)   # only POST signs out
        response = self.client.post(reverse('sign_out'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTemplateUsed(self.client.get(reverse('home')), 'meals/welcome.html')

    def test_account_pages_render(self):
        for name in ['sign_in', 'signup']:
            page = self.client.get(reverse(name))
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, 'js/auth.js')
            self.assertContains(page, 'data-password-toggle')


class HomeTests(TestCase):
    """Chunk 14: the week strip, the Eaten card, the four slots and the sheets."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password', first_name='Ana')
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def log(self, slot, day=None, title='Chicken', hour=12, user=None, **fields):
        """A logged meal of 230-260 kcal (chicken, 150 g) on a day, at a local hour."""
        meal = make_draft(user=user or self.user, slot=slot, status='logged', **fields)
        day = day or self.today
        when = timezone.make_aware(datetime(day.year, day.month, day.day, hour, 0))
        Meal.objects.filter(id=meal.id).update(eaten_at=when, title=title)
        meal.refresh_from_db()
        return meal

    def home(self, **params):
        return self.client.get(reverse('home'), params)

    def slot(self, page, value):
        return next(slot for slot in page.context['slots'] if slot['value'] == value)

    def test_meals_are_grouped_by_slot_with_day_totals(self):
        self.log('breakfast', title='Yogurt')
        self.log('snack', title='Apple', hour=11)
        self.log('snack', title='Coffee', hour=16)
        page = self.home()
        self.assertEqual(len(self.slot(page, 'breakfast')['meals']), 1)
        self.assertEqual(len(self.slot(page, 'snack')['meals']), 2)
        self.assertEqual(self.slot(page, 'snack')['summary'], '2 meals · Apple, Coffee')
        self.assertEqual(self.slot(page, 'dinner')['summary'], 'Nothing yet')
        self.assertEqual(page.context['totals']['kcal_min'], 690)
        self.assertEqual(page.context['totals']['kcal_max'], 780)
        self.assertContains(page, '690–780')
        self.assertEqual(page.context['totals']['protein_min'], 126)
        self.assertContains(page, 'Eaten today')
        # The bar has a part per slot with meals, and the legend names them
        self.assertEqual([part['value'] for part in page.context['bar']], ['breakfast', 'snack'])

    def test_big_totals_get_thousands_separators(self):
        for hour in range(8, 13):
            self.log('lunch', hour=hour)
        self.assertContains(self.home(), '1,150–1,300')

    def test_only_this_users_logged_meals_of_that_day_count(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        make_draft(user=self.user, slot='lunch')                         # a draft
        self.log('lunch', deleted_at=timezone.now())                      # deleted
        self.log('lunch', user=other)                                     # someone else's
        self.log('lunch', day=self.today - timedelta(days=1))             # another day
        page = self.home()
        self.assertEqual(page.context['totals']['kcal_max'], 0)
        self.assertTrue(all(not slot['meals'] for slot in page.context['slots']))
        self.assertContains(page, '<span class="z-num">0</span>', html=False)

    def test_a_past_day(self):
        yesterday = self.today - timedelta(days=1)
        self.log('dinner', day=yesterday)
        page = self.home(date=yesterday.isoformat())
        self.assertEqual(page.context['day'], yesterday)
        self.assertEqual(page.context['eaten_label'], 'Eaten yesterday')
        self.assertEqual(len(self.slot(page, 'dinner')['meals']), 1)
        # "+" logs to the day on screen: the Add sheet carries it
        self.assertEqual(page.context['add_day'], yesterday)
        self.assertContains(page, f'name="day" value="{yesterday.isoformat()}"')

    def test_an_older_day_is_named(self):
        day = self.today - timedelta(days=3)
        page = self.home(date=day.isoformat())
        self.assertEqual(page.context['eaten_label'], f'Eaten on {day:%a} {day.day}')

    def test_future_or_odd_dates_show_today(self):
        for value in [(self.today + timedelta(days=1)).isoformat(), 'yesterday', '2026-02-30']:
            page = self.home(date=value)
            self.assertEqual(page.context['day'], self.today)
            self.assertIsNone(page.context['add_day'])

    def test_week_strip(self):
        page = self.home()
        days = page.context['week']['days']
        self.assertEqual(len(days), 7)
        self.assertEqual(days[0]['date'].weekday(), 0)   # starts on Monday
        self.assertIsNone(page.context['week']['next_url'])   # nothing ahead of this week
        for day in days:
            if day['date'] > self.today:
                self.assertTrue(day['is_future'])
                self.assertNotContains(page, f'href="/?date={day["date"].isoformat()}"')

        last_week = self.home(date=(self.today - timedelta(days=7)).isoformat())
        self.assertEqual(last_week.context['week']['next_url'], '/')   # a week on is today

    def test_calendar_marks_days_with_meals(self):
        self.log('lunch')
        page = self.home()
        cells = [cell for week in page.context['calendar']['weeks'] for cell in week if cell]
        today_cell = next(cell for cell in cells if cell['date'] == self.today)
        self.assertTrue(today_cell['has_meals'])
        self.assertTrue(today_cell['is_selected'])
        self.assertTrue(all(cell['is_future'] for cell in cells if cell['date'] > self.today))
        self.assertIsNone(page.context['calendar']['next_url'])   # never past this month
        self.assertFalse(page.context['calendar_open'])

    def test_calendar_month_arrows(self):
        page = self.home(month='2026-01')
        self.assertEqual(page.context['calendar']['first'], datetime(2026, 1, 1).date())
        self.assertTrue(page.context['calendar_open'])
        self.assertContains(page, 'data-open-on-load')
        # A month in the future shows this month; a broken one the selected day's month
        self.assertEqual(self.home(month='2999-01').context['calendar']['first'], self.today.replace(day=1))
        self.assertFalse(self.home(month='soon').context['calendar_open'])

    def test_first_day_card_until_the_first_meal(self):
        self.assertContains(self.home(), 'Log your first meal')
        self.log('lunch', day=self.today - timedelta(days=5))
        self.assertNotContains(self.home(), 'Log your first meal')

    def test_one_meal_links_to_it_and_two_open_a_sheet(self):
        lunch = self.log('lunch')
        apple = self.log('snack', title='Apple')
        coffee = self.log('snack', title='Coffee')
        page = self.home()
        self.assertContains(page, f'href="{reverse("result", args=[lunch.id])}?from=home"')
        self.assertContains(page, 'id="slotSheet-snack"')
        self.assertNotContains(page, 'id="slotSheet-lunch"')
        for meal in (apple, coffee):
            self.assertContains(page, f'href="{reverse("result", args=[meal.id])}?from=home"')
        self.assertContains(page, 'Add another snack')

    def test_add_sheet_is_on_every_signed_in_page(self):
        page = self.home()
        self.assertContains(page, 'id="addMealSheet"')
        self.assertEqual(page.context['add_slot'], slot_for_time(timezone.now()))
        self.assertContains(page, 'was picked from the time')
        self.assertContains(self.client.get(reverse('diary')), 'id="addMealSheet"')

    def test_guests_have_no_add_sheet(self):
        self.client.logout()
        self.assertNotContains(self.home(), 'id="addMealSheet"')

    def test_greeting(self):
        self.assertRegex(self.home().content.decode(), r'Good (morning|afternoon|evening), Ana')


@override_settings(ZALAK_AI_FAKE=False)
class PastDayTests(TestCase):
    """Chunk 14: "+" on a past day on Home logs the meal to that day."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.yesterday = timezone.localdate() - timedelta(days=1)

    def analyze(self, **data):
        data.setdefault('text', 'chicken and rice')
        data.setdefault('slot', 'dinner')
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), data)
        return Meal.objects.get()

    def test_the_page_says_which_day(self):
        page = self.client.get(reverse('text_input'), {'slot': 'dinner', 'day': self.yesterday.isoformat()})
        self.assertContains(page, f'name="day" value="{self.yesterday.isoformat()}"')
        self.assertContains(page, f'Add to dinner · {self.yesterday:%a} {self.yesterday.day}')

    def test_a_past_day_keeps_the_clock_time(self):
        meal = self.analyze(day=self.yesterday.isoformat())
        self.assertEqual(timezone.localtime(meal.eaten_at).date(), self.yesterday)

    def test_a_future_day_means_now(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        meal = self.analyze(day=tomorrow.isoformat())
        self.assertEqual(timezone.localtime(meal.eaten_at).date(), timezone.localdate())

    def test_log_goes_to_that_days_home(self):
        meal = self.analyze(day=self.yesterday.isoformat())
        response = self.client.post(reverse('log_meal', args=[meal.id]), {'slot': 'dinner'})
        self.assertRedirects(response, f'/?date={self.yesterday.isoformat()}')
        meal.refresh_from_db()
        self.assertEqual(meal.status, 'logged')

    def test_log_today_goes_to_plain_home(self):
        meal = self.analyze()
        response = self.client.post(reverse('log_meal', args=[meal.id]), {'slot': 'dinner'})
        self.assertRedirects(response, reverse('home'))

    def test_photo_on_a_past_day(self):
        use_temp_media(self)
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('photo_input'),
                             {'photo': jpeg(), 'slot': 'lunch', 'day': self.yesterday.isoformat()})
        meal = Meal.objects.get()
        self.assertEqual(timezone.localtime(meal.eaten_at).date(), self.yesterday)


class MealDetailTests(TestCase):
    """Chunk 15: Meal detail edits a logged meal's slot, time, name and photo; delete with Undo."""

    def setUp(self):
        use_temp_media(self)
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.meal = make_draft(user=self.user, slot='lunch', status='logged',
                               ai_response={'status': 'ok', 'title': 'Chicken'})
        self.url = reverse('result', args=[self.meal.id])

    def save(self, **changes):
        eaten = timezone.localtime(self.meal.eaten_at)
        data = {'slot': self.meal.slot, 'title': self.meal.title,
                'eaten_day': eaten.date().isoformat(), 'eaten_time': eaten.strftime('%H:%M'),
                'remove_photo': ''}
        data.update(changes)
        return self.client.post(reverse('save_meal', args=[self.meal.id]), data)

    def test_logged_meal_shows_meal_detail_and_a_draft_shows_result(self):
        page = self.client.get(self.url)
        self.assertTemplateUsed(page, 'meals/meal_detail.html')
        self.assertContains(page, 'Save changes')
        self.assertContains(page, 'Delete meal')
        self.assertContains(page, 'When did you eat it?')
        # The wheel: two spinbuttons that start on the saved hour and minute
        eaten = timezone.localtime(self.meal.eaten_at)
        self.assertContains(page, 'role="spinbutton"', count=2)
        self.assertContains(page, f'aria-valuetext="{eaten:%H}"')
        self.assertContains(page, f'is-selected" data-value="{eaten:%M}"')
        draft = make_draft(user=self.user)
        self.assertTemplateUsed(self.client.get(reverse('result', args=[draft.id])), 'meals/result.html')

    def test_someone_elses_meal_is_404(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.save(title='Mine now').status_code, 404)
        self.assertEqual(self.client.post(reverse('delete_meal', args=[self.meal.id])).status_code, 404)

    def test_a_draft_cannot_be_saved_or_deleted_here(self):
        draft = make_draft(user=self.user)
        self.assertEqual(self.client.post(reverse('save_meal', args=[draft.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('delete_meal', args=[draft.id])).status_code, 404)

    def test_change_slot_and_time(self):
        # The time sheet changes the time on the meal's own day: here a meal from yesterday
        yesterday = timezone.localdate() - timedelta(days=1)
        noon = timezone.make_aware(datetime(yesterday.year, yesterday.month, yesterday.day, 12, 0))
        Meal.objects.filter(id=self.meal.id).update(eaten_at=noon)
        self.meal.refresh_from_db()
        response = self.save(slot='snack', eaten_time='21:40')
        # Not fetched here: that would show (and use up) the toast before the check below
        self.assertRedirects(response, f'/?date={yesterday.isoformat()}', fetch_redirect_response=False)
        self.meal.refresh_from_db()
        eaten = timezone.localtime(self.meal.eaten_at)
        self.assertEqual((eaten.date(), eaten.hour, eaten.minute), (yesterday, 21, 40))
        self.assertEqual(self.meal.slot, 'snack')
        home = self.client.get(response.url)
        self.assertContains(home, 'Changes saved')

    def test_an_untouched_time_stays_exactly(self):
        exact = timezone.now().replace(second=45, microsecond=123000) - timedelta(hours=1)
        Meal.objects.filter(id=self.meal.id).update(eaten_at=exact)
        self.meal.refresh_from_db()
        self.save(title='Lunch at work')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.eaten_at, exact)
        self.assertEqual(self.meal.title, 'Lunch at work')

    def test_a_future_time_is_refused(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        before = self.meal.eaten_at
        page = self.save(eaten_day=tomorrow.isoformat(), eaten_time='08:00', title='Changed')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'That time hasn')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.eaten_at, before)
        self.assertEqual(self.meal.title, 'Chicken')

    def test_an_emptied_name_gives_back_zalaks(self):
        self.save(title='   ')
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.title, 'Chicken')

    def test_add_replace_and_remove_a_photo(self):
        self.save(photo=jpeg())
        self.meal.refresh_from_db()
        first = self.meal.photo.path
        self.assertTrue(os.path.exists(first))

        self.save(photo=jpeg('again.jpg'))
        self.meal.refresh_from_db()
        self.assertTrue(os.path.exists(self.meal.photo.path))
        self.assertFalse(os.path.exists(first))   # the replaced file is gone

        second = self.meal.photo.path
        self.save(remove_photo='1')
        self.meal.refresh_from_db()
        self.assertFalse(self.meal.photo)
        self.assertFalse(os.path.exists(second))

    def test_a_bad_photo_is_refused(self):
        page = self.save(photo=SimpleUploadedFile('note.jpg', b'not a picture'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Try another photo')
        self.meal.refresh_from_db()
        self.assertFalse(self.meal.photo)

    def test_delete_and_undo(self):
        response = self.client.post(reverse('delete_meal', args=[self.meal.id]))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.meal.refresh_from_db()
        self.assertIsNotNone(self.meal.deleted_at)
        home = self.client.get(reverse('home'))
        self.assertContains(home, 'Meal deleted')
        self.assertEqual(home.context['totals']['kcal_max'], 0)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.client.post(reverse('undo_delete_meal', args=[self.meal.id]))
        self.meal.refresh_from_db()
        self.assertIsNone(self.meal.deleted_at)
        self.assertEqual(self.client.get(reverse('home')).context['totals']['kcal_max'], 260)

    def test_undo_delete_is_only_for_the_owner(self):
        self.client.post(reverse('delete_meal', args=[self.meal.id]))
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        self.client.force_login(other)
        response = self.client.post(reverse('undo_delete_meal', args=[self.meal.id]))
        self.assertEqual(response.status_code, 404)

    def test_editing_an_item_comes_back_to_meal_detail(self):
        item = self.meal.items.get()
        response = self.client.post(reverse('edit_item', args=[self.meal.id, item.id]),
                                    {'name': 'Chicken breast', 'amount': '200', 'unit': 'g'}, follow=True)
        self.assertTemplateUsed(response, 'meals/meal_detail.html')
        item.refresh_from_db()
        self.assertEqual(item.grams, 200)

    def test_time_sheet_has_no_day_switch(self):
        # Removed 2 Nov: the sheet only changes the time, on the meal's own day
        page = self.client.get(self.url)
        self.assertNotContains(page, 'name="time_day"')
        self.assertContains(page, 'data-day-label="Today"')
        self.assertContains(page, 'Use the time it was logged')
        # A meal on another day than it was logged: going back to the logged time makes no sense
        Meal.objects.filter(id=self.meal.id).update(eaten_at=timezone.now() - timedelta(days=3))
        self.assertNotContains(self.client.get(self.url), 'Use the time it was logged')


class DiaryTests(TestCase):
    """Chunk 16: the Diary, a page per day; the desktop shows the day before beside it."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def log(self, slot, day=None, hour=12, minute=0, title='Chicken', user=None, **fields):
        meal = make_draft(user=user or self.user, slot=slot, status='logged', **fields)
        day = day or self.today
        when = timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))
        Meal.objects.filter(id=meal.id).update(eaten_at=when, title=title)
        meal.refresh_from_db()
        return meal

    def diary(self, **params):
        return self.client.get(reverse('diary'), params)

    def test_today_lists_meals_in_time_order_with_a_link_each(self):
        lunch = self.log('lunch', hour=13, minute=10, title='Tavce gravce')
        breakfast = self.log('breakfast', hour=8, minute=30, title='Yogurt')
        page = self.diary()
        self.assertTemplateUsed(page, 'meals/diary.html')
        self.assertEqual(page.context['right_page']['meals'], [breakfast, lunch])
        self.assertContains(page, f'href="{reverse("result", args=[lunch.id])}?from=diary"')
        self.assertContains(page, '08:30')
        self.assertEqual(page.context['right_page']['count'], '2 meals so far')
        self.assertContains(page, 'Eaten so far')
        self.assertContains(page, '460–520')

    def test_only_this_users_logged_meals_of_that_day(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        make_draft(user=self.user, slot='lunch')
        self.log('lunch', deleted_at=timezone.now())
        self.log('lunch', user=other)
        self.log('lunch', day=self.today - timedelta(days=1))
        self.assertEqual(self.diary().context['right_page']['meals'], [])

    def test_today_offers_its_empty_slots(self):
        self.log('breakfast', hour=8)
        page = self.diary()
        self.assertEqual([value for value, label in page.context['right_page']['empty_slots']], ['lunch', 'snack', 'dinner'])
        self.assertContains(page, 'Tap to add it', count=3)
        self.assertContains(page, 'data-slot="dinner"')

    def test_a_past_day(self):
        yesterday = self.today - timedelta(days=1)
        self.log('breakfast', day=self.today - timedelta(days=5))   # the first page is earlier
        self.log('dinner', day=yesterday, hour=19)
        page = self.diary(date=yesterday.isoformat())
        self.assertEqual(page.context['right_page']['kicker'], f'{yesterday:%A} · Yesterday')
        self.assertEqual(page.context['right_page']['count'], '1 meal')
        self.assertEqual(page.context['right_page']['empty_slots'], [])   # only today offers them
        self.assertContains(page, 'Eaten this day')
        self.assertEqual(page.context['phone_next'], {'url': '/diary/', 'label': 'Today'})
        self.assertEqual(page.context['add_day'], yesterday)

    def test_future_or_odd_dates_show_today(self):
        for value in [(self.today + timedelta(days=2)).isoformat(), 'soon']:
            self.assertEqual(self.diary(date=value).context['day'], self.today)

    def test_the_first_page(self):
        first = self.today - timedelta(days=3)
        self.log('lunch', day=first)
        page = self.diary(date=first.isoformat())
        self.assertEqual(page.context['right_page']['kicker'], f'{first:%A} · First page')
        self.assertEqual(page.context['right_page']['count'], '1 meal · your first day with Zalak')
        # Back still works before it (changed 2 Nov: no "Start"), and the left page is the day before
        before = first - timedelta(days=1)
        self.assertEqual(page.context['phone_prev']['url'], f'/diary/?date={before.isoformat()}')
        self.assertEqual(page.context['left_page']['date'], before)
        self.assertNotContains(page, 'Start')

    def test_back_works_from_today_with_no_meals_before(self):
        # A new account: today is the only day with meals, and yesterday is still one tap away
        self.log('lunch')
        page = self.diary()
        yesterday = self.today - timedelta(days=1)
        self.assertEqual(page.context['phone_prev'], {'url': f'/diary/?date={yesterday.isoformat()}', 'label': 'Yesterday'})
        self.assertEqual(page.context['left_page']['date'], yesterday)
        older = self.diary(date=(self.today - timedelta(days=30)).isoformat())
        self.assertIsNotNone(older.context['phone_prev'])

    def test_meal_detail_goes_back_to_the_diary(self):
        yesterday = self.today - timedelta(days=1)
        meal = self.log('dinner', day=yesterday, hour=19)
        diary_day = f'/diary/?date={yesterday.isoformat()}'
        page = self.client.get(reverse('result', args=[meal.id]), {'from': 'diary'})
        self.assertEqual(page.context['back_url'], diary_day)
        self.assertContains(page, 'aria-label="Back to the Diary"')
        # Still after editing an item (which comes back without ?from=)
        item = meal.items.get()
        self.client.post(reverse('edit_item', args=[meal.id, item.id]), {'name': 'Chicken', 'amount': '200', 'unit': 'g'})
        self.assertEqual(self.client.get(reverse('result', args=[meal.id])).context['back_url'], diary_day)
        # Save changes and Delete go back there too
        eaten = timezone.localtime(meal.eaten_at)
        response = self.client.post(reverse('save_meal', args=[meal.id]), {
            'slot': 'dinner', 'title': 'Soup', 'eaten_day': eaten.date().isoformat(),
            'eaten_time': eaten.strftime('%H:%M'), 'remove_photo': ''})
        self.assertRedirects(response, diary_day, fetch_redirect_response=False)
        response = self.client.post(reverse('delete_meal', args=[meal.id]))
        self.assertRedirects(response, diary_day, fetch_redirect_response=False)
        response = self.client.post(reverse('undo_delete_meal', args=[meal.id]))
        self.assertRedirects(response, diary_day, fetch_redirect_response=False)

    def test_meal_detail_opened_from_home_goes_back_home(self):
        meal = self.log('lunch')
        self.client.get(reverse('result', args=[meal.id]), {'from': 'diary'})
        page = self.client.get(reverse('result', args=[meal.id]), {'from': 'home'})
        self.assertEqual(page.context['back_url'], '/')
        self.assertContains(page, 'aria-label="Back to Home"')
        # Home and the Diary say where their links come from
        self.assertContains(self.client.get(reverse('home')), f'{reverse("result", args=[meal.id])}?from=home')
        self.assertContains(self.diary(), f'{reverse("result", args=[meal.id])}?from=diary')

    def test_an_empty_past_day_offers_to_add_to_it(self):
        self.log('lunch', day=self.today - timedelta(days=6))
        empty = self.today - timedelta(days=2)
        page = self.diary(date=empty.isoformat())
        self.assertContains(page, 'Nothing logged this day.')
        self.assertContains(page, f'data-day="{empty.isoformat()}"')
        self.assertNotContains(page, 'Eaten this day')

    def test_nothing_ahead_of_today(self):
        page = self.diary()
        self.assertIsNone(page.context['phone_next'])
        self.assertIsNone(page.context['desk_next'])

    def test_desktop_spread(self):
        self.log('lunch', day=self.today - timedelta(days=10))
        day = self.today - timedelta(days=4)
        page = self.diary(date=day.isoformat())
        self.assertEqual(page.context['left_page']['date'], day - timedelta(days=1))
        # The arrows move two days: back to (day-3, day-2), on to (day+1, day+2)
        self.assertEqual(page.context['desk_prev']['url'], f'/diary/?date={(day - timedelta(days=2)).isoformat()}')
        self.assertEqual(page.context['desk_next']['url'], f'/diary/?date={(day + timedelta(days=2)).isoformat()}')
        self.assertEqual(page.context['phone_prev']['url'], f'/diary/?date={(day - timedelta(days=1)).isoformat()}')

    def test_calendar_links_go_to_the_diary(self):
        page = self.diary(month='2026-01')
        self.assertTrue(page.context['calendar_open'])
        self.assertContains(page, 'href="/diary/?date=2026-01-15"')
        self.assertEqual(page.context['calendar']['today_url'], '/diary/')
        # Home's calendar still links to Home
        self.assertEqual(self.client.get(reverse('home')).context['calendar']['today_url'], '/')


class StatisticsTests(TestCase):
    """Chunk 17: Statistics for a Mo–Su week or a month. The fixed numbers use last week and last
    month, so they don't depend on today's weekday. Each meal is chicken, 150 g: 230–260 kcal,
    protein 42–47 g, carbs 0 g, fat 5–6 g."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.this_monday = self.today - timedelta(days=self.today.weekday())
        self.last_monday = self.this_monday - timedelta(days=7)

    def log(self, day, slot='lunch', hour=12, title='Chicken', user=None, **fields):
        meal = make_draft(user=user or self.user, slot=slot, status='logged', **fields)
        when = timezone.make_aware(datetime(day.year, day.month, day.day, hour, 0))
        Meal.objects.filter(id=meal.id).update(eaten_at=when, title=title)
        meal.refresh_from_db()
        return meal

    def stats(self, **params):
        return self.client.get(reverse('statistics'), params)

    def last_week(self):
        return self.stats(date=self.last_monday.isoformat())

    def test_a_guest_is_sent_to_sign_in(self):
        self.client.logout()
        page = self.stats()
        self.assertEqual(page.status_code, 302)
        self.assertIn(reverse('sign_in'), page['Location'])

    def test_the_numbers_match_the_meals_by_hand(self):
        wednesday = self.last_monday + timedelta(days=2)
        self.log(self.last_monday, 'lunch', hour=12)
        self.log(self.last_monday, 'dinner', hour=19)
        self.log(wednesday, 'lunch', title='Yogurt')
        page = self.last_week()
        self.assertTemplateUsed(page, 'meals/statistics.html')
        stats = page.context['stats']
        self.assertEqual(stats['days_logged'], 2)
        self.assertEqual(stats['days_total'], 7)
        self.assertEqual(stats['meal_count'], 3)
        self.assertContains(page, '2 of 7')

        # Monday 460–520, Wednesday 230–260: (690 ÷ 2, 780 ÷ 2) rounded to 10
        self.assertEqual((stats['kcal_min'], stats['kcal_max']), (350, 390))
        self.assertContains(page, '350–390')
        monday, tuesday = stats['days'][0], stats['days'][1]
        self.assertTrue(monday['has_meals'])
        self.assertFalse(tuesday['has_meals'])
        self.assertIn('460–520 kcal', monday['spoken'])
        self.assertIn('nothing logged', tuesday['spoken'])
        # The chart's top is 1,000 × 1.1 here: Monday's bar is 520 / 1,100, its light top 60 / 520
        self.assertEqual(monday['bar_pct'], '47.3')
        self.assertEqual(monday['range_pct'], '11.5')
        self.assertEqual([line['value'] for line in stats['grid']], [1000])

        # Grams a day: protein 126–141 ÷ 2 → 65–70, fat 15–18 ÷ 2 → 10–10 (rounded to 5)
        macros = {macro['key']: macro for macro in stats['macros']}
        self.assertEqual((macros['protein']['min'], macros['protein']['max']), (65, 70))
        self.assertEqual((macros['carbs']['min'], macros['carbs']['max']), (0, 0))
        self.assertEqual((macros['fat']['min'], macros['fat']['max']), (10, 10))
        self.assertEqual(sum(macro['pct'] for macro in stats['macros']), 100)
        self.assertEqual(macros['protein']['pct'], 78)
        self.assertContains(page, 'Protein · 78%')

    def test_shares_match_figma(self):
        from .views import macro_shares
        macros = macro_shares([
            {'key': 'protein', 'energy': 70 * 4},
            {'key': 'carbs', 'energy': 165 * 4},
            {'key': 'fat', 'energy': 55 * 9},
        ])
        self.assertEqual([macro['pct'] for macro in macros], [20, 46, 34])

    def test_only_this_users_logged_meals_of_that_week_count(self):
        other = User.objects.create_user('ivan@example.com', password='a-long-password')
        self.log(self.last_monday)
        self.log(self.last_monday, user=other)
        self.log(self.last_monday, deleted_at=timezone.now())
        self.log(self.last_monday - timedelta(days=1))   # the Sunday before
        draft = make_draft(user=self.user, slot='lunch')
        monday = self.last_monday
        Meal.objects.filter(id=draft.id).update(
            eaten_at=timezone.make_aware(datetime(monday.year, monday.month, monday.day, 9)))
        stats = self.last_week().context['stats']
        self.assertEqual(stats['meal_count'], 1)
        self.assertEqual((stats['kcal_min'], stats['kcal_max']), (230, 260))

    def test_this_week_has_no_next_and_no_future_bars(self):
        page = self.stats()
        self.assertEqual(page.context['words'], 'this week')
        self.assertIsNone(page.context['next_url'])
        self.assertEqual(page.context['prev_url'], f'{reverse("statistics")}?date={self.last_monday.isoformat()}')
        future = [d for d in page.context['stats']['days'] if d['date'] > self.today]
        self.assertTrue(all(d['is_future'] and not d['has_meals'] for d in future))
        # A day after today shows this week
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(self.stats(date=tomorrow.isoformat()).context['words'], 'this week')

    def test_last_week_goes_forward_to_this_week(self):
        page = self.last_week()
        self.assertEqual(page.context['words'], 'last week')
        self.assertEqual(page.context['next_url'], reverse('statistics'))
        self.assertContains(page, 'Previous week')

    def test_a_month(self):
        last_day = self.today.replace(day=1) - timedelta(days=1)
        self.log(last_day)
        page = self.stats(period='month', date=last_day.isoformat())
        stats = page.context['stats']
        self.assertEqual(page.context['words'], 'last month')
        self.assertEqual(page.context['label'], f'{last_day:%B %Y}')
        self.assertEqual(stats['days_total'], last_day.day)
        self.assertEqual(stats['days_logged'], 1)
        self.assertEqual([d['axis'] for d in stats['days'] if d['axis']][:2], ['1', '8'])
        # Week / Month keep the day
        self.assertEqual(page.context['week_url'], f'{reverse("statistics")}?date={last_day.isoformat()}')

    def test_most_logged_needs_two_of_the_same(self):
        self.log(self.last_monday, title='Chicken')
        self.log(self.last_monday + timedelta(days=1), title='chicken ')
        self.log(self.last_monday + timedelta(days=2), title='Yogurt')
        page = self.last_week()
        rows = page.context['stats']['most_logged']
        self.assertEqual([(row['title'], row['count']) for row in rows], [('chicken', 2)])
        self.assertContains(page, 'Most logged last week')
        self.assertContains(page, '2×')

    def test_an_empty_week_says_so_calmly(self):
        page = self.stats()
        self.assertContains(page, 'Nothing logged this week yet.')
        self.assertNotContains(page, 'Macros, average a day')
        self.assertContains(self.last_week(), 'Nothing logged last week.')

    def test_week_labels(self):
        from datetime import date
        from .views import period_label
        self.assertEqual(period_label('week', date(2026, 10, 12), date(2026, 10, 18)), '12–18 October')
        self.assertEqual(period_label('week', date(2026, 10, 26), date(2026, 11, 1)), '26 October – 1 November')
        self.assertEqual(period_label('month', date(2026, 10, 1), date(2026, 10, 31)), 'October 2026')


PROFILE_PAGES = ['profile', 'profile_details', 'profile_preferences', 'profile_account',
                 'profile_password', 'profile_delete', 'profile_help']


class ProfileTests(TestCase):
    """Chunk 18: the Profile hub, Personal details, Preferences, Change password, Delete account."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', email='ana@example.com',
                                             password='a-long-password', first_name='Ana')
        self.client.force_login(self.user)

    def details(self, **changes):
        data = {'first_name': 'Ana', 'email': 'ana@example.com', 'height_cm': '168', 'weight_kg': '61.5',
                'birth_year': '1998', 'activity_level': 'medium'}
        data.update(changes)
        return self.client.post(reverse('profile_details'), data)

    def test_every_page_opens_and_a_guest_is_sent_to_sign_in(self):
        for name in PROFILE_PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.client.logout()
        for name in PROFILE_PAGES:
            self.assertIn(reverse('sign_in'), self.client.get(reverse(name))['Location'], name)

    def test_the_hub(self):
        page = self.client.get(reverse('profile'))
        self.assertContains(page, 'ana@example.com')
        self.assertContains(page, 'When unsure: Ask me')
        self.assertContains(page, f'action="{reverse("sign_out")}"')
        self.assertContains(page, 'estimates, not medical advice')

    def test_details_save_both_forms(self):
        response = self.details(first_name=' Ana M ', email='Ana.M@Example.com')
        self.assertRedirects(response, reverse('profile'), fetch_redirect_response=False)
        self.user.refresh_from_db()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((self.user.first_name, self.user.email, self.user.username),
                         ('Ana M', 'ana.m@example.com', 'ana.m@example.com'))   # the new sign-in name
        self.assertEqual((profile.height_cm, profile.weight_kg, profile.birth_year, profile.activity_level),
                         (168, Decimal('61.5'), 1998, 'medium'))
        self.assertContains(self.client.get(reverse('profile')), 'Changes saved')

        # Signing in works with the new e-mail
        self.client.logout()
        self.assertTrue(self.client.login(username='ana.m@example.com', password='a-long-password'))

    def test_details_keep_your_own_email_but_not_someone_elses(self):
        self.assertEqual(self.details().status_code, 302)   # the same e-mail is fine
        User.objects.create_user('ivan@example.com', password='a-long-password')
        page = self.details(email='Ivan@example.com', weight_kg='70')
        self.assertContains(page, 'There is already an account with this e-mail.')
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.weight_kg, Decimal('61.5'))   # nothing saved while one form is wrong

    def test_details_check_the_numbers(self):
        next_year = str(timezone.localdate().year + 1)
        page = self.details(birth_year=next_year, weight_kg='61.55', first_name='')
        self.assertContains(page, 'Check the year, e.g. 1998.')
        self.assertContains(page, 'Use one decimal at most, e.g. 70.5.')
        self.assertContains(page, 'Write your name')

    def test_preferences_save_with_and_without_javascript(self):
        url = reverse('profile_preferences')
        response = self.client.post(url, {'uncertainty': 'guess'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Profile.objects.get(user=self.user).uncertainty, 'guess')
        self.assertContains(self.client.get(reverse('profile')), 'When unsure: Best guess')

        response = self.client.post(url, {'uncertainty': 'ask'})
        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertEqual(Profile.objects.get(user=self.user).uncertainty, 'ask')
        bad = self.client.post(url, {'uncertainty': 'maybe'}, HTTP_X_REQUESTED_WITH='fetch')
        self.assertEqual(bad.status_code, 400)

    def analyzed_meal(self):
        with override_settings(ZALAK_AI_FAKE=False), \
                patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče, bread, salad', 'slot': 'lunch'})
        return reverse('result', args=[Meal.objects.latest('id').id])

    def test_best_guess_hides_the_question_but_keeps_the_reason(self):
        result = self.analyzed_meal()
        page = self.client.get(result)
        self.assertContains(page, 'How much was there?')
        self.assertContains(page, 'name="answer"')

        Profile.objects.filter(user=self.user).update(uncertainty='guess')
        page = self.client.get(result)
        self.assertContains(page, 'Oil is hard to see')
        self.assertContains(page, 'Unsure')
        self.assertNotContains(page, 'How much was there?')
        self.assertNotContains(page, 'name="answer"')

    def test_a_guest_is_always_asked(self):
        self.client.logout()
        result = self.analyzed_meal()
        self.assertContains(self.client.get(result), 'name="answer"')

    def test_change_password(self):
        url = reverse('profile_password')
        page = self.client.post(url, {'old_password': 'wrong', 'new_password1': 'another-long-one',
                                      'new_password2': 'another-long-one'})
        self.assertContains(page, "That&#x27;s not your current password.")
        page = self.client.post(url, {'old_password': 'a-long-password', 'new_password1': 'short',
                                      'new_password2': 'short'})
        self.assertContains(page, 'Use at least 8 characters.')

        response = self.client.post(url, {'old_password': 'a-long-password', 'new_password1': 'another-long-one',
                                          'new_password2': 'another-long-one'})
        self.assertRedirects(response, reverse('profile_account'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)   # still signed in
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('another-long-one'))

    def test_delete_account_needs_the_password(self):
        self.assertContains(self.client.get(reverse('profile_delete')), '0 logged meals')
        page = self.client.post(reverse('profile_delete'), {'password': 'wrong'})
        self.assertContains(page, "That&#x27;s not your password.")
        self.assertTrue(User.objects.filter(id=self.user.id).exists())

    def test_delete_account_removes_meals_photos_and_signs_out(self):
        use_temp_media(self)
        meal = make_draft(user=self.user, slot='lunch', status='logged')
        meal.photo.save('plate.jpg', SimpleUploadedFile('plate.jpg', b'not really a photo'))
        photo_path = meal.photo.path
        self.assertTrue(os.path.exists(photo_path))

        response = self.client.post(reverse('profile_delete'), {'password': 'a-long-password'})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        self.assertFalse(Meal.objects.exists())
        self.assertFalse(Profile.objects.exists())
        self.assertFalse(os.path.exists(photo_path))
        home = self.client.get(reverse('home'))
        self.assertTemplateUsed(home, 'meals/welcome.html')   # a guest again
        self.assertContains(home, 'Your account and meals are deleted')

    def test_sign_up_step_2_takes_a_decimal_weight(self):
        response = self.client.post(reverse('signup_details'), {'weight_kg': '78.4'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Profile.objects.get(user=self.user).weight_kg, Decimal('78.4'))


class PassTests(TestCase):
    """Chunk 19: the failed step after an analysis, the desktop layouts, the style page gone."""

    def setUp(self):
        self.user = User.objects.create_user('ana@example.com', password='a-long-password')
        self.client.force_login(self.user)

    def test_a_failed_analysis_opens_with_the_failed_step(self):
        meal = make_draft(user=self.user, slot='lunch')
        page = self.client.get(reverse('analysis_error', args=[meal.id]), {'why': 'connection', 'fresh': '1'})
        self.assertEqual(page.context['failed'], {'index': 0, 'words': 'Connection lost', 'bar': 28})
        self.assertContains(page, 'data-failed')
        self.assertContains(page, 'z-step is-failed')
        self.assertContains(page, 'style="width: 28%"')
        # The intro repeats the page's h1, so screen readers skip it
        self.assertContains(page, 'aria-hidden="true" inert')

        # A later visit (or a reload, which drops fresh) goes straight to the page
        later = self.client.get(reverse('analysis_error', args=[meal.id]), {'why': 'connection'})
        self.assertIsNone(later.context['failed'])
        self.assertNotContains(later, 'data-failed')
        self.assertContains(later, 'role="dialog"')   # the overlay is still there for Try again

    def test_no_food_marks_the_second_step(self):
        meal = make_draft(user=self.user, slot='lunch')
        Meal.objects.filter(id=meal.id).update(ai_response={'status': 'no_food', 'no_food_reason': '', 'seen': []})
        meal.items.all().delete()
        page = self.client.get(reverse('no_food', args=[meal.id]), {'fresh': '1'})
        self.assertEqual(page.context['failed']['index'], 1)
        self.assertContains(page, 'No food found in what you wrote')
        self.assertContains(page, 'z-step is-done')   # the first step was done

    def test_the_error_page_shows_the_photo_note(self):
        use_temp_media(self)
        meal = make_draft(user=self.user, slot='lunch')
        Meal.objects.filter(id=meal.id).update(input_method='photo', text='cooked in butter')
        meal.refresh_from_db()
        meal.photo.save('plate.jpg', SimpleUploadedFile('plate.jpg', b'x'))
        page = self.client.get(reverse('analysis_error', args=[meal.id]))
        self.assertContains(page, 'note: cooked in butter')

    def test_home_has_the_week_chart_for_the_desktop(self):
        meal = make_draft(user=self.user, slot='lunch', status='logged')
        page = self.client.get(reverse('home'))
        chart = page.context['week_chart']
        self.assertEqual(chart['days_total'], 7)
        self.assertEqual((chart['kcal_min'], chart['kcal_max']), (meal.kcal_min, meal.kcal_max))
        self.assertContains(page, 'z-home-week')
        self.assertContains(page, 'kcal a day')

    def test_result_and_meal_detail_have_the_two_part_layout(self):
        meal = make_draft(user=self.user, slot='lunch')
        self.assertContains(self.client.get(reverse('result', args=[meal.id])), 'z-result-layout')
        Meal.objects.filter(id=meal.id).update(status='logged')
        self.assertContains(self.client.get(reverse('result', args=[meal.id])), 'z-result-layout')

    def test_the_style_page_is_gone(self):
        self.assertEqual(self.client.get('/style/').status_code, 404)


class DemoFixtureTests(TestCase):
    """Chunk 20: meals/fixtures/demo.json, Ana's meals from Mon 26 Oct to Tue 3 Nov."""
    fixtures = ['demo']

    def setUp(self):
        self.ana = User.objects.get(username='ana@zalak.demo')

    def test_ana_signs_in_with_the_demo_password(self):
        self.assertTrue(self.client.login(username='ana@zalak.demo', password='zalak-demo-2026'))

    def test_every_meal_is_complete(self):
        meals = Meal.objects.filter(user=self.ana)
        self.assertEqual(meals.count(), 33)
        self.assertEqual(Profile.objects.get(user=self.ana).meals_logged, 33)
        days = sorted({timezone.localtime(meal.eaten_at).date() for meal in meals})
        self.assertEqual((days[0].isoformat(), days[-1].isoformat()), ('2026-10-26', '2026-11-03'))
        self.assertEqual(len(days), 9)
        photos = os.path.join(os.path.dirname(__file__), 'fixtures', 'demo_photos')
        for meal in meals:
            self.assertEqual(meal.status, 'logged')
            self.assertTrue(meal.items.exists(), meal.title)
            self.assertEqual(len(meal.ai_response['items']), meal.items.count(), meal.title)
            if meal.photo:
                self.assertTrue(os.path.exists(os.path.join(photos, os.path.basename(meal.photo.name))), meal.photo.name)

    def test_the_pages_open_with_her_week(self):
        self.client.force_login(self.ana)
        monday = '2026-10-26'
        self.assertEqual(self.client.get(reverse('home'), {'date': monday}).context['week_chart']['days_logged'], 7)
        self.assertEqual(len(self.client.get(reverse('diary'), {'date': monday}).context['right_page']['meals']), 4)
        stats = self.client.get(reverse('statistics'), {'date': monday}).context['stats']
        self.assertEqual(stats['days_logged'], 7)
        self.assertEqual([(row['title'], row['count']) for row in stats['most_logged']][:2],
                         [('Yogurt with honey and walnuts', 4), ('Coffee with milk', 3)])
        meal = Meal.objects.filter(user=self.ana).first()
        self.assertTemplateUsed(self.client.get(reverse('result', args=[meal.id])), 'meals/meal_detail.html')
