from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Timer
import datetime

User = get_user_model()

class TimerStateTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.timer = Timer.objects.create(
            user=self.user,
            name='Workout',
            rounds=3,
            duration=180,  # 3 mins
            interval=60,   # 1 min rest
            direction='DOWN',
            status='READY'
        )

    def test_initial_state(self):
        self.assertEqual(self.timer.status, 'READY')
        self.assertEqual(self.timer.time_remaining, 180)
        self.assertEqual(self.timer.current_round, 1)
        self.assertEqual(self.timer.current_state, 'WORK')

    def test_start_timer(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        self.timer.last_started_at = now
        self.timer.save()
        
        status, state, round_num, remaining = self.timer.get_current_timer_state()
        self.assertEqual(status, 'RUNNING')
        self.assertEqual(state, 'WORK')
        self.assertEqual(round_num, 1)
        self.assertEqual(remaining, 180)

    def test_running_work_no_transition(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        self.timer.last_started_at = now - datetime.timedelta(seconds=60)
        self.timer.save()
        
        status, state, round_num, remaining = self.timer.get_current_timer_state()
        self.assertEqual(status, 'RUNNING')
        self.assertEqual(state, 'WORK')
        self.assertEqual(round_num, 1)
        self.assertEqual(remaining, 120)

    def test_transition_to_rest(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        # Started 210 seconds ago. Work duration is 180, so 30 seconds into Rest round 1
        self.timer.last_started_at = now - datetime.timedelta(seconds=210)
        self.timer.save()
        
        status, state, round_num, remaining = self.timer.get_current_timer_state()
        self.assertEqual(status, 'RUNNING')
        self.assertEqual(state, 'REST')
        self.assertEqual(round_num, 1)
        self.assertEqual(remaining, 30)

    def test_transition_to_round_2_work(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        # Started 270 seconds ago:
        # Round 1 Work: 180s
        # Round 1 Rest: 60s
        # Round 2 Work: 30s elapsed, 150s remaining
        self.timer.last_started_at = now - datetime.timedelta(seconds=270)
        self.timer.save()
        
        status, state, round_num, remaining = self.timer.get_current_timer_state()
        self.assertEqual(status, 'RUNNING')
        self.assertEqual(state, 'WORK')
        self.assertEqual(round_num, 2)
        self.assertEqual(remaining, 150)

    def test_timer_finishes(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        # Total duration for 3 rounds:
        # Round 1 Work (180) + Rest (60) + Round 2 Work (180) + Rest (60) + Round 3 Work (180) = 660s
        self.timer.last_started_at = now - datetime.timedelta(seconds=700)
        self.timer.save()
        
        status, state, round_num, remaining = self.timer.get_current_timer_state()
        self.assertEqual(status, 'DONE')
        self.assertEqual(remaining, 0)

    def test_sync_state(self):
        now = timezone.now()
        self.timer.status = 'RUNNING'
        # 210 seconds ago -> Rest round 1, remaining 30s
        self.timer.last_started_at = now - datetime.timedelta(seconds=210)
        self.timer.save()
        
        # Trigger sync
        self.timer.sync_state(save=True)
        
        # Re-fetch from DB
        timer_db = Timer.objects.get(id=self.timer.id)
        self.assertEqual(timer_db.status, 'RUNNING')
        self.assertEqual(timer_db.current_state, 'REST')
        self.assertEqual(timer_db.current_round, 1)
        
        elapsed_since_started = (timezone.now() - timer_db.last_started_at).total_seconds()
        self.assertTrue(28 <= elapsed_since_started <= 32)
        self.assertEqual(timer_db.time_remaining, 60)
