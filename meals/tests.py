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
from .models import Meal, Profile
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

    def test_logged_meal_result_has_no_log_button(self):
        self.log(slot='lunch')
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertContains(page, 'Back to Home')
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
