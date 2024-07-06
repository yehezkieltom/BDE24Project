from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from socialnetwork.api import experts, bullshitters
from fame.serializers import FameSerializer
from socialnetwork import api
from socialnetwork.api import _get_social_network_user
from socialnetwork.models import SocialNetworkUsers


@require_http_methods(["GET"])
@login_required
def fame_list(request):
    # try to get the user from the request parameters:
    userid = request.GET.get("userid", None)
    user = None
    if userid is None:
        user = _get_social_network_user(request.user)
    else:
        try:
            user = SocialNetworkUsers.objects.get(id=userid)
        except ValueError:
            pass

    user, fame = api.fame(user)
    context = {
        "fame": FameSerializer(fame, many=True).data,
        "user": user if user else "",
    }
    return render(request, "fame.html", context=context)

#create a view like for fame one
"""
The render function in Django is used to generate a HTML webpage as
 a response to a HTTP request. It takes a request object, 
 a template name, and an optional context dictionary as arguments.
 In our case we use these data in the html file
"""
@login_required
def experts_view(request):
    experts_data = experts()
    return render(request, "fame_experts.html", {"experts": experts_data})

@login_required
def bullshitters_view(request):
    bullshitters_data = bullshitters()
    return render(request, "fame_bull.html", {"bullshitters": bullshitters_data})
