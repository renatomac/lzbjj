from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Timer, SpotifyAccount
from .forms import TimerForm

class TimerListView(LoginRequiredMixin, ListView):
    model = Timer
    template_name = 'timers/timer_list.html'
    context_object_name = 'timers'

    def get_queryset(self):
        return Timer.objects.filter(user=self.request.user).order_by('-created_at')

class TimerCreateView(LoginRequiredMixin, CreateView):
    model = Timer
    form_class = TimerForm
    template_name = 'timers/timer_form.html'
    success_url = reverse_lazy('timers:list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class TimerUpdateView(LoginRequiredMixin, UpdateView):
    model = Timer
    form_class = TimerForm
    template_name = 'timers/timer_form.html'
    success_url = reverse_lazy('timers:list')

    def get_queryset(self):
        return Timer.objects.filter(user=self.request.user)

class TimerDeleteView(LoginRequiredMixin, DeleteView):
    model = Timer
    template_name = 'timers/timer_confirm_delete.html'
    success_url = reverse_lazy('timers:list')

    def get_queryset(self):
        return Timer.objects.filter(user=self.request.user)

class TimerRunView(LoginRequiredMixin, DetailView):
    model = Timer
    template_name = 'timers/timer_run.html'
    context_object_name = 'timer'

    def get_queryset(self):
        return Timer.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.sync_state()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['spotify_configured'] = spotify_client.is_configured()
        return context

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
import json

@login_required
def active_timer_state(request):
    timer = Timer.objects.filter(user=request.user, status__in=['RUNNING', 'PAUSED']).first()
    if not timer:
        return JsonResponse({'active': False})
    
    timer.sync_state()
    data = timer.to_dict()
    data['active'] = True
    return JsonResponse(data)

@login_required
def timer_state(request, pk):
    try:
        timer = Timer.objects.get(pk=pk, user=request.user)
    except Timer.DoesNotExist:
        return JsonResponse({'error': 'Timer not found'}, status=404)
        
    timer.sync_state()
    return JsonResponse(timer.to_dict())

@login_required
@require_POST
def timer_action(request, pk):
    try:
        timer = Timer.objects.get(pk=pk, user=request.user)
    except Timer.DoesNotExist:
        return JsonResponse({'error': 'Timer not found'}, status=404)
        
    try:
        data = json.loads(request.body)
        action = data.get('action')
    except (json.JSONDecodeError, TypeError):
        action = request.POST.get('action')
        
    if not action or action not in ['start', 'pause', 'reset']:
        return JsonResponse({'error': 'Invalid or missing action'}, status=400)
        
    if action == 'start':
        # Pause/Reset other active timers for this user
        other_timers = Timer.objects.filter(user=request.user, status__in=['RUNNING', 'PAUSED']).exclude(id=timer.id)
        for ot in other_timers:
            ot.status = 'READY'
            ot.time_remaining = ot.duration
            ot.current_round = 1
            ot.current_state = 'WORK'
            ot.last_started_at = None
            ot.save(update_fields=['status', 'time_remaining', 'current_round', 'current_state', 'last_started_at'])
            # Publish change to Ably
            try:
                from notifications.realtime import publish_timer_update
                publish_timer_update(request.user.id, ot.to_dict())
            except Exception:
                pass
                
        if timer.status in ['READY', 'DONE']:
            timer.status = 'RUNNING'
            timer.current_round = 1
            timer.current_state = 'WORK'
            timer.time_remaining = timer.duration
            timer.last_started_at = timezone.now()
        elif timer.status == 'PAUSED':
            timer.status = 'RUNNING'
            timer.last_started_at = timezone.now()
            
    elif action == 'pause':
        timer.sync_state(save=False)
        if timer.status == 'RUNNING':
            _, _, _, remaining = timer.get_current_timer_state()
            timer.status = 'PAUSED'
            timer.time_remaining = remaining
            timer.last_started_at = None
            
    elif action == 'reset':
        timer.status = 'READY'
        timer.current_round = 1
        timer.current_state = 'WORK'
        timer.time_remaining = timer.duration
        timer.last_started_at = None
        
    timer.save(update_fields=['status', 'current_round', 'current_state', 'time_remaining', 'last_started_at'])
    
    # Publish update to Ably
    try:
        from notifications.realtime import publish_timer_update
        publish_timer_update(request.user.id, timer.to_dict())
    except Exception as e:
        print(f"Ably action publish failed: {e}")
        
    return JsonResponse(timer.to_dict())


# =============================================================================
# Spotify integration: OAuth connect flow + playlist/device/playback controls
# =============================================================================
import secrets

from django.contrib import messages
from django.utils import timezone as tz

from . import spotify_client
from .spotify_client import SpotifyPlaybackError


@login_required
def spotify_connect(request):
    if not spotify_client.is_configured():
        messages.error(request, "Spotify integration is not configured. Contact an administrator.")
        return redirect('timers:list')

    state = secrets.token_urlsafe(24)
    request.session['spotify_oauth_state'] = state
    request.session['spotify_return_to'] = request.GET.get('next') or reverse_lazy('timers:list')
    return redirect(spotify_client.build_authorize_url(state))


@login_required
def spotify_callback(request):
    return_to = request.session.pop('spotify_return_to', None) or reverse_lazy('timers:list')
    expected_state = request.session.pop('spotify_oauth_state', None)
    error = request.GET.get('error')
    code = request.GET.get('code')
    state = request.GET.get('state')

    if error:
        messages.error(request, f"Spotify authorization was cancelled: {error}")
        return redirect(return_to)

    if not code or not state or state != expected_state:
        messages.error(request, "Spotify authorization failed (invalid state). Please try again.")
        return redirect(return_to)

    try:
        tokens = spotify_client.exchange_code_for_tokens(code)
        account, _ = SpotifyAccount.objects.get_or_create(user=request.user, defaults={
            'access_token': '',
            'refresh_token': '',
            'expires_at': tz.now(),
        })
        account.access_token = tokens['access_token']
        account.refresh_token = tokens.get('refresh_token') or account.refresh_token
        account.expires_at = tz.now() + tz.timedelta(seconds=tokens.get('expires_in', 3600))

        profile = spotify_client.get_current_user(account)
        account.spotify_user_id = profile.get('id', '')
        account.display_name = profile.get('display_name') or profile.get('id', '')
        account.save()

        messages.success(request, f"Connected to Spotify as {account.display_name}.")
    except Exception as exc:
        messages.error(request, f"Could not connect to Spotify: {exc}")

    return redirect(return_to)


@login_required
def spotify_disconnect(request):
    SpotifyAccount.objects.filter(user=request.user).delete()
    messages.success(request, "Disconnected your Spotify account.")
    return redirect(request.GET.get('next') or 'timers:list')


@login_required
def spotify_status(request):
    account = SpotifyAccount.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({'connected': False, 'configured': spotify_client.is_configured()})
    return JsonResponse({
        'connected': True,
        'configured': True,
        'display_name': account.display_name,
        'last_playlist_uri': account.last_playlist_uri,
        'last_device_id': account.last_device_id,
    })


@login_required
def spotify_playlists(request):
    account = SpotifyAccount.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({'error': 'Spotify account not connected'}, status=400)
    try:
        playlists = spotify_client.get_playlists(account)
        return JsonResponse({'playlists': playlists})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@login_required
def spotify_devices(request):
    account = SpotifyAccount.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({'error': 'Spotify account not connected'}, status=400)
    try:
        devices = spotify_client.get_devices(account)
        return JsonResponse({'devices': devices})
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=502)


@login_required
@require_POST
def spotify_control(request):
    account = SpotifyAccount.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({'error': 'Spotify account not connected'}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        data = request.POST

    action = data.get('action')
    playlist_uri = data.get('playlist_uri')
    device_id = data.get('device_id')

    if action not in ('play', 'pause', 'stop', 'next', 'previous'):
        return JsonResponse({'error': 'Invalid or missing action'}, status=400)

    if playlist_uri:
        account.last_playlist_uri = playlist_uri
    if device_id:
        account.last_device_id = device_id
    if playlist_uri or device_id:
        account.save(update_fields=['last_playlist_uri', 'last_device_id', 'updated_at'])

    device_id = device_id or account.last_device_id or None

    try:
        if action == 'play':
            spotify_client.start_playback(account, playlist_uri=playlist_uri or account.last_playlist_uri, device_id=device_id)
        elif action in ('pause', 'stop'):
            spotify_client.pause_playback(account, device_id=device_id)
        elif action == 'next':
            spotify_client.next_track(account, device_id=device_id)
        elif action == 'previous':
            spotify_client.previous_track(account, device_id=device_id)
    except SpotifyPlaybackError as exc:
        return JsonResponse({'error': str(exc)}, status=409)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=502)

    return JsonResponse({'status': 'ok', 'action': action})
