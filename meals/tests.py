import copy
from datetime import datetime
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
from .services.ai import FAKE_RESPONSE, AnalysisError, analyze_text, validate
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
        self.assertFalse(Profile.objects.exists())

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
    """Chunk 9: a guest can use Just checking; Log waits for the guest flow (chunk 13)."""

    def setUp(self):
        with patch('meals.services.ai._ask_model', return_value=good_answer()):
            self.client.post(reverse('text_input'), {'text': 'tavče gravče', 'slot': 'lunch'})
        self.meal = Meal.objects.get()

    def test_log_is_inactive_for_a_guest(self):
        page = self.client.get(reverse('result', args=[self.meal.id]))
        self.assertContains(page, 'id="logButton" disabled')
        response = self.client.post(reverse('log_meal', args=[self.meal.id]), {'slot': 'lunch'})
        self.assertEqual(response.status_code, 404)
        self.meal.refresh_from_db()
        self.assertEqual(self.meal.status, 'draft')

    def test_guest_just_checking(self):
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertRedirects(response, reverse('home'))
        self.assertFalse(Meal.objects.exists())

    def test_another_guest_cannot_discard_it(self):
        self.client.cookies.clear()
        response = self.client.post(reverse('just_checking', args=[self.meal.id]))
        self.assertEqual(response.status_code, 404)
