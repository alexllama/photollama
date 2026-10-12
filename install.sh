#!/bin/sh
set -e

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bindir="$HOME/.local/bin"
appdir="$HOME/.local/share/applications"
icondir="$HOME/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$bindir" "$appdir" "$icondir"

cat > "$bindir/photollama" <<EOF
#!/bin/sh
exec env PYTHONPATH="$here" /usr/bin/python3 -m photollama "\$@"
EOF
chmod +x "$bindir/photollama"

cp "$here/photollama/resources/photollama.svg" "$icondir/photollama.svg"

sed "s|@BIN@|$bindir/photollama|" \
    "$here/photollama/resources/photollama.desktop" > "$appdir/photollama.desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$appdir" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

for mime in image/jpeg image/png image/gif image/webp image/tiff image/bmp \
            image/svg+xml image/x-icon image/jp2; do
    xdg-mime default photollama.desktop "$mime" 2>/dev/null || true
done

echo "Installed: $bindir/photollama"
echo "Launcher : $appdir/photollama.desktop"
echo "Icon     : $icondir/photollama.svg"
