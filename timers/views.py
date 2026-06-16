from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Timer
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
