def test_package_imports():
    import wagtail_forum  # noqa: F401
    from wagtail_forum.apps import WagtailForumAppConfig

    assert WagtailForumAppConfig.label == "wagtail_forum"


def test_app_is_installed():
    from django.apps import apps

    assert apps.is_installed("wagtail_forum")
