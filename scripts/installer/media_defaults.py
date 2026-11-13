"""Build and validate COSMIC media defaults from installed desktop entries."""
import configparser


VIEWER = 'com.system76.CosmicViewer.desktop'
VLC = 'vlc.desktop'
MIMEAPPS = 'etc/xdg/mimeapps.list'


def _parser():
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    return parser


def _mime_types(root, desktop):
    path = root / 'usr/share/applications' / desktop
    parser = _parser()
    if not path.is_file() or not parser.read(path) or not parser.has_section('Desktop Entry'):
        raise RuntimeError(f'Missing media desktop entry: {desktop}')
    mime_types = {value for value in parser.get('Desktop Entry', 'MimeType', fallback='').split(';')
                  if value}
    if not mime_types:
        raise RuntimeError(f'Media desktop entry has no MIME types: {desktop}')
    return mime_types


def expected_defaults(root):
    # COSMIC Viewer wins any overlap; VLC retains formats Viewer does not claim.
    defaults = {mime: VLC for mime in _mime_types(root, VLC)}
    defaults.update({mime: VIEWER for mime in _mime_types(root, VIEWER)})
    return defaults


def write_defaults(root):
    path = root / MIMEAPPS
    parser = _parser()
    if path.is_file():
        parser.read(path)
    if not parser.has_section('Default Applications'):
        parser.add_section('Default Applications')
    for mime, desktop in sorted(expected_defaults(root).items()):
        parser.set('Default Applications', mime, desktop)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as stream:
        parser.write(stream, space_around_delimiters=False)


def validate_defaults(root):
    parser = _parser()
    path = root / MIMEAPPS
    if not path.is_file() or not parser.read(path) or not parser.has_section('Default Applications'):
        raise RuntimeError('COSMIC media defaults are missing.')
    actual = dict(parser.items('Default Applications'))
    if any(actual.get(mime) != desktop for mime, desktop in expected_defaults(root).items()):
        raise RuntimeError('COSMIC media defaults do not match VLC and COSMIC Viewer support.')
