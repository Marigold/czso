#
#  default.mk
#

SRC = czso tests

default: help

help-default:
	@echo 'Available commands:'
	@echo
	@echo '  make test      Run all linting and unit tests'
	@echo '  make check     Format & Lint & Typecheck'
	@echo

# check formatting before lint, since an autoformat might fix linting issues
test-default: check-formatting check-linting check-typing unittest

.sanity-check:
	@echo '==> Checking your Python setup'

	@if python -c "import sys; exit(0 if sys.platform.startswith('win32') else 1)"; then \
		echo 'ERROR: you are using a non-WSL Python interpreter, please consult the'; \
		echo '       docs on how to switch to WSL Python on Windows'; \
		exit 1; \
	fi
	touch .sanity-check

check-uv-default:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo 'ERROR: uv is not installed.'; \
		echo 'Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh'; \
		echo 'Or see: https://docs.astral.sh/uv/getting-started/installation/'; \
		exit 1; \
	fi

.venv-default: check-uv .sanity-check
	@echo '==> Installing packages'
	@if [ -n "$(PYTHON_VERSION)" ]; then \
		echo '==> Using Python version $(PYTHON_VERSION)'; \
		UV_PYTHON=$(PYTHON_VERSION) uv sync --all-extras --group dev; \
	else \
		uv sync --all-extras --group dev; \
	fi

check-default:
	@make lint
	@make format
	@make check-typing

lint-default: .venv
	@echo '==> Linting & Sorting imports'
	@.venv/bin/ruff check --fix $(SRC)

check-linting-default: .venv
	@echo '==> Checking linting'
	@.venv/bin/ruff check $(SRC)

check-formatting-default: .venv
	@echo '==> Checking formatting'
	@.venv/bin/ruff format --check $(SRC)

check-typing-default: .venv
	@echo '==> Checking types'
	.venv/bin/ty check $(SRC)

unittest-default: .venv
	@echo '==> Running unit tests'
	.venv/bin/pytest $(SRC)

format-default: .venv
	@echo '==> Reformatting files'
	@.venv/bin/ruff format $(SRC)

# allow you to override a command, e.g. "watch", but if you do not, then use
# the default
%: %-default
	@true
