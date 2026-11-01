import json
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Timer


@override_settings(ABLY_API_KEY='')
class CoachingFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach-flow')
        self.client.force_login(self.user)
        self.timer = Timer.objects.create(user=self.user, name='Sparring', rounds=6, duration=300, interval=60)

    def action(self, action, **extra):
        return self.client.post(reverse('timers:action', args=[self.timer.pk]),
                                json.dumps(dict(action=action, **extra)), content_type='application/json')

    def test_readable_totals_exclude_final_rest(self):
        self.assertEqual(self.timer.work_label, '5:00')
        self.assertEqual(self.timer.rest_label, '1:00')
        self.assertEqual(self.timer.total_label, '35:00')
        self.timer.rounds = 1
        self.assertEqual(self.timer.total_label, '5:00')
        self.timer.interval = 0
        self.timer.rounds = 6
        self.assertEqual(self.timer.total_label, '30:00')

    def test_quick_selector_only_lists_current_users_timers(self):
        other_user = get_user_model().objects.create_user(username='other-coach', email='other-coach@example.com')
        Timer.objects.create(user=other_user, name='Private other workout')
        choice = Timer.objects.create(user=self.user, name='Technique drills')
        response = self.client.get(reverse('timers:run', args=[self.timer.pk]))
        self.assertContains(response, 'Technique drills')
        self.assertNotContains(response, 'Private other workout')
        self.assertEqual(set(response.context['available_timers'].values_list('pk', flat=True)),
                         {self.timer.pk, choice.pk})
        self.assertContains(response, 'aria-controls="timerSidePanel"')

    def test_finished_workout_resets_ready_without_starting(self):
        self.timer.status = 'DONE'
        self.timer.time_remaining = 0
        self.timer.current_round = 6
        self.timer.save(update_fields=['status', 'time_remaining', 'current_round'])
        response = self.action('complete')
        self.assertEqual(response.status_code, 200)
        self.timer.refresh_from_db()
        self.assertEqual((self.timer.status, self.timer.current_round, self.timer.current_state,
                          self.timer.time_remaining, self.timer.last_started_at),
                         ('READY', 1, 'WORK', 300, None))
        self.assertEqual(self.action('complete').status_code, 200)

    def test_completion_cannot_reset_unfinished_or_restarted_workout(self):
        self.action('start')
        self.assertEqual(self.action('complete').status_code, 409)
        self.timer.refresh_from_db()
        self.assertEqual(self.timer.status, 'RUNNING')

    def test_elapsed_workout_can_reset_before_server_state_is_polled(self):
        from datetime import timedelta
        from django.utils import timezone
        self.timer.status = 'RUNNING'
        self.timer.current_round = self.timer.rounds
        self.timer.time_remaining = self.timer.duration
        self.timer.last_started_at = timezone.now() - timedelta(seconds=301)
        self.timer.save(update_fields=['status', 'current_round', 'time_remaining', 'last_started_at'])
        self.assertEqual(self.action('complete').status_code, 200)
        self.timer.refresh_from_db()
        self.assertEqual(self.timer.status, 'READY')

    def test_running_reset_requires_confirmation(self):
        self.action('start')
        response = self.action('reset')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['confirmation_required'])
        self.timer.refresh_from_db()
        self.assertEqual(self.timer.status, 'RUNNING')
        response = self.action('reset', confirmed_reset=True)
        self.assertEqual(response.status_code, 200)
        self.timer.refresh_from_db()
        self.assertEqual(self.timer.status, 'READY')

    def test_switch_requires_confirmation_for_exact_active_timers(self):
        other = Timer.objects.create(user=self.user, name='Active drills', status='PAUSED', time_remaining=70)
        response = self.action('start')
        self.assertEqual(response.status_code, 409)
        other.refresh_from_db()
        self.assertEqual(other.status, 'PAUSED')
        self.assertEqual(other.time_remaining, 70)
        self.assertEqual(self.action('start', confirmed_reset_timer_ids=[999999]).status_code, 409)
        response = self.action('start', confirmed_reset_timer_ids=[other.pk])
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        self.assertEqual(other.status, 'READY')

    def test_ready_reset_remains_immediate_and_views_render(self):
        self.assertEqual(self.action('reset').status_code, 200)
        for url in (reverse('timers:list'), reverse('timers:edit', args=[self.timer.pk]),
                    reverse('timers:run', args=[self.timer.pk])):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse('timers:list')), '35:00')

