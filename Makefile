.PHONY: install install-web web-build web-demo web test check run

install:
	python -m pip install -e ".[dev]"

install-web:
	python -m pip install -e ".[web,dev]"

web-build:
	python web/build.py

web-demo: web-build
	codeagent-web --workspace . --demo

web: web-build
	codeagent-web --workspace .

test:
	pytest -q

check: web-build
	python -m compileall -q src
	node --check web/dist/app.js
	pytest -q

run:
	codeagent --workspace .
