#!/usr/bin/env python3
"""
Reusable tomb parser framework for Chinese archaeological reports.
Import the export/utility functions, write your own extraction logic.

Usage:
    from tomb_parser import TombParser

    parser = TombParser("报告名", "/path/to/input.txt", "/path/to/output_dir")
    parser.add_tomb({...})         # add parsed tomb entries
    parser.add_tombs([...])        # add multiple
    parser.export()                # writes JSON + CSV + MD
"""

import re
import json
import csv
import os


class TombParser:
    """Reusable parser with built-in tri-format export."""

    def __init__(self, report_name: str, input_file: str, output_dir: str):
        self.report_name = report_name
        self.input_file = input_file
        self.output_dir = output_dir
        self.tombs: list[dict] = []
        self.source_note = ""

        with open(input_file, 'r', encoding='utf-8') as f:
            self.text = f.read()
            self.lines = self.text.splitlines(keepends=True)

    # ------------------------------------------------------------------
    # Tomb management
    # ------------------------------------------------------------------

    def add_tomb(self, tomb: dict):
        """Add a single tomb entry. Missing keys get defaults."""
        defaults = {
            "墓葬编号": "", "年代": "", "墓向": "", "墓葬形制": "",
            "墓口长": None, "墓口宽": None, "墓深": None,
            "发掘位置": "", "层位": "", "备注": "",
            "随葬器物": []
        }
        entry = {**defaults, **tomb}
        # Ensure artifacts have correct keys too
        art_defaults = {
            "器物编号": "", "器物名称": "", "材质": "", "器型": "",
            "数量": 1, "特征描述": ""
        }
        entry["随葬器物"] = [
            {**art_defaults, **a} for a in entry.get("随葬器物", [])
        ]
        self.tombs.append(entry)

    def add_tombs(self, tombs: list[dict]):
        for t in tombs:
            self.add_tomb(t)

    # ------------------------------------------------------------------
    # Search helpers (read-only, for extraction scripts to use)
    # ------------------------------------------------------------------

    def grep(self, pattern: str, flags=0) -> list[tuple[int, str]]:
        """Search text, return list of (line_number_1indexed, line_text)."""
        results = []
        for i, line in enumerate(self.lines):
            if re.search(pattern, line, flags):
                results.append((i + 1, line.rstrip()))
        return results

    def grep_context(self, pattern: str, before: int = 3, after: int = 10) -> list[str]:
        """Search and return surrounding context blocks."""
        matches = []
        for i, line in enumerate(self.lines):
            if re.search(pattern, line):
                start = max(0, i - before)
                end = min(len(self.lines), i + after + 1)
                block = ''.join(self.lines[start:end])
                matches.append(block)
        return matches

    def get_section(self, start_line: int, end_line: int) -> str:
        """Get text between line numbers (1-indexed, inclusive)."""
        return ''.join(self.lines[start_line - 1:end_line])

    # ------------------------------------------------------------------
    # Classification utilities
    # ------------------------------------------------------------------

    @staticmethod
    def classify_material(name: str) -> str:
        rules = [
            (['陶', '泥质', '灰陶', '红陶'], "陶器"),
            (['瓷', '白胎', '青花', '釉', '窑'], "瓷器"),
            (['铜', '青铜', '銅'], "青铜器"),
            (['铁', '鐵'], "铁器"),
            (['玉', '石', '玛瑙', '绿松石', '翡翠'], "玉石器"),
            (['骨', '角', '牙'], "骨角牙器"),
            (['漆', '木'], "漆木器"),
            (['金', '银', '金'], "金银器"),
            (['钱', '币', '铢', '宝', '贝'], "货币"),
            (['料', '琉璃', '玻璃'], "料器"),
        ]
        for keywords, material in rules:
            if any(k in name for k in keywords):
                return material
        return "其他"

    @staticmethod
    def classify_vessel_type(name: str) -> str:
        types = {
            '罐': '罐', '壶': '壶', '瓶': '瓶', '盆': '盆', '碗': '碗',
            '盘': '盘', '杯': '杯', '尊': '尊', '罍': '罍', '瓮': '瓮',
            '鬲': '鬲', '豆': '豆', '簋': '簋', '爵': '爵', '鼎': '鼎',
            '洗': '洗', '炉': '炉', '灯': '灯', '枕': '枕', '碟': '碟',
            '盏': '盏', '缸': '缸', '盒': '盒', '镜': '镜',
            '戈': '戈', '矛': '矛', '剑': '剑', '刀': '刀', '镞': '镞',
            '斧': '斧', '锛': '锛', '凿': '凿', '铲': '铲',
            '璧': '璧', '琮': '琮', '璜': '璜', '环': '环', '珠': '串珠',
            '簪': '簪', '钗': '簪', '镯': '手镯', '带钩': '带钩',
            '钱': '钱币', '币': '钱币', '印': '印章', '俑': '俑',
        }
        for key, val in types.items():
            if key in name:
                return val
        return name

    @staticmethod
    def parse_num(s: str):
        if not s:
            return None
        s = s.strip()
        if '~' in s:
            parts = s.split('~')
            try:
                return round((float(parts[0]) + float(parts[1])) / 2, 2)
            except ValueError:
                return s
        try:
            return float(s)
        except ValueError:
            return s

    @staticmethod
    def extract_dimensions(text: str) -> dict:
        result = {"墓口长": None, "墓口宽": None, "墓深": None}
        m = re.search(
            r'(?:南北)?长\s*([\d.]+)\s*[、，]\s*(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)\s*[、，]\s*(?:残)?深\s*([\d.]+(?:~[\d.]+)?)',
            text
        )
        if m:
            result["墓口长"] = TombParser.parse_num(m.group(1))
            result["墓口宽"] = TombParser.parse_num(m.group(2))
            result["墓深"] = TombParser.parse_num(m.group(3))
        return result

    @staticmethod
    def extract_direction(text: str) -> str:
        for pattern in [
            r'方向\s*\$?\s*(\d+)\s*\^?\{?\\?circ\}?\s*\$?°?',
            r'方向\s*(\d+)°',
            r'方向\s*(南北向|东西向|南向|北向|东向|西向)',
        ]:
            m = re.search(pattern, text)
            if m:
                val = m.group(1)
                return f"{val}°" if val.isdigit() else val
        return ""

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_tombs(self):
        def key(t):
            id_str = t['墓葬编号']
            m = re.search(r'(\d+)$', id_str)
            if m:
                prefix = re.sub(r'\d+$', '', id_str) or 'Z'
                return (prefix, int(m.group(1)))
            return (id_str, 0)
        self.tombs.sort(key=key)

    # ------------------------------------------------------------------
    # Export (JSON + CSV + MD)
    # ------------------------------------------------------------------

    def export(self):
        self.sort_tombs()
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"Exporting {len(self.tombs)} tombs...")
        self._export_json()
        self._export_csv()
        self._export_markdown()
        total_art = sum(len(t.get('随葬器物', [])) for t in self.tombs)
        print(f"Total artifacts: {total_art}")
        print(f"Output: {self.output_dir}/")

    def _export_json(self):
        path = os.path.join(self.output_dir, "tombs.json")
        output = {
            "墓葬列表": self.tombs,
            "原始文本片段": self.source_note or f"来源：{self.report_name}，共提取{len(self.tombs)}座墓葬"
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  JSON: {path}")

    def _export_csv(self):
        path = os.path.join(self.output_dir, "tombs.csv")
        headers = [
            "墓葬编号", "年代", "墓向", "墓葬形制", "墓口长", "墓口宽", "墓深",
            "发掘位置", "层位", "备注",
            "器物编号", "器物名称", "材质", "器型", "数量", "特征描述"
        ]
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(headers)
            for t in self.tombs:
                base = [
                    t.get(k, '') for k in [
                        '墓葬编号', '年代', '墓向', '墓葬形制',
                        '墓口长', '墓口宽', '墓深', '发掘位置', '层位', '备注'
                    ]
                ]
                arts = t.get('随葬器物', [])
                if arts:
                    for a in arts:
                        row = base + [a.get(k, '') for k in [
                            '器物编号', '器物名称', '材质', '器型', '数量', '特征描述'
                        ]]
                        w.writerow(row)
                else:
                    w.writerow(base + [''] * 6)
        print(f"  CSV:  {path}")

    def _export_markdown(self):
        path = os.path.join(self.output_dir, "tombs.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# 墓葬数据 — {self.report_name}\n\n")
            f.write(f"共提取 **{len(self.tombs)}** 条墓葬记录\n\n")

            # Overview table
            f.write("## 概览\n\n")
            f.write("| 墓葬编号 | 年代 | 形制 | 尺寸(长×宽×深) | 随葬品数 |\n")
            f.write("|----------|------|------|----------------|----------|\n")
            for t in self.tombs:
                dim = ""
                if t.get('墓口长'):
                    dim = f"{t['墓口长']}×{t.get('墓口宽', '')}×{t.get('墓深', '')}m"
                f.write(f"| {t['墓葬编号']} | {t.get('年代', '')} | "
                        f"{t.get('墓葬形制', '')} | {dim} | "
                        f"{len(t.get('随葬器物', []))} |\n")
            f.write("\n")

            # Detail per tomb
            f.write("## 详细记录\n\n")
            for t in self.tombs:
                f.write(f"### {t['墓葬编号']}\n\n")
                for label in ['年代', '墓向', '墓葬形制', '墓口长', '墓口宽',
                              '墓深', '发掘位置', '层位', '备注']:
                    val = t.get(label, '')
                    if val:
                        f.write(f"- **{label}**: {val}\n")
                arts = t.get('随葬器物', [])
                if arts:
                    f.write(f"\n**随葬器物** ({len(arts)}件)\n\n")
                    f.write("| 编号 | 名称 | 材质 | 器型 | 数量 | 特征描述 |\n")
                    f.write("|------|------|------|------|------|----------|\n")
                    for a in arts:
                        desc = a.get('特征描述', '')
                        if len(desc) > 80:
                            desc = desc[:80] + '...'
                        f.write(f"| {a.get('器物编号', '')} | {a.get('器物名称', '')} | "
                                f"{a.get('材质', '')} | {a.get('器型', '')} | "
                                f"{a.get('数量', '')} | {desc} |\n")
                f.write("\n")
        print(f"  MD:   {path}")


# ======================================================================
# Example usage (for testing / reference)
# ======================================================================
if __name__ == '__main__':
    # Quick test with dummy data
    p = TombParser("测试报告", "/dev/null", "/tmp/tomb_test")
    p.add_tomb({
        "墓葬编号": "M1",
        "年代": "汉代",
        "墓葬形制": "土坑竖穴墓",
        "墓口长": 3.1, "墓口宽": 2.16, "墓深": 1.9,
        "随葬器物": [{
            "器物编号": "M1:1", "器物名称": "陶壶",
            "材质": "陶器", "器型": "壶", "数量": 2,
            "特征描述": "泥质灰陶。盘口，束颈。"
        }]
    })
    p.export()
