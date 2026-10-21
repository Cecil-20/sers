from rest_framework.routers import DefaultRouter
from .views import ResponseTeamViewSet, EmergencyCategoryViewSet

router = DefaultRouter()
router.register('response-teams', ResponseTeamViewSet)
router.register('categories', EmergencyCategoryViewSet)

urlpatterns = router.urls
