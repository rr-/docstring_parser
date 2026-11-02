"""Pytest configuration."""

import sys

# These only test legacy=False, which requires Python 3.10.
collect_ignore = (
    ["test_new_behavior.py", "test_properties.py"]
    if sys.version_info < (3, 10)
    else []
)


def pytest_addoption(parser):
    """Add the option used to regenerate golden files."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite the expected corpus results instead of comparing.",
    )
