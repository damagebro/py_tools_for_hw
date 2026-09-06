#!/usr/bin/env bash
# Run in a disposable shell; installed versions remain available for inspection.
set -eo pipefail
if [[ $# != 3 ]]; then
    echo "Usage: PYTHON=/path/to/python bash test_release.sh BUNDLE_A BUNDLE_B INSTALL_ROOT" >&2
    exit 2
fi
source /usr/share/modules/init/bash
set -u
export PYTHON="$(command -v "${PYTHON:-python3}")"
"$PYTHON" -c 'import jinja2, openpyxl, markdown, yaml; import sys; print(sys.version)'
command -v git >/dev/null
install_root=$(realpath -m "$3")
case "$install_root" in
    /|/mnt|/mnt/*) echo "Use a dedicated Linux filesystem directory, not /mnt/*" >&2; exit 2 ;;
esac
mkdir -p "$install_root"
df -T "$install_root"

versions=()
for bundle in "$1" "$2"; do
    bundle=$(realpath "$bundle")
    "$PYTHON" -B "$bundle/hw_tool/publish/verify_release.py" "$bundle"
    version=$("$PYTHON" -c 'import sys,tomllib; print(tomllib.load(open(sys.argv[1],"rb"))["release"]["version"])' "$bundle/hw_tool/release_info.toml")
    "$PYTHON" - "$bundle" "$install_root" "$version" <<'PY'
import os
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZipFile
bundle, root, version = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
destination = root / version
modulefile = bundle / "modulefiles/hw_tool" / version
if f"set root {{{destination}/hw_tool}}" not in modulefile.read_text():
    raise SystemExit("modulefile install root mismatch; rebuild with --linux-install-root")
destination.mkdir()  # Never overwrite an installed release.
with ZipFile(bundle / f"hw_tool-{version}.zip") as archive:
    for entry in archive.infolist():
        path = PurePosixPath(entry.filename)
        if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
            raise SystemExit("unsafe ZIP member")
        extracted = archive.extract(entry, destination)
        if not entry.is_dir():
            os.chmod(extracted, entry.external_attr >> 16 & 0o777)
module_destination = root / "modulefiles/hw_tool" / version
module_destination.parent.mkdir(parents=True, exist_ok=True)
with module_destination.open("xb") as stream:
    stream.write(modulefile.read_bytes())
PY
    versions+=("$version")
done

module purge
module use "$install_root/modulefiles"
module avail hw_tool
baseline_path=$PATH
baseline_home=${HW_TOOL_HOME-}
baseline_version=${HW_TOOL_VERSION-}

check_loaded() {
    local version=$1
    [[ "$HW_TOOL_VERSION" == "$version" ]]
    [[ "$HW_TOOL_HOME" == "$install_root/$version/hw_tool" ]]
    [[ "$(command -v hw_tool)" == "$HW_TOOL_HOME/bin/hw_tool" ]]
    [[ -x "$HW_TOOL_HOME/bin/hw_tool" && -x "$HW_TOOL_HOME/hw_tool_de/bin/hw_tool_de" ]]
    hw_tool --version
    hw_tool doctor
    hw_tool verify
    hw_tool de test --smoke
    "$PYTHON" -B "$HW_TOOL_HOME/publish/verify_release.py" "$HW_TOOL_HOME"
}

module load "hw_tool/${versions[0]}"
check_loaded "${versions[0]}"
module switch "hw_tool/${versions[0]}" "hw_tool/${versions[1]}"
check_loaded "${versions[1]}"
module unload "hw_tool/${versions[1]}"
[[ "$PATH" == "$baseline_path" ]]
[[ "${HW_TOOL_HOME-}" == "$baseline_home" ]]
[[ "${HW_TOOL_VERSION-}" == "$baseline_version" ]]
echo "[OK] Linux load/switch/unload, dependencies, permissions, tool smoke and installed hashes"
