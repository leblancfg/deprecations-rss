"""Test that the package version is set correctly."""


def describe_package_version():
    """Tests for package version."""

    def it_has_version_defined() -> None:
        """It should have a version defined."""
        from src import __version__

        assert __version__ == "0.1.0"

    def it_exports_version_string() -> None:
        """It should export version as a string."""
        from src import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0
