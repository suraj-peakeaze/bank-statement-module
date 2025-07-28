from django.contrib import admin
from django.urls import path, include
from eval import urls as eval_urls
from extractor import urls as extractor_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("eval/", include(eval_urls)),
    path("", include(extractor_urls)),
]
