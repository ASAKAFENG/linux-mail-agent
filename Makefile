.PHONY: install dev test build

install:
	python3 -m pip install .

dev:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest -q

build:
	python3 -m pip wheel . -w dist/
