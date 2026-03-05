.PHONY: run install install-system clean test build aur-build

# ── Development ──────────────────────────────

run:
	cd casper-keyboard-rgb && cargo run

test:
	cd casper-keyboard-rgb && cargo test

build:
	cd casper-keyboard-rgb && cargo build --release

# ── Installation ─────────────────────────────

install: build
	install -Dm755 casper-keyboard-rgb/target/release/casper-keyboard-rgb /usr/local/bin/casper-keyboard-rgb

install-system: build
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
	cd casper-keyboard-rgb && cargo clean
	rm -rf casper-keyboard-rgb-1.0.*.tar.gz

# ── AUR build ────────────────────────────────

aur-build:
	makepkg -si
