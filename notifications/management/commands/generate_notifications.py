"""
Management command to generate notifications.

Usage:
    python manage.py generate_notifications
    python manage.py generate_notifications --type birthday
    python manage.py generate_notifications --type promotion_milestone
    python manage.py generate_notifications --type low_attendance
    python manage.py generate_notifications --type all
"""

from django.core.management.base import BaseCommand
from notifications.notifications import (
    generate_birthday_notifications,
    generate_promotion_milestone_notifications,
    generate_low_attendance_notifications,
    generate_membership_expiration_warnings,
    generate_streak_milestone_notifications,
    generate_waiver_expiration_warnings,
    run_all_notifications,
)


class Command(BaseCommand):
    help = 'Generate and send notifications to members'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='all',
            help='Type of notification to generate (birthday, promotion_milestone, low_attendance, membership_expiring, streak_milestone, waiver_expiring, all)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with notification details',
        )

    def handle(self, *args, **options):
        notification_type = options['type'].lower()
        verbose = options['verbose']

        results = {}

        if notification_type in ['birthday', 'all']:
            self.stdout.write("Generating birthday notifications...")
            results['birthday'] = generate_birthday_notifications()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Birthday notifications: {len(results['birthday'])} sent")
            )
            if verbose and results['birthday']:
                for notif in results['birthday']:
                    self.stdout.write(f"  - {notif.message}")

        if notification_type in ['promotion_milestone', 'all']:
            self.stdout.write("Generating promotion milestone notifications...")
            results['promotion_milestone'] = generate_promotion_milestone_notifications()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Promotion milestone notifications: {len(results['promotion_milestone'])} sent")
            )
            if verbose and results['promotion_milestone']:
                for notif in results['promotion_milestone']:
                    self.stdout.write(f"  - {notif.message}")

        if notification_type in ['low_attendance', 'all']:
            self.stdout.write("Generating low attendance notifications...")
            results['low_attendance'] = generate_low_attendance_notifications()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Low attendance notifications: {len(results['low_attendance'])} sent")
            )
            if verbose and results['low_attendance']:
                for notif in results['low_attendance']:
                    self.stdout.write(f"  - {notif.message}")

        if notification_type in ['membership_expiring', 'all']:
            self.stdout.write("Generating membership expiration warnings...")
            results['membership_expiring'] = generate_membership_expiration_warnings()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Membership expiration warnings: {len(results['membership_expiring'])} sent")
            )
            if verbose and results['membership_expiring']:
                for notif in results['membership_expiring']:
                    self.stdout.write(f"  - {notif.message}")

        if notification_type in ['streak_milestone', 'all']:
            self.stdout.write("Generating streak milestone notifications...")
            results['streak_milestone'] = generate_streak_milestone_notifications()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Streak milestone notifications: {len(results['streak_milestone'])} sent")
            )
            if verbose and results['streak_milestone']:
                for notif in results['streak_milestone']:
                    self.stdout.write(f"  - {notif.message}")

        if notification_type in ['waiver_expiring', 'all']:
            self.stdout.write("Generating waiver expiration warnings...")
            results['waiver_expiring'] = generate_waiver_expiration_warnings()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Waiver expiration warnings: {len(results['waiver_expiring'])} sent")
            )
            if verbose and results['waiver_expiring']:
                for notif in results['waiver_expiring']:
                    self.stdout.write(f"  - {notif.message}")

        # Print summary
        total = sum(len(v) for v in results.values() if isinstance(v, list))
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Total notifications generated: {total}")
        )
