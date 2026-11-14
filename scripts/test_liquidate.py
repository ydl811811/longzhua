#!/usr/bin/env python3
"""test_liquidate.py —— 清仓工具回归测试

2026-11-13 新增。目的：保证 liquidate_position.py 产出的台账**一次就符合 schema v1**，
且不会破坏其它 position 块。

跑法：python3 ~/.hermes/scripts/test_liquidate.py
"""
import re
import sys
import shutil
import json
import tempfile
import unittest
import subprocess
from pathlib import Path

import yaml

SCRIPT = Path.home() / '.hermes/scripts/liquidate_position.py'
LINT = Path.home() / '.hermes/scripts/ledger_lint.py'
POS = Path.home() / '.hermes/stock-portfolio/monitor_positions.yaml'
STATE = Path.home() / '.hermes/stock-portfolio/portfolio_state.yaml'


def build_fixture(tmpdir):
    """复制 live 台账，复制 512480 块成测试标的 999999。"""
    lines = POS.read_text(encoding='utf-8').split('\n')
    pat = re.compile(r"^(\s*)-\s+code:\s*['\"]?(\w+)['\"]?\s*$")
    st = None
    for i, l in enumerate(lines):
        m = pat.match(l)
        if m and m.group(2) == '512480':
            st = i
            break
    assert st is not None, 'live 台账里没有 512480'
    ind = len(lines[st]) - len(lines[st].lstrip())
    en = len(lines)
    for j in range(st + 1, len(lines)):
        if lines[j].strip() and (len(lines[j]) - len(lines[j].lstrip())) <= ind:
            en = j
            break
    blk = [l.replace("code: '512480'", "code: '999999'")
            .replace('name: 半导体ETF国联安', 'name: 测试标的') for l in lines[st:en]]
    out = Path(tmpdir) / 'monitor_positions.yaml'
    out.write_text('\n'.join(lines[:en] + blk + lines[en:]), encoding='utf-8')
    return out


def run_liquidate(pos_path, *extra):
    """用测试副本跑 liquidate_position.py。"""
    code = SCRIPT.read_text(encoding='utf-8').replace(
        "POS = Path.home() / '.hermes/stock-portfolio/monitor_positions.yaml'",
        f"POS = Path('{pos_path}')")
    tmp_script = pos_path.parent / '_liq_test_run.py'
    tmp_script.write_text(code, encoding='utf-8')
    r = subprocess.run([sys.executable, str(tmp_script), '999999',
                        '--shares', '5000', '--price', '1.05',
                        '--time', '10:17:49', '--reason', '测试清仓'] + list(extra),
                       capture_output=True, text=True)
    return r


def run_lint(pos_path):
    code = LINT.read_text(encoding='utf-8').replace(
        "POS = BASE / 'monitor_positions.yaml'", f"POS = Path('{pos_path}')")
    tmp = pos_path.parent / '_lint_test_run.py'
    tmp.write_text(code, encoding='utf-8')
    r = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True)
    return r


class TestLiquidate(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='liq_test_'))
        self.pos = build_fixture(self.tmp)
        self.before = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        self.before_codes = [str(p['code']) for p in self.before['positions']]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ── 主流程 ──
    def test_liquidation_produces_schema_v1_output(self):
        r = run_liquidate(self.pos)
        self.assertEqual(r.returncode, 0, f'清仓失败:\n{r.stdout}\n{r.stderr}')

        doc = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        p = next(x for x in doc['positions'] if str(x['code']) == '999999')

        # 1) shares → 0，base_shares 保留
        self.assertEqual(p['shares'], 0)
        self.assertEqual(p['base_shares'], 5000)
        # 2) status / strategy
        self.assertEqual(p['status'], 'sold')
        self.assertEqual(p['strategy'], 'cleared')
        # 3) TP 全部 cleared（不是 done）
        for t in (p.get('take_profit') or []):
            self.assertEqual(t['status'], 'cleared')
        # 4) trailing_stop 清除
        self.assertIn(p.get('trailing_stop'), (None, 'null'))
        # 5) exit_record 正典结构
        er = p['exit_record']
        self.assertIsInstance(er, dict)
        for f in ('exit_date', 'exit_shares', 'exit_price', 'exit_amount',
                  'realized_pnl', 'realized_pnl_pct', 'cleared_at', 'cleared_reason'):
            self.assertIn(f, er, f'exit_record 缺 {f}')
        self.assertAlmostEqual(er['exit_amount'], er['exit_shares'] * er['exit_price'], places=2)
        self.assertEqual(er['exit_shares'], 5000)

    def test_top_level_deprecated_fields_removed(self):
        run_liquidate(self.pos)
        doc = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        p = next(x for x in doc['positions'] if str(x['code']) == '999999')
        for f in ('cleared_at', 'cleared_reason', 'realized_pnl',
                  'realized_pnl_pct', 'historical_exit_record'):
            self.assertNotIn(f, p, f'顶层废弃字段 {f} 未清除')

    def test_action_appended_with_controlled_vocab(self):
        run_liquidate(self.pos)
        doc = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        p = next(x for x in doc['positions'] if str(x['code']) == '999999')
        sells = [a for a in p['actions'] if a.get('type') == 'sell']
        self.assertEqual(len(sells), 1)
        a = sells[0]
        self.assertEqual(a['trigger'], 'manual')
        self.assertEqual(a['shares'], 5000)
        self.assertAlmostEqual(a['price'], 1.05)
        self.assertAlmostEqual(a['amount'], 5250.0)
        for f in ('date', 'time', 'type', 'trigger', 'shares', 'price', 'amount', 'reason'):
            self.assertIn(f, a)

    def test_other_positions_untouched(self):
        run_liquidate(self.pos)
        doc = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        after_codes = [str(p['code']) for p in doc['positions']]
        self.assertEqual(self.before_codes, after_codes, 'position 列表变了')

        B = {str(p['code']): p for p in self.before['positions']}
        A = {str(p['code']): p for p in doc['positions']}
        for c, b in B.items():
            if c == '999999':
                continue
            for f in ('shares', 'cost', 'stop_loss', 'status', 'strategy', 'base_shares'):
                self.assertEqual(b.get(f), A[c].get(f), f'{c}.{f} 被改动')

    def test_lint_passes_after_liquidation(self):
        r = run_liquidate(self.pos)
        self.assertEqual(r.returncode, 0)
        lr = run_lint(self.pos)
        self.assertEqual(lr.returncode, 0, f'linter 失败:\n{lr.stdout}')

    def test_partial_shares_rejected(self):
        """减仓不能走清仓模式。"""
        r = run_liquidate(self.pos, '--shares', '1000')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('清仓必须卖光全部', r.stdout + r.stderr)

    def test_bad_trigger_rejected(self):
        r = run_liquidate(self.pos, '--trigger', '随便写的')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('受控词表', r.stdout + r.stderr)

    def test_yaml_still_parseable(self):
        run_liquidate(self.pos)
        doc = yaml.safe_load(self.pos.read_text(encoding='utf-8'))
        self.assertIsInstance(doc, dict)
        self.assertIn('positions', doc)
        self.assertEqual(len(doc['positions']), len(self.before['positions']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
