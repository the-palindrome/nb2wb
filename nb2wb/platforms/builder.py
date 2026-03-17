"""
Generic platform builder driven by target profiles and feature options.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ._templates import COPYABLE_SCRIPT, SIMPLE_COPY_SCRIPT, build_page
from .base import PlatformBuilder
from .profiles import (
    COPY_SCRIPT_MODES,
    IMAGE_STRATEGIES,
    TargetProfile,
)


@dataclass(frozen=True)
class TargetPageOptions:
    """Optional overrides for profile defaults."""

    image_strategy: str | None = None
    raw_image_strategy: str | None = None
    copy_script_mode: str | None = None
    article_width_px: int | None = None
    table_mode: str | None = None
    toolbar_message: str | None = None
    theme_overrides: dict[str, str] = field(default_factory=dict)


def normalize_page_options(
    options: Mapping[str, object] | TargetPageOptions | None,
) -> TargetPageOptions:
    """Normalize raw page options into a validated options object.

    Args:
        options: Mapping, ``TargetPageOptions``, or ``None`` to normalize.

    Returns:
        A validated ``TargetPageOptions`` instance.
    """
    if options is None:
        return TargetPageOptions()
    if isinstance(options, TargetPageOptions):
        _validate_page_options(options)
        return options
    if not isinstance(options, Mapping):
        raise TypeError("target_options must be a mapping or TargetPageOptions.")

    normalized = TargetPageOptions(
        image_strategy=_read_optional_string(options, "image_strategy"),
        raw_image_strategy=_read_optional_string(options, "raw_image_strategy"),
        copy_script_mode=_read_optional_string(options, "copy_script_mode"),
        article_width_px=_read_optional_int(options, "article_width_px"),
        table_mode=_read_optional_string(options, "table_mode"),
        toolbar_message=_read_optional_string(options, "toolbar_message"),
        theme_overrides=_read_theme_overrides(options.get("theme_overrides")),
    )
    _validate_page_options(normalized)
    return normalized


def merge_page_options(
    base: TargetPageOptions,
    override: TargetPageOptions,
) -> TargetPageOptions:
    """Merge two option objects, with overrides taking precedence.

    Args:
        base: Base option values to start from.
        override: Override values that should win when provided.

    Returns:
        A merged ``TargetPageOptions`` instance.
    """
    return TargetPageOptions(
        image_strategy=override.image_strategy or base.image_strategy,
        raw_image_strategy=override.raw_image_strategy or base.raw_image_strategy,
        copy_script_mode=override.copy_script_mode or base.copy_script_mode,
        article_width_px=(
            override.article_width_px
            if override.article_width_px is not None
            else base.article_width_px
        ),
        table_mode=override.table_mode or base.table_mode,
        toolbar_message=override.toolbar_message or base.toolbar_message,
        theme_overrides={**base.theme_overrides, **override.theme_overrides},
    )


def _validate_page_options(options: TargetPageOptions) -> None:
    """Validate target page option values before builder construction.

    Args:
        options: Page option overrides to validate.

    Returns:
        ``None``. Raises when an option value is unsupported.
    """
    if options.image_strategy is not None and options.image_strategy not in IMAGE_STRATEGIES:
        raise ValueError(
            f"Invalid image_strategy={options.image_strategy!r}. "
            f"Expected one of: {sorted(IMAGE_STRATEGIES)}"
        )
    if (
        options.raw_image_strategy is not None
        and options.raw_image_strategy not in IMAGE_STRATEGIES
    ):
        raise ValueError(
            f"Invalid raw_image_strategy={options.raw_image_strategy!r}. "
            f"Expected one of: {sorted(IMAGE_STRATEGIES)}"
        )
    if options.copy_script_mode is not None and options.copy_script_mode not in COPY_SCRIPT_MODES:
        raise ValueError(
            f"Invalid copy_script_mode={options.copy_script_mode!r}. "
            f"Expected one of: {sorted(COPY_SCRIPT_MODES)}"
        )
    if options.article_width_px is not None and options.article_width_px <= 0:
        raise ValueError("article_width_px must be a positive integer when provided.")
    if options.table_mode is not None and options.table_mode not in {"native", "image"}:
        raise ValueError("table_mode must be either 'native' or 'image' when provided.")


def _read_optional_string(options: Mapping[str, object], key: str) -> str | None:
    """Read an optional string-like option from a mapping.

    Args:
        options: Raw option mapping supplied by the caller.
        key: Option key to read.

    Returns:
        A normalized string value, or ``None`` when the key is absent.
    """
    value = options.get(key)
    if value is None:
        return None
    return str(value).strip().lower() if key.endswith("_mode") or key.endswith("_strategy") else str(value)


def _read_optional_int(options: Mapping[str, object], key: str) -> int | None:
    """Read an optional integer option from a mapping.

    Args:
        options: Raw option mapping supplied by the caller.
        key: Option key to read.

    Returns:
        The coerced integer value, or ``None`` when the key is absent.
    """
    value = options.get(key)
    if value is None:
        return None
    return int(value)


def _read_theme_overrides(value: object) -> dict[str, str]:
    """Normalize theme override values into a string-only mapping.

    Args:
        value: Raw theme override object from user input.

    Returns:
        A mapping of CSS variable names to string values.
    """
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("target_options.theme_overrides must be a mapping/object.")
    out: dict[str, str] = {}
    for k, v in value.items():
        out[str(k)] = str(v)
    return out


def _script_from_mode(mode: str) -> str:
    """Resolve the copy-button script payload for a given mode.

    Args:
        mode: Requested copy-script mode name.

    Returns:
        The JavaScript snippet for the mode, or an empty string.
    """
    if mode == "copyable":
        return COPYABLE_SCRIPT
    if mode == "simple":
        return SIMPLE_COPY_SCRIPT
    return ""


def _resolve_script_mode(requested_mode: str, image_strategy: str) -> str:
    """Resolve the effective copy-script mode for a target page.

    Args:
        requested_mode: Copy-script mode requested by config or runtime.
        image_strategy: Final image strategy used for page generation.

    Returns:
        The effective script mode compatible with the image strategy.
    """
    if image_strategy == "copyable":
        return "copyable"
    return requested_mode


class ProfiledBuilder(PlatformBuilder):
    """Build pages from one static target profile and optional overrides."""

    def __init__(
        self,
        profile: TargetProfile,
        *,
        options: TargetPageOptions | None = None,
    ) -> None:
        """Initialize a profile-backed page builder.

        Args:
            profile: Target profile supplying defaults and theme values.
            options: Optional page-level overrides for the target profile.

        Returns:
            ``None``. The builder stores the profile and resolved options.
        """
        self.profile = profile
        self.options = options or TargetPageOptions()

    @property
    def name(self) -> str:
        """Return the builder's target profile name.

        Args:
            None.

        Returns:
            The canonical name of the active target profile.
        """
        return self.profile.name

    def build_page(self, content_html: str, *, raw_mode: bool = False) -> str:
        """Wrap converted content using the active profile and overrides.

        Args:
            content_html: Converted notebook body HTML to wrap.
            raw_mode: Whether to use raw-output image settings and chrome.

        Returns:
            A complete HTML page for the selected publishing target.
        """
        strategy = (
            self.options.raw_image_strategy or self.profile.raw_image_strategy
            if raw_mode
            else self.options.image_strategy or self.profile.image_strategy
        )

        if strategy == "embed":
            content_html = self._embed_images_as_data_uris(content_html)
        elif strategy == "copyable":
            content_html = self._make_images_copyable(content_html)
        elif strategy == "preserve":
            pass
        else:
            raise ValueError(
                f"Invalid image strategy {strategy!r}. "
                f"Expected one of: {sorted(IMAGE_STRATEGIES)}"
            )

        theme_overrides = dict(self.profile.theme_overrides)
        theme_overrides.update(self.options.theme_overrides)
        if self.options.article_width_px is not None:
            theme_overrides["body-max-width"] = f"{self.options.article_width_px}px"

        requested_script_mode = (
            self.options.copy_script_mode or self.profile.copy_script_mode
        )
        script_mode = _resolve_script_mode(requested_script_mode, strategy)
        script = _script_from_mode(script_mode)
        include_copy_button = requested_script_mode != "none"

        return build_page(
            content_html,
            title=self.profile.title,
            toolbar_message=self.options.toolbar_message or self.profile.toolbar_message,
            script=script,
            raw_mode=raw_mode,
            theme_overrides=theme_overrides,
            extra_css=self.profile.extra_css,
            include_copy_button=include_copy_button,
        )
