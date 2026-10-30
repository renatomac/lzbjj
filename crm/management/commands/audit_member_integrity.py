"""Read-only targeted checks for login links and current promotion state."""
from django.core.management.base import BaseCommand
from crm.models import BeltPromotion, Member, User


class Command(BaseCommand):
    help = 'Inspect account/member links and rank history without modifying records.'

    def add_arguments(self, parser):
        parser.add_argument('--email')
        parser.add_argument('--first-name')
        parser.add_argument('--last-name')

    def handle(self, *args, **options):
        if options['email']:
            accounts = User.objects.filter(email__iexact=options['email'])
            for account in accounts:
                self.stdout.write(f'Account #{account.pk}: {account.email}; account name: {account.get_full_name() or "(blank)"}')
                linked = list(Member.objects.filter(user=account))
                for member in linked:
                    self.stdout.write(f'Linked member #{member.pk}: {member.first_name} {member.last_name}')
                if not linked:
                    self.stdout.write('No linked member.')
            if not accounts:
                self.stdout.write('No matching account.')
        if options['first_name'] and options['last_name']:
            members = Member.objects.filter(first_name__iexact=options['first_name'], last_name__iexact=options['last_name'])
            for member in members:
                latest = BeltPromotion.objects.filter(member=member).order_by('-promotion_date', '-created_at', '-pk').first()
                self.stdout.write(f'Member #{member.pk}: {member.first_name} {member.last_name}; stored rank: {member.belt_rank}, {member.stripes} stripes')
                if latest:
                    matches = (member.belt_rank, member.stripes) == (latest.new_rank, latest.new_stripes)
                    self.stdout.write(f'Latest award #{latest.pk} ({latest.promotion_date}): {latest.new_rank}, {latest.new_stripes} stripes; {"MATCH" if matches else "MISMATCH"}')
                else:
                    self.stdout.write('No promotion history.')
            if not members:
                self.stdout.write('No matching member.')
        self.stdout.write('Read-only audit complete; no records changed.')
