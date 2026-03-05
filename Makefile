.PHONY: run install install-system clean test lint

# ── Development ──────────────────────────────

run:
	python -m src.main

test:
	python -m pytest tests/ -v

lint:
	python -m flake8 src/ tests/
	python -m mypy src/

# ── Installation ─────────────────────────────

install:
	pip install -e .

install-system:
	@echo "Installing system files (requires root)..."
	install -Dm755 data/led-write-helper /usr/lib/casper-keyboard-rgb/led-write-helper
	install -Dm644 data/org.casper.keyboard.rgb.policy /usr/share/polkit-1/actions/org.casper.keyboard.rgb.policy
	install -Dm644 data/casper-keyboard-rgb.desktop /usr/share/applications/casper-keyboard-rgb.desktop
	install -Dm644 data/99-casper-kbd-backlight.rules /usr/lib/udev/rules.d/99-casper-kbd-backlight.rules
	install -Dm644 systemd/casper-keyboard-rgb-restore.service /usr/lib/systemd/system/casper-keyboard-rgb-restore.service
	udevadm control --reload-rules && udevadm trigger
	@echo "Done. Udev rules reloaded."

# ── Cleanup ──────────────────────────────────

clean:
	rm -rf build/ dist/ *.egg-info .mypy_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

# ── AUR build ────────────────────────────────

aur-build:
	makepkg -si
