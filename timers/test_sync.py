from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import Timer


class TimerSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='sync-test')
        self.client.force_login(self.user)
        self.start = timezone.now()
        self.timer = Timer.objects.create(user=self.user, name='Sync', duration=10,
                                          interval=5, rounds=3, status='RUNNING',
                                          last_started_at=self.start)

    @patch('notifications.realtime.publish_timer_update')
    def test_repeated_polling_preserves_fractional_seconds(self, publish):
        for seconds in [1.7, 2.9, 4.2, 9.9, 10.8, 12.6, 15.9, 18.3]:
            now = self.start + timedelta(seconds=seconds)
            with patch('django.utils.timezone.now', return_value=now):
                self.timer.sync_state()
                self.timer.refresh_from_db()
        self.assertEqual(self.timer.last_started_at, self.start + timedelta(seconds=15))
        self.assertEqual(self.timer.get_current_timer_state(now), ('RUNNING', 'WORK', 2, 7))
        self.assertEqual(publish.call_count, 2)

    @patch('notifications.realtime.publish_timer_update')
    def test_response_clock_excludes_publishing_delay(self, publish):
        current = [self.start]
        def delayed_publish(*args):
            current[0] += timedelta(seconds=3)
        publish.side_effect = delayed_publish
        with patch('django.utils.timezone.now', side_effect=lambda: current[0]):
            response = self.client.post(reverse('timers:action', args=[self.timer.pk]),
                                        data='{"action":"pause"}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['server_received_at'], self.start.isoformat())
        self.assertEqual(data['server_time'], (self.start + timedelta(seconds=3)).isoformat())
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_state_endpoints_include_clock_sample_without_active_timer(self):
        self.timer.status = 'READY'
        self.timer.save()
        for url in [reverse('timers:state', args=[self.timer.pk]), reverse('timers:active_state')]:
            data = self.client.get(url).json()
            self.assertIn('server_received_at', data)
            self.assertIn('server_time', data)
