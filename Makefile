.PHONY: install setup run test clean help

help:
	@echo "E-Ink Dashboard Generator"
	@echo ""
	@echo "Usage:"
	@echo "  make install     Install Python dependencies"
	@echo "  make setup       Install dependencies + Playwright browsers"
	@echo "  make run         Run CLI with example prompt"
	@echo "  make server      Start HTTP API server"
	@echo "  make test        Test with simulation mode"
	@echo "  make clean       Remove generated files"

install:
	uv sync

setup: install
	uv run playwright install chromium

run:
	uv run python generate.py --prompt "Show current time, weather summary, and a motivational quote" --save-html output/test.html

server:
	uv run python server.py

test:
	@echo "Testing dashboard generation..."
	uv run python generate.py --prompt "Display: temperature 22°C, humidity 65%, wind 3 m/s" --save-html output/test.html
	@echo "HTML saved to output/test.html"

clean:
	rm -rf output/*.png output/*.html
