"""Tests for docstring parser."""

# Private pydoctor customization code in order to make to exclude this package from the API documentation.
# Based on Twisted code.

try:
    from pydoctor.model import System, PrivacyClass, Documentable
except ImportError:
    pass
else:
    class _HidesTestsPydoctorSystem(System):
        """
        A PyDoctor "system" used to generate the docs.
        """
        def privacyClass(self, documentable:Documentable) -> PrivacyClass:
            """
            Report the privacy level for an object.
            Hide the module 'docstring_parser.tests'.
            """
            if documentable.fullName().startswith("docstring_parser.tests"):
                return PrivacyClass.HIDDEN
            return super().privacyClass(documentable)