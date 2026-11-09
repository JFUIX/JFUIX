"""Show named repository languages without changing contribution/activity totals."""
from collections import Counter
from pathlib import Path
from urllib.parse import quote
import json
import math
import os
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OWNER = os.environ.get('GITHUB_REPOSITORY_OWNER', 'JFUIX')
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
COLORS = {'HTML': '#e34c26', 'CSS': '#a78bfa', 'JavaScript': '#f1e05a', 'TypeScript': '#3178c6'}

def api(path):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'profile-language-chart'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com' + path, headers=headers), timeout=30) as response:
        return json.load(response)

def languages():
    totals = Counter()
    page = 1
    while True:
        repos = api(f'/users/{quote(OWNER)}/repos?type=owner&per_page=100&page={page}')
        for repo in repos:
            if repo.get('fork') or repo.get('archived') or repo['name'].lower() == OWNER.lower():
                continue
            # The profile automation repository is excluded from portfolio language usage.
            totals.update(api(f'/repos/{quote(OWNER)}/{quote(repo["name"])}/languages'))
        if len(repos) < 100:
            break
        page += 1
    return dict(sorted(totals.items(), key=lambda item: -item[1]))

def element(parent, tag, attrs=None, text=None):
    node = ET.SubElement(parent, '{' + NS + '}' + tag, {key: str(value) for key, value in (attrs or {}).items()})
    node.text = text
    return node

def point(radius, angle):
    return radius * math.cos(angle), radius * math.sin(angle)

def chart_panel(panel, values, foreground):
    for child in list(panel):
        panel.remove(child)
    total = sum(values.values())
    element(panel, 'title', text='Detected source-code bytes across public project repositories. Inline CSS and JavaScript are counted as HTML by GitHub.')
    element(panel, 'text', {'x': 0, 'y': 9, 'fill': foreground, 'font-size': 18, 'font-weight': 'bold'}, 'Languages used')
    donut = element(panel, 'g', {'transform': 'translate(118, 140)'})
    start = -math.pi / 2
    for index, (name, count) in enumerate(values.items()):
        fraction = count / total
        end = start + 2 * math.pi * fraction
        x1, y1 = point(95, start)
        x2, y2 = point(95, end)
        ix2, iy2 = point(58, end)
        ix1, iy1 = point(58, start)
        large = int(fraction > .5)
        color = COLORS.get(name, '#7ee787')
        shape = f'M{x1},{y1}A95,95,0,{large},1,{x2},{y2}L{ix2},{iy2}A58,58,0,{large},0,{ix1},{iy1}Z'
        part = element(donut, 'path', {'d': shape, 'fill': color})
        element(part, 'title', text=f'{name}: {count:,} bytes ({fraction:.1%})')
        y = 65 + index * 43
        element(panel, 'circle', {'cx': 254, 'cy': y - 5, 'r': 6, 'fill': color})
        element(panel, 'text', {'x': 271, 'y': y, 'fill': foreground, 'font-size': 19}, name)
        element(panel, 'text', {'x': 443, 'y': y, 'fill': foreground, 'font-size': 16, 'text-anchor': 'end'}, f'{fraction:.1%}')
        start = end
    element(panel, 'text', {'x': 0, 'y': 270, 'fill': foreground, 'font-size': 12, 'opacity': '.7'}, 'Source bytes across public projects; not a proficiency score.')

def update_svg(path, values):
    root = ET.parse(path).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    # Locate the original contribution-language legend without altering the 3D graph.
    old = next((node for node in root.iter() if node.tag == '{' + NS + '}text' and node.text in ('HTML', 'Languages used')), None)
    if old is None:
        return False
    panel = parents[parents[old]] if old.text == 'HTML' else parents[old]
    if panel is root:
        return False
    foreground = old.get('fill', '#eeeeff')
    chart_panel(panel, values, foreground)
    path.write_text(ET.tostring(root, encoding='unicode'))
    return True

def main():
    values = languages()
    if not values or not sum(values.values()):
        raise RuntimeError('No language data returned; existing charts left untouched.')
    updated = 0
    for path in (ROOT / 'profile-3d-contrib').glob('*.svg'):
        updated += update_svg(path, values)
    (ROOT / 'assets/languages.json').write_text(json.dumps({'metric': 'GitHub-detected source bytes', 'languages': values}, indent=2) + '\n')
    print('Updated language labels:', ', '.join(values), '| charts:', updated)

if __name__ == '__main__':
    main()
