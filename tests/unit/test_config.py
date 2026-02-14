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
    load_config,
    apply_platform_defaults,
)


class TestConfigDefaults:
    """Test default configuration values."""

    def test_config_defaults(self):
        """Default Config has expected values."""
        config = Config()
        assert config.image_width == 1920
        assert config.border_radius == 14
        assert isinstance(config.code, CodeConfig)
        assert isinstance(config.latex, LatexConfig)

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
        assert code.separator == 2
        assert code.background == ""
        assert code.border_radius == 14

    def test_latex_config_defaults(self):
        """Default LatexConfig has expected values."""
        latex = LatexConfig()
        assert latex.font_size == 48
        assert latex.dpi == 150
        assert latex.color == "black"
        assert latex.background == "white"
        assert latex.padding == 68
        assert latex.image_width == 1920
        assert latex.try_usetex is True
        assert latex.preamble == ""
        assert latex.border_radius == 0


class TestConfigLoading:
    """Test loading configuration from YAML files."""

    def test_load_config_missing_file(self):
        """Missing config file returns defaults."""
        config = load_config(Path("/nonexistent/config.yaml"))
        assert config.image_width == 1920  # Default value
        assert config.border_radius == 14

    def test_load_config_none_path(self):
        """None path returns defaults."""
        config = load_config(None)
        assert config.image_width == 1920
        assert isinstance(config.code, CodeConfig)
        assert isinstance(config.latex, LatexConfig)

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
  color: "white"
""")
        config = load_config(config_path)
        assert config.image_width == 1000
        assert config.border_radius == 20
        assert config.code.font_size == 36
        assert config.code.theme == "default"
        assert config.latex.dpi == 200
        assert config.latex.color == "white"

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

    def test_border_radius_inheritance(self, tmp_path):
        """Top-level border_radius inherited by code and latex configs."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("border_radius: 15\n")
        config = load_config(config_path)
        assert config.border_radius == 15
        assert config.code.border_radius == 15
        assert config.latex.border_radius == 15

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
  color: "red"
  background: "black"
""")
        config = load_config(config_path)
        # Overridden
        assert config.latex.color == "red"
        assert config.latex.background == "black"
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
        # Inherited
        assert config.code.image_width == 1500
        assert config.latex.image_width == 1500


class TestPlatformDefaults:
    """Test platform-specific default adjustments."""

    def test_substack_platform_unchanged(self):
        """Substack platform returns config unchanged."""
        config = Config()
        result = apply_platform_defaults(config, "substack")
        assert result.image_width == config.image_width
        assert result.code.font_size == config.code.font_size
        assert result.latex.font_size == config.latex.font_size

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
        assert result.code.separator == 2
        # LaTeX config should be adjusted
        assert result.latex.font_size == 35
        assert result.latex.image_width == 1200
        assert result.latex.padding == 50

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
  background: "black"
  border_radius: 30
latex:
  font_size: 42
  dpi: 180
  color: "white"
  background: "black"
  padding: 60
  image_width: 1600
  try_usetex: false
  preamble: "\\\\usepackage{amsmath}"
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
        assert config.code.background == "black"
        assert config.code.border_radius == 30
        # LaTeX config
        assert config.latex.font_size == 42
        assert config.latex.dpi == 180
        assert config.latex.color == "white"
        assert config.latex.background == "black"
        assert config.latex.padding == 60
        assert config.latex.image_width == 1600
        assert config.latex.try_usetex is False
        assert config.latex.preamble == "\\usepackage{amsmath}"
        assert config.latex.border_radius == 30

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
        # Custom settings preserved
        assert result.border_radius == 20
        assert result.code.theme == "github"
