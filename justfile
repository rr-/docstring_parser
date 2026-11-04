default:
    @just --list

# Create .venv with the dev dependencies and install the git hooks
setup:
    uv sync
    uv run prek install

# Run the tests
test *args:
    uv run pytest {{args}}

# Rewrite the expected output in the text case files from the current code
update-cases:
    UPDATE_CASES=1 uv run pytest -q docstring_parser/tests/test_cases.py::test_case

# Download the corpus docstrings again and fill in their expected output
harvest:
    uv run --no-project --python 3.14 python tools/harvest_corpus.py
    just update-cases

# Compare parse and compose speed against a base commit
bench base="origin/main" *args:
    uv run python tools/bench.py --base {{base}} {{args}}

# Run every prek hook on the whole tree, fixing what ruff can
lint:
    uv run prek run --all-files

# Build the sdist and the wheel into dist/
build:
    uv build

# Generate the API documentation into apidocs/
docs:
    uv run --isolated --python 3.12 --only-group docs pydoctor \
        --project-name=docstring_parser \
        --make-html \
        --html-output=./apidocs \
        --project-base-dir="." \
        --docformat=restructuredtext \
        --privacy="HIDDEN:docstring_parser.tests" \
        --intersphinx=https://docs.python.org/3/objects.inv \
        ./docstring_parser
