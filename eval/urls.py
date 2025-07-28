from django.urls import path
from . import views

app_name = "eval"

urlpatterns = [
    path("", views.EvalView, name="eval"),
]
