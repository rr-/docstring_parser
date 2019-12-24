from pathlib import Path

from setuptools import find_packages, setup

setup(
    author="Marcin Kurczewski",
    author_email="rr-@sakuya.pl",
    name="docstring_parser",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    version="0.5",
    url="https://github.com/rr-/docstring_parser",
    packages=find_packages(),
    package_dir={"docstring_parser": "docstring_parser"},
    package_data={"docstring_parser": ["../LICENSE.md"]},
    classifiers=[
        "Environment :: Other Environment",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Topic :: Documentation :: Sphinx",
        "Topic :: Text Processing :: Markup",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
