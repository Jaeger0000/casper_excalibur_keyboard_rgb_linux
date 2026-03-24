# CHANGELOG


## v1.1.0 (2026-03-24)

### Bug Fixes

- Ensure uniform brightness across all keyboard LED zones
  ([`598cf38`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/598cf38e45166f6b61028524ca1b80281cf3727c))

The casper-wmi driver previously applied brightness changes exclusively to CASPER_KEYBOARD_LED_1
  (zone 0x03), leaving the center (0x04) and right (0x05) zones at their hardware default brightness
  levels when triggered by systemd-backlight at boot or via standard ACPI events. This resulted in
  uneven keyboard illumination.

This patch refactors `last_keyboard_led_change` into a 3-element array to explicitly track the color
  state of each main zone. When a uniform brightness update is requested, the driver now iterates
  over all three zones, combining their respective cached colors with the new brightness level,
  ensuring visually consistent behavior across the entire keyboard.

Co-authored-by: Jaeger0000 <147045444+Jaeger0000@users.noreply.github.com>

- Fix ci.yml
  ([`9976bc6`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/9976bc604672e8ca19fd0a2ba29f8486d270d3e2))

- Fix ci.yml for CI/CD
  ([`9fc3d04`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/9fc3d047d3ec9c36588eac25b4395c91330bbf1e))

- Fix to ci.yml file
  ([`9114382`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/91143826eb277783f694d89ecfe2a7a924983d84))

- Pyptoject.toml
  ([`0fb8bda`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/0fb8bdad966e5c30c1bff7b1af24df8277354331))

- Update pyproject.toml
  ([`2a7e027`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/2a7e02772d31cab1372217c04afa76c5427ee6ba))

- Update readme
  ([`2aa09ba`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/2aa09bab8a02c371329be9e0e9479d337b3e4299))

### Continuous Integration

- Add GitHub Actions workflow for automated testing on master branch
  ([`539a8f5`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/539a8f59addb1f760401db3308a9ea541dc7d97b))

Adds `.github/workflows/ci.yml` to run tests automatically whenever changes are pushed to the
  `master` branch. The tests will run using `xvfb-run make test` against Python 3.12. Configured two
  separate jobs to verify compatibility on both Ubuntu (using `ubuntu-latest`) and Arch Linux (using
  `archlinux:latest` container). Installs necessary system dependencies to support headless PyQt6
  execution in both environments.

Co-authored-by: Jaeger0000 <147045444+Jaeger0000@users.noreply.github.com>

### Documentation

- Update README for open source, add Debian package build script
  ([`1f576f4`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/1f576f40a3e97d0406be3db9e8f245f15ee738f8))

- Rewrite README with badges, multi-distro install instructions, contributing guide, and issue
  reporting section - Add build-deb.sh for Debian/Ubuntu package generation - Add deb target to
  Makefile

### Features

- **ci**: Automate semantic versioning and AUR deployment
  ([`73e2f5b`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/73e2f5b8d60dfa5f752a1568db275edb71c6568c))

- Adds `python-semantic-release` configuration to `pyproject.toml` to automatically manage
  versioning and generate changelogs on the master branch. - Modifies the GitHub Actions pipeline
  (`ci.yml`) to add a `release` job that runs after successful testing on both Ubuntu and Arch
  Linux. - Integrates `upload-to-gh-release` to generate GitHub Releases with attached distribution
  tarballs and wheels. - Adds an automated deployment script `update_pkgbuild.sh` that securely
  updates the version and SHA256 sum of the `PKGBUILD` and correctly handles wait-retry scenarios
  for the source tarball. - Fully orchestrates the update, `makepkg --printsrcinfo`, and push to AUR
  within the action by running an Arch Linux Docker container and managing SSH keys and runner
  ownership properly.

Co-authored-by: Jaeger0000 <147045444+Jaeger0000@users.noreply.github.com>

### Performance Improvements

- Prevent unnecessary dict allocation in profile loading
  ([`137d97f`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/137d97f2d6787094127134f8a2f4a67a8b90a8c6))

Replaces `data.get("profiles", {}).items()` with `(data.get("profiles") or {}).items()` in
  ProfileManager to prevent Python from unnecessarily allocating a new dictionary `{}` every time
  when the `"profiles"` key already exists in the data.

Benchmark results (10,000,000 iterations): - Existing key (default dict allocation): 3.628s -
  Existing key (`or {}` lazy evaluation): 3.134s (~13.6% improvement) - Missing key (default dict
  allocation): 2.769s - Missing key (`or {}` lazy evaluation): 3.006s (Slightly slower, but overall
  net positive since the key usually exists)

Co-authored-by: Jaeger0000 <147045444+Jaeger0000@users.noreply.github.com>


## v1.0.1 (2026-03-05)

### Bug Fixes

- Correct sha256sum for v1.0.0 tarball
  ([`6cf03d3`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/6cf03d3fe4180e498e3fc16f10d4a838b842f1aa))

### Chores

- Remove unnecessary duplicate files from src directory
  ([`0d8dfe2`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/0d8dfe2cc1e361ab4a982b9e17dc9058d29d9318))

Co-authored-by: Jaeger0000 <147045444+Jaeger0000@users.noreply.github.com>


## v1.0.0 (2026-03-05)

### Bug Fixes

- Update PKGBUILD sha256sum for new tarball
  ([`e43e0d2`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/e43e0d23e400da70e65254a12588fac7dde2ed3c))

- Update sha256sum
  ([`9030ae5`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/9030ae5cbb7dc0c053e2787fa6060674b6d8db5d))

### Refactoring

- Rename src/ to casper_keyboard_rgb/ for proper AUR packaging
  ([`054e3da`](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/commit/054e3daf039df6fef461b64d4bf145fe446a5be0))

- Fixes 'No module named src' when installed via yay - .gitignore no longer conflicts with source
  directory - All imports updated to casper_keyboard_rgb.*
