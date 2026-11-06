import pathlib
import re

for f in ['README.md', 'devnotes/DEVNOTES.md', 'server.py']:
    t = pathlib.Path(f).read_text(encoding='utf-8')
    neg = re.findall(r'不是[^。；，\n]{1,24}[，,]\s*(?:而)?是', t)
    stale = re.findall(r'约 5 秒|约 6 秒|48 ms|150 项|完全离线', t)
    path_bad = re.findall(r'默认 \./\.cache|（约 1\.1 MB，gitignore）$', t, re.M)
    print(f'{f:26s} | 否定式对比: {neg or "无"} | 旧数字残留: {stale or "无"} | 旧路径: {path_bad or "无"}')

rd = pathlib.Path('README.md').read_text(encoding='utf-8')
print('README 链接 devnotes:', 'devnotes' in rd.lower())
print('README 小节数:', rd.count('\n## ') + 1)
print('README 末段:', rd.strip().splitlines()[-1][:60])
