from django.db.models import Q

from fame.models import Fame, FameLevels, FameUsers
from socialnetwork.models import PostExpertiseAreasAndRatings, Posts, SocialNetworkUsers, ExpertiseAreas

# general methods independent of html and REST views
# should be used by REST and html views


def _get_social_network_user(user) -> SocialNetworkUsers:
    """Given a FameUser, gets the social network user from the request. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise PermissionError("User does not exist")
    return user


def timeline(user: SocialNetworkUsers, start: int = 0, end: int = None, published=True):
    """Get the timeline of the user. Assumes that the user is authenticated."""
    _follows = user.follows.all()
    posts = Posts.objects.filter(
        (Q(author__in=_follows) & Q(published=published)) | Q(author=user)
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start : end + 1]


def search(keyword: str, start: int = 0, end: int = None, published=True):
    """Search for all posts in the system containing the keyword. Assumes that all posts are public"""
    posts = Posts.objects.filter(
        Q(content__icontains=keyword)
        | Q(author__email__icontains=keyword)
        | Q(author__first_name__icontains=keyword)
        | Q(author__last_name__icontains=keyword),
        published=published,
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start : end + 1]


def follows(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the users followed by this user. Assumes that the user is authenticated."""
    _follows = user.follows.all()
    if end is None:
        return _follows[start:]
    else:
        return _follows[start : end + 1]


def followers(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the followers of this user. Assumes that the user is authenticated."""
    _followers = user.followed_by.all()
    if end is None:
        return _followers[start:]
    else:
        return _followers[start : end + 1]


def follow(user: SocialNetworkUsers, user_to_follow: SocialNetworkUsers):
    """Follow a user. Assumes that the user is authenticated. If user already follows the user, signal that."""
    if user_to_follow in user.follows.all():
        return {"followed": False}
    user.follows.add(user_to_follow)
    user.save()
    return {"followed": True}


def unfollow(user: SocialNetworkUsers, user_to_unfollow: SocialNetworkUsers):
    """Unfollow a user. Assumes that the user is authenticated. If user does not follow the user anyway, signal that."""
    if user_to_unfollow not in user.follows.all():
        return {"unfollowed": False}
    user.follows.remove(user_to_unfollow)
    user.save()
    return {"unfollowed": True}


def submit_post(
    user: SocialNetworkUsers,
    content: str,
    cites: Posts = None,
    replies_to: Posts = None,
):
    """Submit a post for publication. Assumes that the user is authenticated.
    returns a tuple of three elements:
    1. a dictionary with the keys "published" and "id" (the id of the post)
    2. a list of dictionaries containing the expertise areas and their truth ratings
    3. a boolean indicating whether the user was banned and logged out and should be redirected to the login page
    """

    # create post  instance:
    post = Posts.objects.create(
        content=content,
        author=user,
        cites=cites,
        replies_to=replies_to,
    )

    # classify the content into expertise areas:
    # only publish the post if none of the expertise areas contains bullshit:
    _at_least_one_expertise_area_contains_bullshit, _expertise_areas = (
        post.determine_expertise_areas_and_truth_ratings()
    )
    post.published = not _at_least_one_expertise_area_contains_bullshit

    redirect_to_logout = False


    #########################
    # add your code here
    # prep work to minimize query calls to the database(idk if this true tho, perhaps only making alias)
    # after doing T2a perhaps this is not needed lol
    user_expertise = Fame.objects.filter(user=user)
    # T1
    # Fetch the fame level tied to the user and get any expertise area with

    negative_user_expertise = user_expertise.filter(
        fame_level__numeric_value__lt=0
        ).values("expertise_area")
    if negative_user_expertise.count() > 0:
        post.published = False

    # T2a
    # Fetch the newly assigned negative truth ratings by magic AI and lower the fame level of the user expertise area
    negative_truth_ratings = PostExpertiseAreasAndRatings.objects.filter(
        post=post, truth_rating__numeric_value__lt=0
    ).values("expertise_area")
    for ntr in negative_truth_ratings:
        #using filter.first() because catching the exception with get() is just not possible(tried it many times)
        #deteriorating_user_expertise can be empty. The if statement will handle each case
        deteriorating_user_expertise = Fame.objects.filter(
                user=user, expertise_area=ntr["expertise_area"]
                ).first()
        if deteriorating_user_expertise is None:
            #T2b
            new_area = ExpertiseAreas.objects.get(id=ntr["expertise_area"])
            new_bad_user_expertise = Fame.objects.create(
                user=user,
                expertise_area=new_area,
                fame_level=FameLevels.objects.get(name="Confuser")
            )
            new_bad_user_expertise.save()
            continue
        #try except block to handle the case where the user is already at the lowest fame level
        try:
            lower_level = deteriorating_user_expertise.fame_level.get_next_lower_fame_level()
            #T2a
            deteriorating_user_expertise.fame_level = lower_level
            deteriorating_user_expertise.save()
        except ValueError:
            #T2c
            FameUsers.objects.filter(id=user.id).update(is_active=False)
            Posts.objects.filter(author=user).update(published=False)
            redirect_to_logout = True
    #########################
    post.save()

    return (
        {"published": post.published, "id": post.id},
        _expertise_areas,
        redirect_to_logout,
    )


def rate_post(
    user: SocialNetworkUsers, post: Posts, rating_type: str, rating_score: int
):
    """Rate a post. Assumes that the user is authenticated. If user already rated the post with the given rating_type,
    update that rating score."""
    user_rating = None
    try:
        user_rating = user.userratings_set.get(post=post, rating_type=rating_type)
    except user.userratings_set.model.DoesNotExist:
        pass

    if user == post.author:
        raise PermissionError(
            "User is the author of the post. You cannot rate your own post."
        )

    if user_rating is not None:
        # update the existing rating:
        user_rating.rating_score = rating_score
        user_rating.save()
        return {"rated": True, "type": "update"}
    else:
        # create a new rating:
        user.userratings_set.add(
            post,
            through_defaults={"rating_type": rating_type, "rating_score": rating_score},
        )
        user.save()
        return {"rated": True, "type": "new"}


def fame(user: SocialNetworkUsers):
    """Get the fame of a user. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise ValueError("User does not exist")

    return user, Fame.objects.filter(user=user)




def experts():
    """Return for each existing expertise area in the fame profiles a list of the users having positive fame for that
    expertise area. The list should be a Python dictionary with keys ``user'' (for the user) and ``fame_level_numeric''
    (for the corresponding fame value), and should be ranked, i.e. users with the highest fame are shown first, in case
    there is a tie, within that tie sort by date_joined (most recent first). Note that expertise areas with no expert
    may be omitted.
    """
    # pass
    #########################
    # add your code here
    complete_expert_list = dict()
    expertise_areas = ExpertiseAreas.objects.all()
    for area in expertise_areas:
        area_experts = []
        experts = Fame.objects.filter(
            expertise_area=area,
            fame_level__numeric_value__gt=0
            ).order_by(
            "-fame_level__numeric_value", "-user__date_joined"
            ).values("user", "fame_level__numeric_value")
        if experts.count() == 0:
            continue
        for expert in experts:
            area_expert = {
                "user": FameUsers.objects.get(id=expert["user"]),
                "fame_level_numeric": expert["fame_level__numeric_value"]
            }
            area_experts.append(area_expert)
        complete_expert_list[area] = area_experts

    return complete_expert_list
    #########################



def bullshitters():
    """Return for each existing expertise area in the fame profiles a list of the users having negative fame for that
    expertise area. The list should be a Python dictionary with keys ``user'' (for the user) and ``fame_level_numeric''
    (for the corresponding fame value), and should be ranked, i.e. users with the lowest fame are shown first, in case
    there is a tie, within that tie sort by date_joined (most recent first). Note that expertise areas with no expert
    may be omitted.
    """
    # pass
    #########################
    # add your code here
    complete_bullshitter_list = dict()
    expertise_areas = ExpertiseAreas.objects.all()
    for area in expertise_areas:
        area_experts = []
        bullshitters = Fame.objects.filter(
            expertise_area=area,
            fame_level__numeric_value__lt=0
            ).order_by(
            "fame_level__numeric_value", "-user__date_joined"
            ).values("user", "fame_level__numeric_value")
        if bullshitters.count() == 0:
            continue
        for bullshitter in bullshitters:
            area_expert = {
                "user": FameUsers.objects.get(id=bullshitter["user"]),
                "fame_level_numeric": bullshitter["fame_level__numeric_value"]
            }
            area_experts.append(area_expert)
        complete_bullshitter_list[area] = area_experts
    return complete_bullshitter_list
    #########################

