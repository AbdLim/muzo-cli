"""Registry for built-in and future community scenes."""

import re
from dataclasses import dataclass

from muzo.scenes.base import Scene

_KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class RegistryError(Exception):
    """Base exception for scene registry operations."""


class DuplicateSceneError(RegistryError):
    """Raised when attempting to register a scene with an already registered ID."""


class SceneNotFoundError(RegistryError):
    """Raised when looking up an unregistered scene ID."""


@dataclass(frozen=True, slots=True)
class SceneInfo:
    """Immutable metadata describing an available scene."""

    id: str
    name: str
    description: str
    is_ambient: bool = True


class SceneRegistry:
    """Manages scene type registration, lookup, and metadata listing."""

    def __init__(self) -> None:
        self._scenes: dict[str, type[Scene]] = {}

    def register(self, scene_type: type[Scene]) -> None:
        """Register a scene class.

        Args:
            scene_type: Subclass of Scene to register.

        Raises:
            TypeError: If scene_type is not a subclass of Scene.
            ValueError: If the scene class has an invalid ID, name, or description.
            DuplicateSceneError: If a scene with this ID is already registered.
        """
        if not isinstance(scene_type, type) or not issubclass(scene_type, Scene):
            raise TypeError(f"Expected a subclass of Scene, got {scene_type!r}.")

        scene_id = getattr(scene_type, "id", None)
        scene_name = getattr(scene_type, "name", None)
        scene_desc = getattr(scene_type, "description", None)

        if not isinstance(scene_id, str) or not _KEBAB_CASE_PATTERN.match(scene_id):
            raise ValueError(
                f"Scene ID must be non-empty ASCII lowercase kebab-case "
                f"(e.g. 'rainy-window'), got {scene_id!r}."
            )

        if not isinstance(scene_name, str) or not scene_name.strip():
            raise ValueError(f"Scene name must be a non-empty string, got {scene_name!r}.")

        if not isinstance(scene_desc, str) or not scene_desc.strip():
            raise ValueError(f"Scene description must be a non-empty string, got {scene_desc!r}.")

        if scene_id in self._scenes:
            raise DuplicateSceneError(f"Scene with ID '{scene_id}' is already registered.")

        self._scenes[scene_id] = scene_type

    def get(self, scene_id: str) -> type[Scene]:
        """Retrieve a registered scene class by ID."""
        if scene_id not in self._scenes:
            raise SceneNotFoundError(f"Unknown scene ID: '{scene_id}'.")
        return self._scenes[scene_id]

    def create(self, scene_id: str) -> Scene:
        """Instantiate and return a scene by ID."""
        scene_cls = self.get(scene_id)
        return scene_cls()

    def list_scenes(self, ambient_only: bool = False) -> tuple[SceneInfo, ...]:
        """Return an immutable list of metadata for registered scenes, sorted by ID."""
        scenes = tuple(
            SceneInfo(
                id=cls.id,
                name=cls.name,
                description=cls.description,
                is_ambient=getattr(cls, "is_ambient", True),
            )
            for _, cls in sorted(self._scenes.items(), key=lambda item: item[0])
        )
        if ambient_only:
            return tuple(s for s in scenes if s.is_ambient)
        return scenes

    def list_ambient_scenes(self) -> tuple[SceneInfo, ...]:
        """Return ambient scenes in curated presentation order for the UI picker."""
        preferred_order = ("rainy-window", "horizon", "stargazing", "fireplace")
        ambient_map = {s.id: s for s in self.list_scenes(ambient_only=True)}
        ordered: list[SceneInfo] = []
        for scene_id in preferred_order:
            if scene_id in ambient_map:
                ordered.append(ambient_map.pop(scene_id))
        for scene_id in sorted(ambient_map.keys()):
            ordered.append(ambient_map[scene_id])
        return tuple(ordered)

    def is_registered(self, scene_id: str) -> bool:
        """Check if a scene ID is registered."""
        return scene_id in self._scenes


def register_builtin_scenes(registry: SceneRegistry) -> None:
    """Register all built-in Muzo scenes into the provided registry."""
    from muzo.scenes.builtin.fireplace import FireplaceScene
    from muzo.scenes.builtin.horizon import HorizonScene
    from muzo.scenes.builtin.rain import RainyWindowScene
    from muzo.scenes.builtin.stars import StargazingScene
    from muzo.scenes.builtin.welcome import WelcomeScene

    registry.register(RainyWindowScene)
    registry.register(HorizonScene)
    registry.register(StargazingScene)
    registry.register(FireplaceScene)
    registry.register(WelcomeScene)


def create_default_registry() -> SceneRegistry:
    """Create a new SceneRegistry populated with built-in scenes."""
    registry = SceneRegistry()
    register_builtin_scenes(registry)
    return registry
