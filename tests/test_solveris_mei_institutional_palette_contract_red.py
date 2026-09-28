from pathlib import Path
import re

CSS = Path("frontend-dashboard/src/App.css").read_text(encoding="utf-8")


def rule(selector):
    pattern = r"(?m)^" + re.escape(selector) + r"\s*\{([^{}]*)\}"
    matches = re.findall(pattern, CSS)
    assert len(matches) == 1, selector
    return matches[0]


def test_primary_actions_share_solveris_blue():
    for selector in (
        ".solveris-public-entry .solveris-login-submit",
        ".solveris-public-entry .solveris-register-submit",
        ".solveris-public-entry .solveris-primary-action",
    ):
        declarations = rule(selector)
        assert "background: #a6c9ff;" in declarations
        assert "color: #06101c;" in declarations


def test_secondary_elements_follow_blue_silver_hierarchy():
    assert "color: #f4f7fb;" in rule(".solveris-public-entry .solveris-entry-card h2")
    assert "color: #c9d5e2;" in rule(".solveris-public-entry .solveris-secondary-action")

    for selector in (
        ".solveris-public-entry .solveris-account-link",
        ".solveris-public-entry .solveris-register-login-link",
        ".solveris-public-entry .solveris-password-toggle",
        ".solveris-public-entry .solveris-register-password-toggle",
    ):
        assert "color: #a6c9ff;" in rule(selector)


def test_primary_actions_have_visible_keyboard_focus():
    assert ".solveris-public-entry .solveris-login-submit:focus-visible" in CSS
    assert ".solveris-public-entry .solveris-register-submit:focus-visible" in CSS
