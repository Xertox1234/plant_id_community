"""
Wagtail API serializers for plant identification models.

Provides headless CMS functionality for plant data, care guides,
and plant species pages through Wagtail API.
"""

from django.db.models import Count
from django.utils.text import Truncator
from rest_framework import serializers
from wagtail.api.v2.serializers import BaseSerializer, PageSerializer
from wagtail.images.api.fields import ImageRenditionField
from wagtail.rich_text import get_text_for_indexing

from ..models import (
    PlantCareGuide,
    PlantCategory,
    PlantCategoryIndexPage,
    PlantSpecies,
    PlantSpeciesPage,
)


def _absolute_page_url(request, page):
    """A page's absolute URL, derived from the request's own host (todo 308).

    Mirrors `apps/blog/api/serializers.py`'s helper of the same name: uses
    `get_url_parts()` rather than `get_url()` so the result never depends
    on how many Wagtail `Site` rows exist — `get_url()` prepends a
    Site-rooted absolute URL once there's more than one, which
    `request.build_absolute_uri()` would then pass through unchanged
    (wrong host). Returns None if the page isn't routable, or the bare
    relative path if called with no request.

    KNOWN GAP, not fixed here (see todo 328) — see the sibling helper's
    docstring in `apps/blog/api/serializers.py` for the full explanation:
    Wagtail's multi-Site disambiguation inside `get_url_parts()` is gated
    on `isinstance(request, HttpRequest)`, which DRF's `Request` wrapper
    fails, so it never runs here either. Deliberately not unwrapped —
    tested and found to introduce rare, unreproduced-root-cause test
    flakiness elsewhere in this codebase, not worth it for a topology
    this project doesn't use today.
    """
    url_parts = page.get_url_parts(request=request)
    page_path = url_parts[2] if url_parts else None
    if not page_path:
        return None
    return request.build_absolute_uri(page_path) if request else page_path


class PlantSpeciesSerializer(BaseSerializer):
    """Serializer for PlantSpecies model as a snippet."""

    common_name = serializers.SerializerMethodField()
    care_difficulty = serializers.SerializerMethodField()
    care_guide_url = serializers.SerializerMethodField()
    species_page_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PlantSpecies
        fields = [
            "id",
            "uuid",
            "scientific_name",
            "common_names",
            "common_name",
            "family",
            "genus",
            "species",
            "plant_type",
            "growth_habit",
            "mature_height_min",
            "mature_height_max",
            "light_requirements",
            "water_requirements",
            "hardiness_zone_min",
            "hardiness_zone_max",
            "care_difficulty",
            "care_guide_url",
            "species_page_url",
            "image_url",
        ]

    def get_common_name(self, obj):
        """Get the first common name."""
        if obj.common_names:
            return obj.common_names.split(",")[0].strip()
        return obj.scientific_name

    def get_care_difficulty(self, obj):
        """Get care difficulty from care guide if available."""
        care_guide = getattr(obj, "care_guide", None)
        if care_guide:
            return care_guide.get_care_difficulty_display()
        return None

    def get_care_guide_url(self, obj):
        """Get URL to care guide API endpoint."""
        request = self.context.get("request")
        care_guide = getattr(obj, "care_guide", None)
        if care_guide and request:
            return request.build_absolute_uri(f"/api/v2/care-guides/{care_guide.id}/")
        return None

    def get_species_page_url(self, obj):
        """Get URL to species page if available."""
        request = self.context.get("request")
        species_page = getattr(obj, "species_page", None)
        if species_page and request:
            return _absolute_page_url(request, species_page)
        return None

    def get_image_url(self, obj):
        """Get primary image URL if available."""
        species_page = getattr(obj, "species_page", None)
        if species_page and species_page.hero_image:
            request = self.context.get("request")
            rendition = species_page.hero_image.get_rendition("fill-400x300")
            if request:
                return request.build_absolute_uri(rendition.url)
            return rendition.url
        return None


class PlantCategorySerializer(BaseSerializer):
    """Serializer for PlantCategory snippets."""

    plant_count = serializers.SerializerMethodField()
    cover_image = ImageRenditionField("fill-400x300", read_only=True)
    cover_image_thumb = ImageRenditionField(
        "fill-200x150", source="cover_image", read_only=True
    )

    class Meta:
        model = PlantCategory
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "color",
            "cover_image",
            "cover_image_thumb",
            "is_featured",
            "plant_count",
            "created_at",
        ]

    def get_plant_count(self, obj):
        """Get number of plant species in this category."""
        if hasattr(obj, "_plant_count"):
            return obj._plant_count
        return obj.plant_species.count()


class PlantCareGuideSerializer(BaseSerializer):
    """Serializer for PlantCareGuide snippets."""

    plant_species = PlantSpeciesSerializer(read_only=True)
    care_level_description = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = PlantCareGuide
        fields = [
            "id",
            "plant_species",
            "care_difficulty",
            "care_level_description",
            "display_name",
            "quick_care_summary",
            "care_content",
            "light_description",
            "watering_description",
            "soil_description",
            "temperature_description",
            "humidity_description",
            "fertilizing_description",
            "propagation_methods",
            "common_problems",
            "seasonal_notes",
            "tags",
            "is_featured",
            "created_at",
            "updated_at",
        ]

    def get_tags(self, obj):
        """Get tag names."""
        return [tag.name for tag in obj.tags.all()]


class PlantSpeciesPageSerializer(PageSerializer):
    """Serializer for PlantSpeciesPage pages."""

    plant_species = PlantSpeciesSerializer(read_only=True)
    categories = PlantCategorySerializer(many=True, read_only=True)
    hero_image = ImageRenditionField("fill-800x600", read_only=True)
    hero_image_thumb = ImageRenditionField(
        "fill-400x300", source="hero_image", read_only=True
    )
    gallery_images = serializers.SerializerMethodField()
    care_guide = PlantCareGuideSerializer(
        source="plant_species.care_guide", read_only=True
    )
    excerpt = serializers.SerializerMethodField()
    related_plants = serializers.SerializerMethodField()

    class Meta:
        model = PlantSpeciesPage
        fields = ["id", "title", "slug", "url", "meta"] + [
            "plant_species",
            "introduction",
            "content_blocks",
            "hero_image",
            "hero_image_thumb",
            "gallery_images",
            "categories",
            "is_featured",
            "care_guide",
            "excerpt",
            "related_plants",
        ]

    def get_gallery_images(self, obj):
        """Get gallery image renditions."""
        request = self.context.get("request")
        images = []

        for image in obj.gallery_images.all():
            rendition = image.get_rendition("fill-400x300")
            thumb = image.get_rendition("fill-200x150")

            image_data = {
                "id": image.id,
                "title": image.title,
                "alt": image.title,
                "url": (
                    request.build_absolute_uri(rendition.url)
                    if request
                    else rendition.url
                ),
                "thumb": (
                    request.build_absolute_uri(thumb.url) if request else thumb.url
                ),
            }
            images.append(image_data)

        return images

    def get_excerpt(self, obj):
        """Get excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(50)
        return ""

    def get_related_plants(self, obj):
        """Get related plant species pages."""
        from django.db.models import Q

        related_plants = (
            PlantSpeciesPage.objects.live()
            .public()
            .exclude(id=obj.id)
            .filter(
                Q(plant_species__family=obj.plant_species.family)
                | Q(categories__in=obj.categories.all())
            )
            .distinct()[:4]
        )

        request = self.context.get("request")
        return [
            {
                "id": plant.id,
                "title": plant.title,
                "slug": plant.slug,
                "url": _absolute_page_url(request, plant),
                "scientific_name": plant.plant_species.scientific_name,
                "common_name": (
                    plant.plant_species.common_names.split(",")[0].strip()
                    if plant.plant_species.common_names
                    else plant.plant_species.scientific_name
                ),
                "hero_image": self._get_plant_image(plant, request),
            }
            for plant in related_plants
        ]

    def _get_plant_image(self, plant, request):
        """Get plant hero image URL."""
        if plant.hero_image:
            rendition = plant.hero_image.get_rendition("fill-300x200")
            if request:
                return request.build_absolute_uri(rendition.url)
            return rendition.url
        return None


class PlantSpeciesPageListSerializer(PageSerializer):
    """Lighter serializer for plant species page lists."""

    plant_species = PlantSpeciesSerializer(read_only=True)
    categories = PlantCategorySerializer(many=True, read_only=True)
    hero_image_thumb = ImageRenditionField(
        "fill-300x200", source="hero_image", read_only=True
    )
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = PlantSpeciesPage
        fields = ["id", "title", "slug", "url", "meta"] + [
            "plant_species",
            "hero_image_thumb",
            "categories",
            "is_featured",
            "excerpt",
        ]

    def get_excerpt(self, obj):
        """Get short excerpt from introduction."""
        if obj.introduction:
            text = get_text_for_indexing(obj.introduction)
            return Truncator(text).words(30)
        return ""


class PlantCategoryIndexPageSerializer(PageSerializer):
    """Serializer for PlantCategoryIndexPage."""

    categories = serializers.SerializerMethodField()
    featured_plants = serializers.SerializerMethodField()

    class Meta:
        model = PlantCategoryIndexPage
        fields = ["id", "title", "slug", "url", "meta"] + [
            "introduction",
            "categories_per_page",
            "show_featured_plants",
            "categories",
            "featured_plants",
        ]

    def get_categories(self, obj):
        """Get featured plant categories."""
        featured_categories = PlantCategory.objects.filter(is_featured=True).annotate(
            _plant_count=Count("plant_species", distinct=True)
        )
        return PlantCategorySerializer(
            featured_categories, many=True, context=self.context
        ).data

    def get_featured_plants(self, obj):
        """Get featured plants if enabled."""
        if not obj.show_featured_plants:
            return []

        featured_plants = (
            PlantSpeciesPage.objects.live().public().filter(is_featured=True)[:6]
        )

        return PlantSpeciesPageListSerializer(
            featured_plants, many=True, context=self.context
        ).data
