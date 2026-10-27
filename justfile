default:
    @just --list

# Create .venv with the dev dependencies and install the git hooks
setup:
    uv sync
    uv run prek install

# Run the tests
test *args:
    uv run pytest {{args}}

# Run every prek hook on the whole tree, fixing what ruff can
lint:
    uv run prek run --all-files

# Build the sdist and the wheel into dist/
build:
    uv build

# Generate the API documentation into apidocs/
docs:
    uv run --only-group docs pydoctor \
        --project-name=docstring_parser \
        --make-html \
        --html-output=./apidocs \
        --project-base-dir="." \
        --docformat=restructuredtext \
        --privacy="HIDDEN:docstring_parser.tests" \
        --intersphinx=https://docs.python.org/3/objects.inv \
        ./docstring_parser
