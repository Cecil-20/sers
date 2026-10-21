from rest_framework.routers import SimpleRouter
from .manage_api import AccountAdminViewSet, CategoryAdminViewSet, TeamAdminViewSet

router = SimpleRouter()
router.register('teams', TeamAdminViewSet, basename='manage-team')
router.register('categories', CategoryAdminViewSet, basename='manage-category')
router.register('accounts', AccountAdminViewSet, basename='manage-account')

urlpatterns = router.urls
