"""Prepare the exact upstream rendering sources with explicit Linux substitutions.

No generated source is committed. All changes are reproducible against the lock.
"""
import json
import pathlib
import re
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / 'upstream.lock.json').read_text())['wled']
PORT_CHECKOUT = ROOT.parent.name == 'ports' and (ROOT.parents[1] / 'wled00').is_dir()
SRC = ROOT.parents[1] if PORT_CHECKOUT else ROOT / ('.upstream/WLED-linux' if LOCK.get('port_commit') else '.upstream/WLED')
OUT = ROOT / 'build/engine'


def replace_function(text, signature, body):
    start = text.index(signature)
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    # Targeted upstream functions do not contain unbalanced braces in strings.
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[:brace] + '{\n' + body + '\n}' + text[end:]


def prepare_checkout():
    if not SRC.exists():
        port = bool(LOCK.get('port_commit'))
        subprocess.run(['git', 'clone', '--no-checkout', '--branch', LOCK['branch'] if port else LOCK['tag'], '--depth', '2',
                        LOCK['fork'] if port else LOCK['repository'], str(SRC)], check=True)
        revision = LOCK.get('port_commit', LOCK['commit'])
        subprocess.run(['git', '-C', str(SRC), 'fetch', '--depth', '2', 'origin', revision], check=True)
        subprocess.run(['git', '-C', str(SRC), 'checkout', '--detach', revision], check=True)
    actual = subprocess.check_output(['git', '-C', str(SRC), 'rev-parse', 'HEAD'], text=True).strip()
    if not PORT_CHECKOUT and actual != LOCK.get('port_commit', LOCK['commit']):
        dirty = subprocess.check_output(['git', '-c', 'core.autocrlf=true', '-c', 'core.filemode=false', '-C', str(SRC), 'status', '--porcelain'], text=True).strip()
        branch = subprocess.check_output(['git', '-C', str(SRC), 'branch', '--show-current'], text=True).strip()
        if dirty or branch:
            raise SystemExit('WLED pin changed; refusing to replace a modified or branch-based checkout')
        revision = LOCK.get('port_commit', LOCK['commit'])
        subprocess.run(['git', '-C', str(SRC), 'fetch', '--depth', '2', 'origin', revision], check=True)
        subprocess.run(['git', '-C', str(SRC), 'checkout', '--detach', revision], check=True)
    # The original release can be farther back than a shallow port clone reaches.
    if subprocess.run(['git', '-C', str(SRC), 'cat-file', '-e', LOCK['commit'] + ':wled00'],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        subprocess.run(['git', '-C', str(SRC), 'fetch', '--depth', '1', 'origin', LOCK['commit']], check=True)
    for revision in ('HEAD', LOCK['commit']):
        tree = subprocess.check_output(['git', '-C', str(SRC), 'rev-parse', revision + ':wled00'], text=True).strip()
        if revision == 'HEAD':
            source_tree = tree
        elif tree != source_tree:
            raise SystemExit('Port branch altered the pinned upstream wled00 source tree')
    if subprocess.check_output(['git', '-c', 'core.autocrlf=true', '-c', 'core.filemode=false', '-C', str(SRC), 'status', '--porcelain', '--', 'wled00'], text=True).strip():
        raise SystemExit('Refusing a modified upstream source tree')
    if LOCK.get('port_commit') and not PORT_CHECKOUT:
        for path in (ROOT / 'runtime/linux').glob('*'):
            mirror = SRC / 'ports/fpp-linux/runtime/linux' / path.name
            if path.read_text() != mirror.read_text():
                raise SystemExit('Local Linux wrappers differ from the pinned port branch: ' + path.name)


def main():
    prepare_checkout()
    OUT.mkdir(parents=True, exist_ok=True)
    source = SRC / 'wled00'
    names = ['FX.cpp', 'FX.h', 'FX_fcn.cpp', 'FX_2Dfcn.cpp', 'FXparticleSystem.h',
             'colors.cpp', 'colors.h', 'const.h', 'prng.h', 'palettes.cpp',
             'wled_math.cpp', 'fontmanager.h', 'fontmanager.cpp', 'FXparticleSystem.cpp']
    for name in names:
        shutil.copyfile(source / name, OUT / name)
    shutil.copytree(source / 'src/dependencies/fastled_slim',
                    OUT / 'src/dependencies/fastled_slim', dirs_exist_ok=True)
    shutil.copytree(source / 'src/font', OUT / 'src/font', dirs_exist_ok=True)
    fcn = (source / 'fcn_declare.h').read_text()
    math = fcn[fcn.index('//wled_math.cpp'):fcn.index('//wled_serial.cpp')]
    util = fcn[fcn.index('uint16_t beat88('):fcn.index('// fast (true) random')]
    util = util.replace('um_data_t* simulateSound(uint8_t simulationId);', '')
    (OUT / 'fcn_declare.h').write_text('#pragma once\n' + math + util)
    fx = (OUT / 'FX_fcn.cpp').read_text()
    fx = replace_function(fx, 'void WS2812FX::finalizeInit()', '''
  _length = linux_pixels;
  _hasWhiteChannel = linux_rgbw;
  Segment::maxWidth = linux_width;
  Segment::maxHeight = linux_height;
  isMatrix = linux_height > 1;
  updatePixelBuffer();
  resetSegments();
  fixInvalidSegments();
''')
    fx = replace_function(fx, 'bool WS2812FX::deserializeMap(', 'return false;')
    fx = fx.replace('pgm_read_dword(&(gGradientPalettes', 'pgm_read_ptr(&(gGradientPalettes')
    (OUT / 'FX_fcn.cpp').write_text(fx)
    two = (OUT / 'FX_2Dfcn.cpp').read_text()
    two = replace_function(two, 'void WS2812FX::setUpMatrix()', '/* mapping supplied by the Linux coordinator */')
    (OUT / 'FX_2Dfcn.cpp').write_text(two)
    colors = (OUT / 'colors.cpp').read_text()
    colors = replace_function(colors, 'void loadCustomPalettes()', '/* coordinator owns persistent palettes */')
    (OUT / 'colors.cpp').write_text(colors)
    fonts = (OUT / 'fontmanager.cpp').read_text()
    fonts = replace_function(fonts, 'void FontManager::getFontFileName(', "buffer[0] = '\\0'; if (getMetadata()) getMetadata()->availableFonts = 0;")
    (OUT / 'fontmanager.cpp').write_text(fonts)
    util_source = (source / 'util.cpp').read_text()
    chunks = ['// Extracted from pinned WLED util.cpp; EUPL-1.2-or-later.\n'
              '// Copyright (c) Christian Schwinne and individual WLED contributors.\n'
              '// Beat functions derive from FastLED 3.6.0, MIT; see src/dependencies/fastled_slim/LICENSE.txt.\n'
              '// Fixed point integer Perlin noise functions by @dedehai.\n'
              '#include "wled.h"\n']
    for signature in ['uint32_t utf8_decode(', 'size_t utf8_strlen(', 'int16_t extractModeDefaults(',
                      'uint16_t beat88(', 'uint16_t beat16(', 'uint8_t beat8(',
                      'uint16_t beatsin88_t(', 'uint16_t beatsin16_t(', 'uint8_t beatsin8_t(',
                      'uint8_t get_random_wheel_index(', 'float mapf(', 'uint32_t hashInt(']:
        start = util_source.index(signature)
        brace = util_source.index('{', start)
        depth, end = 1, brace + 1
        while depth:
            depth += (util_source[end] == '{') - (util_source[end] == '}')
            end += 1
        chunks.append(util_source[start:end])
    chunks.append(util_source[util_source.index('#define PERLIN_SHIFT'):util_source.index('String computeSHA1(')])
    (OUT / 'linux_util.cpp').write_text('\n'.join(chunks))
    for path in (ROOT / 'runtime/linux').glob('*'):
        shutil.copyfile(path, OUT / path.name)
    ui = ROOT / 'build/ui'
    ui.mkdir(parents=True, exist_ok=True)
    for name in ['index.htm', 'index.js', 'index.css', 'common.js', 'iro.js', 'rangetouch.js', 'favicon.ico']:
        shutil.copyfile(source / 'data' / name, ui / name)
    shutil.copyfile(ROOT / 'icon.png', ui / 'icon.png')
    markup = (ui / 'index.htm').read_text()
    import re
    markup = re.sub(r'<link rel="(?:shortcut icon|apple-touch-icon)"[^>]*>', '', markup)
    markup = markup.replace('</head>', '<link rel="icon" type="image/png" href="icon.png"><link rel="apple-touch-icon" href="icon.png"></head>')
    (ui / 'index.htm').write_text(markup)
    # The upstream device-only WebSocket fallback drops a configurable port.
    js = (ui / 'index.js').read_text()
    js = js.replace('window.location.hostname+"/ws"', 'window.location.host+"/ws"')
    js = js.replace('checkVersionUpgrade(i);', '/* Linux releases are managed by the FPP plugin installer. */')
    # readState runs on every Linux status notification. Upstream starts this
    # interval inside readState; without a guard an open tab accumulates timers.
    interval = 'setInterval(setSelectedEffectPosition,750);'
    if js.count(interval) != 1:
        raise SystemExit('Review upstream selected-effect timer before preparing UI')
    js = js.replace(interval, 'window.linuxEffectPositionTimer ||= setInterval(setSelectedEffectPosition,750);')
    # Keep the editor/draft until the authenticated HTTP save is acknowledged.
    save_start = '\tshowToast("Saving " + pN +" (" + pI + ")");'
    if js.count(save_start) != 1:
        raise SystemExit('Review upstream preset save before preparing UI')
    js = js.replace(save_start, '\twindow.wledSavePreset(obj); return;\n' + save_start)
    delete_start = '\t\trequestJson(obj);\n\t\tdelete pJson[i];'
    if js.count(delete_start) != 1:
        raise SystemExit('Review upstream preset deletion before preparing UI')
    js = js.replace(delete_start, '\t\twindow.wledSavePreset(obj); return;\n' + delete_start)
    # Palette edits can retain the same slot count. Include the content revision
    # in the upstream browser cache key so reloading shows the updated gradient.
    js = js.replace('d.pcount == lastinfo.palcount', 'd.pcount == lastinfo.palcount && d.palrev == lastinfo.palrev')
    js = js.replace('pcount: lastinfo.palcount', 'palrev: lastinfo.palrev, pcount: lastinfo.palcount')
    (ui / 'index.js').write_text(js)
    print('Prepared WLED', LOCK['commit'])


if __name__ == '__main__':
    main()
