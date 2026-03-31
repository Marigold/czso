#
#  Makefile
#

.PHONY: help test check lint format unittest clean clobber

include default.mk

SRC = czso tests

help:
	@echo 'Available commands:'
	@echo
	@echo '  make .venv        Install Python packages via uv'
	@echo '  make check        Format, lint & typecheck'
	@echo '  make format       Format code with ruff'
	@echo '  make lint         Lint & fix code with ruff'
	@echo '  make test         Run all linting, typing, and unit tests'
	@echo '  make unittest     Run unit tests only'
	@echo '  make check-typing Typecheck with ty'
	@echo
	@echo '  make clean        Remove build artifacts'
	@echo '  make clobber      Remove artifacts + .venv'
	@echo

clean:
	@echo '==> Cleaning build artifacts'
	rm -rf build dist *.egg-info

clobber: clean
	rm -rf .venv
	find . -name .pytest_cache | xargs rm -rf
	find . -name __pycache__ | xargs rm -rf
