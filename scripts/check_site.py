from pathlib import Path
import re,json
root=Path(__file__).resolve().parents[1]
html=(root/'index.html').read_text()
js=(root/'app.js').read_text()
for path in re.findall(r'(?:src|href)="([^"]+)"',html):
    if path.startswith(('assets/','app.js','styles.css')):
        assert (root/path).is_file(),path
for path in re.findall(r'["\'](assets/[^"\']+)["\']',js):
    assert (root/path).is_file(),path
m=re.search(r'const researchTopics=(.*?);\n',js)
topics=json.loads(m.group(1))
keys=[k for topic in topics for k in topic[2]]
assert len(keys)==len(set(keys)), 'Duplicate Research assignments'
assert len(topics)==5
assert 'id="home-news"' in html
home=html[html.index('id="home-news"'):html.index('</section>',html.index('id="home-news"'))]
assert 'Bakteriopolis' not in home
assert 'SCOPE Synthesis Annual Meeting' in html
print('Local assets, Research assignments, and homepage News checks passed.')
