"""
Unit tests for inline LaTeX → Unicode/HTML conversion.

Tests the renderers/inline_latex.py module which converts inline math ($...$)
to Unicode and HTML for clean rendering in web contexts.
"""
import pytest
from nb2wb.renderers.inline_latex import (
    convert_inline_math,
    _expand_frac,
    _expand_scripts,
    _italicize,
    _to_unicode,
)


class TestInlineMathConversion:
    """Test the top-level convert_inline_math() function."""

    def test_simple_greek_letters(self):
        """Greek letters converted to Unicode."""
        text = r"$\alpha + \beta = \gamma$"
        result = convert_inline_math(text)
        assert "α" in result
        assert "β" in result
        assert "γ" in result
        assert "$" not in result

    def test_superscript_numbers(self):
        """Numeric superscripts converted to Unicode or HTML."""
        text = "$x^2 + x^3$"
        result = convert_inline_math(text)
        # Should have Unicode superscripts (and variables may be italicized)
        assert "²" in result
        assert "³" in result

    def test_subscript_numbers(self):
        """Numeric subscripts converted to Unicode or HTML."""
        text = "$x_1 + x_2$"
        result = convert_inline_math(text)
        # Should have Unicode subscripts (and variables may be italicized)
        assert "₁" in result
        assert "₂" in result

    def test_preserve_non_math_dollars(self):
        """Dollar signs in non-math context preserved."""
        text = "Price: $100 USD"
        result = convert_inline_math(text)
        # Single dollar signs without matching pair should be preserved
        assert "$100" in result

    def test_ignore_display_math_delimiters(self):
        """$$ delimiters not treated as inline math."""
        text = "$$E = mc^2$$"
        result = convert_inline_math(text)
        assert result == text  # Display math untouched

    def test_multiple_inline_math(self):
        """Multiple inline math expressions in same text."""
        text = "Let $x = 1$ and $y = 2$, then $x + y = 3$."
        result = convert_inline_math(text)
        assert "$" not in result
        assert "Let" in result
        assert "and" in result
        assert "then" in result

    def test_empty_inline_math(self):
        """Empty inline math handled gracefully."""
        text = "Empty math: $$"
        result = convert_inline_math(text)
        # Should not crash

    def test_einstein_equation(self):
        """E = mc^2 converts correctly."""
        text = "$E = mc^2$"
        result = convert_inline_math(text)
        assert "$" not in result
        assert "E" in result
        assert "c" in result or "<em>c</em>" in result
        # Either Unicode superscript or HTML tag
        assert ("²" in result or "<sup>2</sup>" in result)


class TestFracExpansion:
    """Test \\frac{}{} expansion to (num)/(den) format."""

    def test_simple_frac(self):
        """Simple fraction expanded."""
        latex = r"\frac{a}{b}"
        result = _expand_frac(latex)
        assert result == "(a)/(b)"

    def test_nested_frac(self):
        """Nested fractions expanded correctly."""
        latex = r"\frac{\frac{a}{b}}{c}"
        result = _expand_frac(latex)
        # Only top-level \frac expanded, inner one remains
        assert result == r"(\frac{a}{b})/(c)"

    def test_frac_with_spaces(self):
        """Spaces around braces handled."""
        latex = r"\frac {a} {b}"
        result = _expand_frac(latex)
        assert result == "(a)/(b)"

    def test_multiple_fracs(self):
        """Multiple fractions in same expression."""
        latex = r"\frac{a}{b} + \frac{c}{d}"
        result = _expand_frac(latex)
        assert result == "(a)/(b) + (c)/(d)"

    def test_frac_with_complex_numerator(self):
        """Fraction with complex numerator."""
        latex = r"\frac{a + b}{c}"
        result = _expand_frac(latex)
        assert result == "(a + b)/(c)"

    def test_frac_with_complex_denominator(self):
        """Fraction with complex denominator."""
        latex = r"\frac{a}{b + c}"
        result = _expand_frac(latex)
        assert result == "(a)/(b + c)"

    def test_no_frac_unchanged(self):
        """Text without \\frac unchanged."""
        latex = "a + b"
        result = _expand_frac(latex)
        assert result == latex


class TestScriptExpansion:
    """Test superscript/subscript expansion to Unicode or HTML."""

    def test_superscript_braced(self):
        """Braced superscript converted."""
        text = "x^{2}"
        result = _expand_scripts(text)
        # Should be either Unicode or HTML tag
        assert ("x²" in result or 'x<sup>2</sup>' in result)

    def test_subscript_braced(self):
        """Braced subscript converted."""
        text = "x_{1}"
        result = _expand_scripts(text)
        assert ("x₁" in result or 'x<sub>1</sub>' in result)

    def test_superscript_bare(self):
        """Bare (unbraced) superscript converted."""
        text = "x^2"
        result = _expand_scripts(text)
        assert "x²" in result

    def test_subscript_bare(self):
        """Bare (unbraced) subscript converted."""
        text = "x_1"
        result = _expand_scripts(text)
        assert "x₁" in result

    def test_complex_superscript_fallback(self):
        """Complex superscripts converted to Unicode or HTML."""
        text = "x^{complex}"
        result = _expand_scripts(text)
        # May convert to Unicode superscripts or use HTML tag
        assert ("ᶜ" in result or "<sup>" in result)

    def test_complex_subscript_fallback(self):
        """Complex subscripts fall back to HTML."""
        text = "x_{complex}"
        result = _expand_scripts(text)
        assert "<sub>complex</sub>" in result

    def test_multiple_scripts(self):
        """Multiple super/subscripts in same text."""
        text = "x^2 + y_1"
        result = _expand_scripts(text)
        assert "²" in result
        assert "₁" in result

    def test_superscript_letters(self):
        """Letter superscripts converted."""
        text = "x^a"
        result = _expand_scripts(text)
        assert "xᵃ" in result

    def test_subscript_letters(self):
        """Letter subscripts converted."""
        text = "x_a"
        result = _expand_scripts(text)
        assert "xₐ" in result


class TestItalicization:
    """Test variable italicization with <em> tags."""

    def test_single_latin_letter(self):
        """Single Latin letters wrapped in <em>."""
        text = "x"
        result = _italicize(text)
        assert result == "<em>x</em>"

    def test_multi_letter_word_not_italicized(self):
        """Multi-letter words not italicized."""
        text = "sin"
        result = _italicize(text)
        # Function names should not be italicized
        assert "<em>sin</em>" not in result

    def test_greek_letters_italicized(self):
        """Greek letters wrapped in <em>."""
        text = "α"
        result = _italicize(text)
        assert result == "<em>α</em>"

    def test_preserve_existing_html_tags(self):
        """Existing HTML tags not double-wrapped."""
        text = "<sup>2</sup>"
        result = _italicize(text)
        # Should not add <em> inside <sup>
        assert result == "<sup>2</sup>"

    def test_text_with_multiple_variables(self):
        """Multiple single-letter variables italicized."""
        text = "x + y = z"
        result = _italicize(text)
        assert "<em>x</em>" in result
        assert "<em>y</em>" in result
        assert "<em>z</em>" in result

    def test_preserve_html_tags_in_complex_text(self):
        """HTML tags preserved in complex text."""
        text = "x<sub>1</sub> + y"
        result = _italicize(text)
        assert "<em>x</em><sub>1</sub>" in result or "x<sub>1</sub>" in result
        assert "<em>y</em>" in result


class TestFullPipeline:
    """Test complete conversion pipeline with _to_unicode()."""

    def test_golden_ratio(self):
        """Golden ratio with fraction."""
        latex = r"\phi = \frac{1+\sqrt{5}}{2}"
        result = _to_unicode(latex)
        # Should have phi (Unicode)
        assert "φ" in result or "ϕ" in result
        # Should have expanded fraction
        assert "(" in result and ")" in result

    def test_quadratic_formula(self):
        """Quadratic formula with complex fraction."""
        latex = r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
        result = _to_unicode(latex)
        # Should have expanded fraction
        assert "(" in result and ")" in result
        # Should have pm symbol or ±
        assert "±" in result or "pm" in result

    def test_sum_notation(self):
        """Summation notation with subscript/superscript."""
        latex = r"\sum_{i=1}^{n} x_i"
        result = _to_unicode(latex)
        # Should have sum symbol
        assert "∑" in result

    def test_integral(self):
        """Integral notation."""
        latex = r"\int_0^{\infty} f(x) dx"
        result = _to_unicode(latex)
        # Should have integral symbol
        assert "∫" in result

    def test_mixed_greek_and_operators(self):
        """Mixed Greek letters and operators."""
        latex = r"\alpha + \beta \cdot \gamma"
        result = _to_unicode(latex)
        assert "α" in result
        assert "β" in result
        assert "γ" in result
        # cdot should be converted to dot operator
        assert "⋅" in result or "·" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string(self):
        """Empty string handled gracefully."""
        text = ""
        result = convert_inline_math(text)
        assert result == ""

    def test_no_math_content(self):
        """Text with no math content unchanged."""
        text = "This is plain text."
        result = convert_inline_math(text)
        assert result == text

    def test_mismatched_dollar_signs(self):
        """Mismatched dollar signs handled."""
        text = "This has one $ dollar sign"
        result = convert_inline_math(text)
        # Single unmatched $ should remain
        assert "$" in result

    def test_nested_dollar_signs(self):
        """Nested dollar signs (invalid LaTeX) handled."""
        text = "$x = $y$$"
        result = convert_inline_math(text)
        # Should not crash

    def test_unicode_input(self):
        """Unicode in input preserved."""
        text = "$α = β$"
        result = convert_inline_math(text)
        assert "α" in result
        assert "β" in result
        assert "$" not in result

    def test_html_entities_in_math(self):
        """HTML entities in math context."""
        text = "$x &lt; y$"
        result = convert_inline_math(text)
        # Should not crash

    def test_very_long_expression(self):
        """Very long math expression handled."""
        text = "$" + " + ".join([f"x_{i}" for i in range(100)]) + "$"
        result = convert_inline_math(text)
        assert "$" not in result
