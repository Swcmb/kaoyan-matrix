# SPDX-License-Identifier: GPL-3.0-or-later
"""真实 MCP 协议端到端：以 stdio 启动 server.py，initialize → list_tools → call_tool。

这是「注册 ≠ 可加载」的最终证据：走完整 MCP 协议，不做 Python 直接调用。
用法：python tests/smoke_stdio.py
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402
from mcp.client.session import ClientSession  # noqa: E402

# 查询串从索引本身取出，避免把站点原文写进测试文件
FAKE_STEM = '设椭球面 x^2+2y^2+3z^2=6 与参数为 7 的泊松分布相切，求主轴长度与偏度系数之积'


def payload_of(res):
    return res.structured_content or json.loads(res.content[0].text)


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'server.py')])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print('server:', info.server_info.name, '| protocol:', info.protocol_version)

            tools = (await session.list_tools()).tools
            print('tools:', [t.name for t in tools])
            for t in tools:
                print(f'  - {t.name}: required='
                      f'{t.input_schema.get("required", [])} props='
                      f'{sorted(t.input_schema.get("properties", {}))}')

            # 取 2024 数学一第 10 题的题干原文作为查询（运行时读取，不落盘）
            import index
            recs = index.load()['records']
            stem = next(r['stem'] for r in recs
                        if r['year'] == 2024 and r['subject'] == '数学一' and r['num'] == 10)
            res = await session.call_tool('find_problem', {'stem': stem})
            print('\n[A 完整题干原文] is_error:', res.is_error)
            p = payload_of(res)
            print('verdict:', p['verdict'])
            print('reason:', p['reason'], '| hits:', len(p['hits']),
                  '| index:', p['index'])
            for h in p['hits']:
                print(f"  {h['year']} {h['subject']} 第{h['num']}题 "
                      f"{h['match']} conf={h['confidence']} ratio={h['ratio']} "
                      f"{h['url']}")

            for name, args in (('B 空题干', {'stem': '   '}),
                               ('C 短题干', {'stem': '曲线'}),
                               ('D 编造题干', {'stem': FAKE_STEM})):
                r = await session.call_tool('find_problem', args)
                if r.is_error:
                    print(f'\n[{name}] is_error=True |', r.content[0].text[:70])
                else:
                    q = payload_of(r)
                    print(f'\n[{name}] reason={q["reason"]} hits={len(q["hits"])} '
                          f'match集合={[h["match"] for h in q["hits"]]}')
                    print('   verdict:', q['verdict'])

            e = await session.call_tool('find_problem',
                                        {'stem': stem[:40], 'year': 2024})
            print('\n[E 前半句 + 限定年份]', payload_of(e)['verdict'])

            f = await session.call_tool('find_problem', {'stem': stem, 'top_k': 99})
            print('[F top_k 越界钳制] is_error:', f.is_error,
                  'hits:', len(payload_of(f)['hits']))
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
