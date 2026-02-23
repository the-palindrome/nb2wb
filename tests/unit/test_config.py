"""
Unit tests for configuration loading and merging.

Tests the config.py module which handles YAML loading, defaults,
inheritance, and platform-specific adjustments.
"""
import pytest
from pathlib import Path
from nb2wb.config import (
    Config,
    CodeConfig,
    LatexConfig,
    TableConfig,
    SafetyConfig,
    load_config,
    load_config_from_dict,
    apply_platform_defaults,
)


class TestConfigDefaults:
    """Test default configuration values."""

    def test_config_defaults(self):
        """Default Config has expected values."""
        config = Config()
        assert config.image_width == 1920
        assert config.border_radius == 0
        assert isinstance(config.code, CodeConfig)
        assert isinstance(config.latex, LatexConfig)
        assert isinstance(config.table, TableConfig)
        assert isinstance(config.safety, SafetyConfig)
        assert config.safety.max_display_math_blocks == 500
        assert config.safety.max_total_latex_chars == 1_000_000

    def test_code_config_defaults(self):
        """Default CodeConfig has expected values."""
        code = CodeConfig()
        assert code.font_size == 48
        assert code.theme == "monokai"
        assert code.line_numbers is True
        assert code.font == "DejaVu Sans Mono"
        assert code.image_width == 1920
        assert code.padding_x == 100
        assert code.padding_y == 100
        assert code.separator == 0
        assert code.background == ""
        assert code.border_radius == 0

    def test_latex_config_defaults(self):
        """Default LatexConfig has expected values."""
        latex = LatexConfig()
        assert latex.font_size == 48
        assert latex.dpi == 150
        assert latex.color == "#000000"
        assert latex.background == "#ffffff"
        assert latex.padding == 68
        assert latex.image_width == 1920
        assert latex.try_usetex is True
        assert latex.preamble == ""
        assert latex.border_radius == 0

    def test_table_config_defaults(self):
        """Default TableConfig has expected values."""
        table = TableConfig()
        assert table.mode == "native"
        assert table.font_size == 34
        assert table.font == "DejaVu Sans"
        assert table.color == "#1f2937"
        assert table.header_color == "#0f172a"
        assert table.background == "#ffffff"
        assert table.header_background == "#eef2ff"
        assert table.stripe_background == "#f8fafc"
        assert table.border_color == "#dbe4ee"
        assert table.border_width == 1
        assert table.cell_padding_x == 24
        assert table.cell_padding_y == 14
        assert table.outer_padding == 20
        assert table.canvas_background == "#ffffff"
        assert table.zebra_striping is True
        assert table.shadow is True
        assert table.shadow_color == "#0f172a"
        assert table.shadow_alpha == 24
        assert table.shadow_offset_x == 0
        assert table.shadow_offset_y == 8
        assert table.shadow_blur == 18
        assert table.image_width == 1920
        assert table.border_radius == 0


class TestConfigLoading:
    """Test loading configuration from YAML files."""

    def test_load_config_missing_file(self):
        """Missing config file returns defaults."""
        config = load_config(Path("/nonexistent/config.yaml"))
        assert config.image_width == 1920  # Default value
        assert config.border_radius == 0

    def test_load_config_none_path(self):
        """None path returns defaults."""
        config = load_config(None)
        assert config.image_width == 1920
        assert config.border_radius == 0
        assert isinstance(config.code, CodeConfig)
        assert isinstance(config.latex, LatexConfig)
        assert isinstance(config.table, TableConfig)

    def test_load_config_from_temp_file(self, tmp_path):
        """Load config from temporary YAML file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
image_width: 1000
border_radius: 20
code:
  font_size: 36
  theme: "default"
latex:
  dpi: 200
  color: "#ffffff"
table:
  mode: "image"
  font_size: 24
safety:
  max_cells: 123
  max_display_math_blocks: 77
""")
        config = load_config(config_path)
        assert config.image_width == 1000
        assert config.border_radius == 20
        assert config.code.font_size == 36
        assert config.code.theme == "default"
        assert config.latex.dpi == 200
        assert config.latex.color == "#ffffff"
        assert config.table.mode == "image"
        assert config.table.font_size == 24
        assert config.safety.max_cells == 123
        assert config.safety.max_display_math_blocks == 77

    def test_load_config_empty_file(self, tmp_path):
        """Empty config file returns defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")
        config = load_config(config_path)
        assert config.image_width == 1920
        assert config.border_radius == 0

    def test_load_config_invalid_yaml(self, tmp_path):
        """Invalid YAML file raises error."""
        import yaml
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content:")
        # Invalid YAML should raise an error
        with pytest.raises(yaml.scanner.ScannerError):
            load_config(config_path)

    def test_load_config_from_dict(self):
        """In-memory dict config is supported for script/API usage."""
        config = load_config_from_dict(
            {
                "image_width": 1200,
                "code": {"font_size": 30},
                "latex": {"dpi": 200},
                "safety": {"max_cells": 123},
            }
        )
        assert config.image_width == 1200
        assert config.code.font_size == 30
        assert config.latex.dpi == 200
        assert config.safety.max_cells == 123

    def test_load_config_from_dict_rejects_non_mapping(self):
        """Non-dict config input raises a TypeError."""
        with pytest.raises(TypeError):
            load_config_from_dict(["not", "a", "mapping"])

    def test_invalid_table_mode_falls_back_to_native(self):
        """Unknown table mode falls back to native rendering."""
        config = load_config_from_dict({"table": {"mode": "unsupported"}})
        assert config.table.mode == "native"


class TestConfigInheritance:
    """Test configuration inheritance from top-level to sub-configs."""

    def test_image_width_inheritance(self, tmp_path):
        """Top-level image_width inherited by code and latex configs."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("image_width: 2000\n")
        config = load_config(config_path)
        assert config.image_width == 2000
        assert config.code.image_width == 2000
        assert config.latex.image_width == 2000
        assert config.table.image_width == 2000

    def test_border_radius_inheritance(self, tmp_path):
        """Top-level border_radius inherited by code and latex configs."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("border_radius: 15\n")
        config = load_config(config_path)
        assert config.border_radius == 15
        assert config.code.border_radius == 15
        assert config.latex.border_radius == 15
        assert config.table.border_radius == 15

    def test_override_inherited_image_width(self, tmp_path):
        """Sub-config can override inherited image_width."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
image_width: 2000
code:
  image_width: 1500
""")
        config = load_config(config_path)
        assert config.image_width == 2000
        assert config.code.image_width == 1500  # Override
        assert config.latex.image_width == 2000  # Inherited
        assert config.table.image_width == 2000  # Inherited

    def test_override_inherited_border_radius(self, tmp_path):
        """Sub-config can override inherited border_radius."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
border_radius: 15
latex:
  border_radius: 0
""")
        config = load_config(config_path)
        assert config.border_radius == 15
        assert config.code.border_radius == 15  # Inherited
        assert config.latex.border_radius == 0  # Override
        assert config.table.border_radius == 15  # Inherited


class TestPartialConfigOverrides:
    """Test partial configuration overrides in YAML."""

    def test_partial_code_override(self, tmp_path):
        """Partial code config override, rest defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
code:
  font_size: 36
""")
        config = load_config(config_path)
        # Overridden
        assert config.code.font_size == 36
        # Defaults preserved
        assert config.code.theme == "monokai"
        assert config.code.line_numbers is True

    def test_partial_latex_override(self, tmp_path):
        """Partial latex config override, rest defaults."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
latex:
  color: "#ff0000"
  background: "#000000"
""")
        config = load_config(config_path)
        # Overridden
        assert config.latex.color == "#ff0000"
        assert config.latex.background == "#000000"
        # Defaults preserved
        assert config.latex.font_size == 48
        assert config.latex.dpi == 150

    def test_mixed_overrides(self, tmp_path):
        """Mixed overrides across top-level and sub-configs."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
image_width: 1500
code:
  theme: "github"
  line_numbers: false
latex:
  try_usetex: false
""")
        config = load_config(config_path)
        assert config.image_width == 1500
        assert config.code.theme == "github"
        assert config.code.line_numbers is False
        assert config.latex.try_usetex is False
        assert config.table.mode == "native"
        # Inherited
        assert config.code.image_width == 1500
        assert config.latex.image_width == 1500
        assert config.table.image_width == 1500


class TestPlatformDefaults:
    """Test platform-specific default adjustments."""

    def test_substack_platform_enables_table_images(self):
        """Substack defaults enable table image fallback while preserving core sizing."""
        config = Config()
        result = apply_platform_defaults(config, "substack")
        assert result.image_width == config.image_width
        assert result.code.font_size == config.code.font_size
        assert result.latex.font_size == config.latex.font_size
        assert result.table.mode == "image"
        assert result.table.border_radius == 12
        assert result.table.outer_padding == 20

    def test_x_platform_smaller_dimensions(self):
        """X platform has smaller dimensions for mobile."""
        config = Config()
        result = apply_platform_defaults(config, "x")
        # Top-level should be smaller
        assert result.image_width == 680
        # Code config should be adjusted
        assert result.code.font_size == 42
        assert result.code.image_width == 1200
        assert result.code.padding_x == 30
        assert result.code.padding_y == 30
        assert result.code.separator == 0
        # LaTeX config should be adjusted
        assert result.latex.font_size == 35
        assert result.latex.image_width == 1200
        assert result.latex.padding == 50
        # Table config should use image fallback defaults
        assert result.table.mode == "image"
        assert result.table.font_size == 30
        assert result.table.image_width == 1200
        assert result.table.outer_padding == 14
        assert result.table.border_radius == 10
        assert result.table.shadow_alpha == 20

    def test_x_platform_preserves_theme(self):
        """X platform preserves custom theme."""
        config = Config()
        config.code.theme = "github"
        result = apply_platform_defaults(config, "x")
        assert result.code.theme == "github"

    def test_x_platform_preserves_top_border_radius(self):
        """X platform preserves top-level border_radius."""
        config = Config(border_radius=20)
        result = apply_platform_defaults(config, "x")
        # Top-level border_radius is preserved
        assert result.border_radius == 20
        # But sub-configs get new CodeConfig/LatexConfig instances with platform defaults
        # which don't inherit the custom border_radius

    def test_unknown_platform_unchanged(self):
        """Unknown platform returns config unchanged."""
        config = Config()
        result = apply_platform_defaults(config, "unknown_platform")
        assert result.image_width == config.image_width
        assert result.code.font_size == config.code.font_size


class TestComplexConfigScenarios:
    """Test complex configuration scenarios."""

    def test_full_custom_config(self, tmp_path):
        """Full custom configuration loaded correctly."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
image_width: 1800
border_radius: 25
code:
  font_size: 40
  theme: "solarized-dark"
  line_numbers: false
  font: "Monaco"
  image_width: 1600
  padding_x: 80
  padding_y: 80
  separator: 80
  background: "#000000"
  border_radius: 30
latex:
  font_size: 42
  dpi: 180
  color: "#ffffff"
  background: "#000000"
  padding: 60
  image_width: 1600
  try_usetex: false
  preamble: "\\\\usepackage{amsmath}"
  border_radius: 30
table:
  mode: "image"
  font_size: 28
  font: "Arial"
  color: "#1a1a1a"
  header_color: "#000000"
  background: "#ffffff"
  header_background: "#f0f0f0"
  stripe_background: "#f7f9fb"
  border_color: "#cccccc"
  border_width: 2
  cell_padding_x: 12
  cell_padding_y: 8
  outer_padding: 10
  canvas_background: "#ffffff"
  zebra_striping: true
  shadow: true
  shadow_color: "#111827"
  shadow_alpha: 28
  shadow_offset_x: 1
  shadow_offset_y: 9
  shadow_blur: 20
  image_width: 1400
  border_radius: 30
""")
        config = load_config(config_path)
        # Top-level
        assert config.image_width == 1800
        assert config.border_radius == 25
        # Code config
        assert config.code.font_size == 40
        assert config.code.theme == "solarized-dark"
        assert config.code.line_numbers is False
        assert config.code.font == "Monaco"
        assert config.code.image_width == 1600
        assert config.code.padding_x == 80
        assert config.code.padding_y == 80
        assert config.code.separator == 80
        assert config.code.background == "#000000"
        assert config.code.border_radius == 30
        # LaTeX config
        assert config.latex.font_size == 42
        assert config.latex.dpi == 180
        assert config.latex.color == "#ffffff"
        assert config.latex.background == "#000000"
        assert config.latex.padding == 60
        assert config.latex.image_width == 1600
        assert config.latex.try_usetex is False
        assert config.latex.preamble == "\\usepackage{amsmath}"
        assert config.latex.border_radius == 30
        # Table config
        assert config.table.mode == "image"
        assert config.table.font_size == 28
        assert config.table.font == "Arial"
        assert config.table.color == "#1a1a1a"
        assert config.table.header_color == "#000000"
        assert config.table.background == "#ffffff"
        assert config.table.header_background == "#f0f0f0"
        assert config.table.stripe_background == "#f7f9fb"
        assert config.table.border_color == "#cccccc"
        assert config.table.border_width == 2
        assert config.table.cell_padding_x == 12
        assert config.table.cell_padding_y == 8
        assert config.table.outer_padding == 10
        assert config.table.canvas_background == "#ffffff"
        assert config.table.zebra_striping is True
        assert config.table.shadow is True
        assert config.table.shadow_color == "#111827"
        assert config.table.shadow_alpha == 28
        assert config.table.shadow_offset_x == 1
        assert config.table.shadow_offset_y == 9
        assert config.table.shadow_blur == 20
        assert config.table.image_width == 1400
        assert config.table.border_radius == 30

    def test_config_with_extra_fields_ignored(self, tmp_path):
        """Extra unknown fields in YAML ignored gracefully."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
image_width: 1500
unknown_field: "value"
code:
  font_size: 36
  unknown_code_field: "value"
""")
        config = load_config(config_path)
        assert config.image_width == 1500
        assert config.code.font_size == 36
        # Unknown fields ignored, no errors

    def test_x_platform_with_custom_config(self, tmp_path):
        """X platform defaults applied after loading custom config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
border_radius: 20
code:
  theme: "github"
""")
        config = load_config(config_path)
        result = apply_platform_defaults(config, "x")
        # X platform defaults applied
        assert result.image_width == 680
        assert result.code.font_size == 42
        assert result.table.mode == "image"
        # Custom settings preserved
        assert result.border_radius == 20
        assert result.code.theme == "github"
