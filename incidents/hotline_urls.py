from django.urls import path
from .hotline import HotlineCallView, HotlineNumbersView

urlpatterns = [
    path('numbers/', HotlineNumbersView.as_view()),
    path('calls/', HotlineCallView.as_view()),
]
