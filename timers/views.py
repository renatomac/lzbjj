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
