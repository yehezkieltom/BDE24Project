from django.urls import path

from fame.views.html import fame_list, experts_view, bullshitters_view
from fame.views.rest import ExpertiseAreasApiView, FameUsersApiView, FameListApiView
from . import views

app_name = "fame"

urlpatterns = [
    path(
        "api/expertise_areas", ExpertiseAreasApiView.as_view(), name="expertise_areas"
    ),
    path("api/users", FameUsersApiView.as_view(), name="fame_users"),
    path("api/fame", FameListApiView.as_view(), name="fame_fulllist"),
    path("html/fame", fame_list, name="fame_list"),
    #add the new url for the experts view
    path("html/experts", experts_view, name="experts_view"),
    path("html/bullshitters", bullshitters_view, name="bullshitters_view")


]
