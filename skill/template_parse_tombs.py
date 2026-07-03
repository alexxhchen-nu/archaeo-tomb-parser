#!/usr/bin/env python3
"""
Tomb Parsing Template (考古墓葬解析模板)

Usage:
1. Copy this file to your working directory
2. Update INPUT_FILE, OUTPUT_FILE, and DYNASTY_RANGES
3. Run: python3 parse_tombs.py

Customize for your report by:
- Finding chapter line numbers: grep -n "^## 第[二三四五六七八九]章" <file>
- Updating DYNASTY_RANGES with exact line numbers
- Adding/removing tomb types in extract_tomb_type() if needed
"""

import re
import json
import csv
import os

# ============================================================
# CUSTOMIZE THESE FOR YOUR REPORT
# ============================================================

INPUT_FILE = "path/to/your/report.md"
OUTPUT_DIR = "path/to/output_dir"
REPORT_NAME = "考古报告"

# Dynasty chapter line ranges
# Find with: grep -n "^## 第[二三四五六七八九]章" <file>
DYNASTY_RANGES = [
    (START_LINE, END_LINE, "汉代"),    # 第二章
    (START_LINE, END_LINE, "唐代"),    # 第三章
    (START_LINE, END_LINE, "宋代"),    # 第四章
    (START_LINE, END_LINE, "金代"),    # 第五章
    (START_LINE, END_LINE, "元代"),    # 第六章
    (START_LINE, END_LINE, "明代"),    # 第七章
    (START_LINE, END_LINE, "清代"),    # 第八章
]

# ============================================================
# NO CHANGES NEEDED BELOW (usually)
# ============================================================

def get_dynasty(line_num):
    for start, end, dynasty in DYNASTY_RANGES:
        if start <= line_num < end:
            return dynasty
    return ""

def extract_tomb_id(text):
    """Extract tomb ID like M3, M23, M317 etc."""
    m = re.search(r'\bM(\d+)\b', text)
    if m:
        return f"M{m.group(1)}"
    return None

def extract_direction(text):
    """Extract tomb direction/orientation."""
    # Pattern: 方向94° or 方向 $ 8^{\circ} $ or 方向185°
    m = re.search(r'方向\s*\$?\s*(\d+)\s*\^?\{?\\?circ\}?\s*\$?°?', text)
    if m:
        return f"{m.group(1)}°"
    # Pattern: 方向8° (直接带度数)
    m = re.search(r'方向\s*(\d+)°', text)
    if m:
        return f"{m.group(1)}°"
    # Pattern: 南北向 etc
    m = re.search(r'方向\s*(南北向|东西向|南向|北向|东向|西向)', text)
    if m:
        return m.group(1)
    return ""

def extract_tomb_type(text):
    """Extract tomb type/形制."""
    # Remove spaces for matching (text may have spaces due to line breaks)
    text_no_space = text.replace(' ', '')
    # Add or remove types as needed for your report
    types = [
        "土坑竖穴砖椁墓", "土坑竖穴墓", "土坑洞室墓", "砖室墓",
        "舟形墓", "砖、石室墓", "石室墓"
    ]
    for t in types:
        if t in text_no_space:
            return t
    return ""

def extract_dimensions(text):
    """Extract length, width, depth from description."""
    result = {"墓口长": None, "墓口宽": None, "墓深": None}
    
    # Pattern: 长2.7、宽2、深1.3米
    # Also: 长 2.7、宽 2、深 1.3 米
    # Also: 南北长2.4、宽1.2、残深0.34米
    m = re.search(r'(?:南北)?长\s*([\d.]+)\s*[、，]\s*(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)\s*[、，]\s*(?:残)?深\s*([\d.]+(?:~[\d.]+)?)', text)
    if m:
        result["墓口长"] = parse_num(m.group(1))
        result["墓口宽"] = parse_num(m.group(2))
        result["墓深"] = parse_num(m.group(3))
        return result
    
    # Try separate patterns
    m = re.search(r'(?:南北)?长\s*([\d.]+)', text)
    if m:
        result["墓口长"] = parse_num(m.group(1))
    m = re.search(r'(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)', text)
    if m:
        result["墓口宽"] = parse_num(m.group(2) if m.lastindex >= 2 else m.group(1))
    m = re.search(r'(?:残)?深\s*([\d.]+(?:~[\d.]+)?)', text)
    if m:
        result["墓深"] = parse_num(m.group(1))
    
    return result

def parse_num(s):
    """Parse a number string, handling ranges like '1.2~1.5'."""
    if not s:
        return None
    s = s.strip()
    if '~' in s:
        parts = s.split('~')
        try:
            return round((float(parts[0]) + float(parts[1])) / 2, 2)
        except:
            return s
    try:
        return float(s)
    except:
        return s

def extract_artifacts_from_desc(text, tomb_id):
    """Extract artifacts from the main tomb description paragraph."""
    artifacts = []
    
    # Look for 随葬品 pattern
    m = re.search(r'随葬品有(.+?)(?:$|(?:图\d|图版))', text, re.DOTALL)
    if not m:
        # Check for 无随葬品
        if '无随葬品' in text:
            return artifacts
        return artifacts
    
    desc = m.group(1)
    
    # Extract individual artifacts with tomb:item numbering
    # Pattern: 陶罐1件(M3:1) or 铜钱3枚（1组） etc
    artifact_patterns = [
        # Pattern with explicit ID: 灰陶罐1件 or 陶罐 1 件（M3:1）
        r'([\u4e00-\u9fff]+)\s*(\d+)\s*件(?:\s*（\d+组）)?(?:\s*[（(]\s*(M\d+:\d+(?:-\d+)?)\s*[）)])?',
        # Pattern: 铜钱3枚（1组）
        r'([\u4e00-\u9fff]+)\s*(\d+)\s*枚(?:\s*（\d+组）)?',
    ]
    
    for pat in artifact_patterns:
        for m in re.finditer(pat, desc):
            name = m.group(1)
            # Clean up name - remove "其中" prefix
            name = re.sub(r'^其中', '', name)
            count = int(m.group(2))
            item_id = m.group(3) if m.lastindex >= 3 and m.group(3) else f"{tomb_id}:{len(artifacts)+1}"
            artifacts.append({
                "器物编号": item_id,
                "器物名称": name,
                "材质": classify_material(name),
                "器型": classify_vessel_type(name),
                "数量": count,
                "特征描述": ""
            })
    
    return artifacts

def extract_detailed_artifacts(text, tomb_id):
    """Extract detailed artifact descriptions that follow the main tomb paragraph."""
    artifacts = []
    
    # Pattern: 器物名 N件（MX:N）。description
    # Or: 器物名 N件。description
    pattern = r'^([\u4e00-\u9fff]+)\s+(\d+)\s*件[。.]?\s*(?:（(M\d+:\d+(?:-\d+)?)）)?\s*(.+?)(?=\n\n|\n<|\n##|\Z)'
    
    for m in re.finditer(pattern, text, re.MULTILINE | re.DOTALL):
        name = m.group(1)
        # Clean up name - remove "其中" prefix
        name = re.sub(r'^其中', '', name)
        count = int(m.group(2))
        item_id = m.group(3) if m.group(3) else f"{tomb_id}:{len(artifacts)+1}"
        desc = m.group(4).strip()
        # Clean up description - remove image references
        desc = re.sub(r'图\s*[\d-]+', '', desc)
        desc = re.sub(r'图版\s*[\d-]+', '', desc)
        desc = desc.strip()
        
        artifacts.append({
            "器物编号": item_id,
            "器物名称": name,
            "材质": classify_material(name),
            "器型": classify_vessel_type(name),
            "数量": count,
            "特征描述": desc[:200] if desc else ""
        })
    
    return artifacts

def classify_material(name):
    """Classify artifact material based on name."""
    if any(k in name for k in ['陶', '泥质']):
        return "陶器"
    if any(k in name for k in ['瓷', '白胎', '青花']):
        return "瓷器"
    if any(k in name for k in ['铜', '青铜']):
        return "青铜器"
    if '铁' in name:
        return "铁器"
    if any(k in name for k in ['玉', '石', '玛瑙', '绿松石']):
        return "玉石器"
    if any(k in name for k in ['骨', '角', '牙']):
        return "骨角牙器"
    if any(k in name for k in ['漆', '木']):
        return "漆木器"
    if any(k in name for k in ['金', '银']):
        return "金银器"
    if any(k in name for k in ['钱', '币', '铢', '宝']):
        return "货币"
    if '料' in name:
        return "料器"
    return "其他"

def classify_vessel_type(name):
    """Classify artifact vessel type based on name."""
    vessel_types = {
        '罐': '罐', '壶': '壶', '瓶': '瓶', '盆': '盆', '碗': '碗',
        '盘': '盘', '杯': '杯', '尊': '尊', '罍': '罍', '瓮': '瓮',
        '鬲': '鬲', '豆': '豆', '簋': '簋', '爵': '爵', '斝': '斝',
        '觚': '觚', '鼎': '鼎', '洗': '洗', '炉': '炉', '灯': '灯',
        '枕': '枕', '碟': '碟', '盏': '盏', '缸': '缸',
        '戈': '戈', '矛': '矛', '剑': '剑', '刀': '刀', '镞': '镞',
        '戟': '戟', '弩机': '弩机',
        '斧': '斧', '锛': '锛', '凿': '凿', '铲': '铲', '锄': '锄',
        '镰': '镰', '纺轮': '纺轮', '锥': '锥',
        '璧': '璧', '琮': '琮', '璜': '璜', '玦': '玦', '环': '环',
        '串珠': '串珠', '珠': '串珠', '坠': '坠饰', '带钩': '带钩',
        '带扣': '带扣', '带饰': '带饰', '耳坠': '耳坠', '耳环': '耳环',
        '手镯': '手镯', '镯': '手镯', '簪': '簪', '钗': '簪',
        '扣': '扣饰', '铃': '铃', '鼓': '鼓', '磬': '磬',
        '印': '印章', '镜': '镜', '钱': '钱币', '币': '钱币',
        '俑': '俑', '案': '案', '台': '台',
    }
    for key, val in vessel_types.items():
        if key in name:
            return val
    return name

def parse_file():
    """Main parsing function."""
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    full_text = ''.join(lines)
    tombs = []
    
    # Find all tomb section headers: ## N、 MXX or ## MXX
    # Pattern: lines starting with ## followed by optional number + 、 then M + digits
    tomb_headers = []
    for i, line in enumerate(lines):
        # Match patterns like: ## 一、 M3  or ## M3  or # M3
        # Also handle "M 50" with space
        m = re.match(r'^#{1,3}\s*(?:[一二三四五六七八九十百千]+、\s*)?(M\s*\d+)\b', line)
        if m:
            tomb_id = m.group(1).replace(' ', '')  # Remove spaces
            tomb_headers.append((i+1, tomb_id))  # (1-indexed line, tomb_id)
    
    print(f"Found {len(tomb_headers)} tomb headers")
    
    # Process each tomb
    for idx, (line_num, tomb_id) in enumerate(tomb_headers):
        # Determine the section of text for this tomb
        start_line = line_num - 1  # 0-indexed
        if idx + 1 < len(tomb_headers):
            end_line = tomb_headers[idx + 1][0] - 1
        else:
            end_line = len(lines)
        
        # Get the text block for this tomb
        tomb_text = ''.join(lines[start_line:end_line])
        # Clean up HTML image tags and captions that split the text
        tomb_text_clean = re.sub(r'<div[^>]*>.*?</div>', ' ', tomb_text, flags=re.DOTALL)
        tomb_text_clean = re.sub(r'\s+', ' ', tomb_text_clean)
        # Use cleaned version for parsing, but keep original for artifact details
        
        # Get dynasty
        dynasty = get_dynasty(line_num)
        
        # Find the main description paragraph (starts with MXX位于, with optional space)
        # Use cleaned text to handle split descriptions
        # Handle "M50位于" or "M 50 位于" or "M50 位于"
        desc_match = re.search(r'(M\s*\d+\s*位于.+?图\s*[\d-]+[）\)])', tomb_text_clean, re.DOTALL)
        if not desc_match:
            # Try with newline breaks
            desc_match = re.search(r'(M\s*\d+\s*位于.+?(?:\n\n|\n<|\n##))', tomb_text, re.DOTALL)
        if not desc_match:
            # Try shorter match
            desc_match = re.search(r'(M\s*\d+\s*位于.+?图\s*[\d-]+[）\)])', tomb_text, re.DOTALL)
        
        if not desc_match:
            # Minimal entry
            tombs.append({
                "墓葬编号": tomb_id,
                "年代": dynasty,
                "墓向": "",
                "墓葬形制": "",
                "墓口长": None,
                "墓口宽": None,
                "墓深": None,
                "备注": "描述未找到",
                "随葬器物": []
            })
            continue
        
        desc = desc_match.group(1)
        
        # Extract fields - use cleaned text for tomb type to handle line breaks
        direction = extract_direction(desc)
        tomb_type = extract_tomb_type(tomb_text_clean)  # Use cleaned text
        dims = extract_dimensions(desc)
        
        # Check for special notes
        notes = []
        if '被盗' in desc or '盗扰' in desc:
            notes.append("盗扰")
        if '迁葬' in desc:
            notes.append("迁葬")
        if '合葬' in desc:
            notes.append("合葬")
        if '打破' in desc:
            notes.append("被打破")
        
        # Extract artifacts
        artifacts = extract_artifacts_from_desc(desc, tomb_id)
        
        # Also try to get detailed artifacts from the full tomb text
        detailed = extract_detailed_artifacts(tomb_text, tomb_id)
        if detailed and not artifacts:
            artifacts = detailed
        elif detailed:
            # Merge: use detailed descriptions where available
            detailed_dict = {a['器物名称']: a for a in detailed}
            for a in artifacts:
                if a['器物名称'] in detailed_dict:
                    d = detailed_dict[a['器物名称']]
                    if d['特征描述'] and not a['特征描述']:
                        a['特征描述'] = d['特征描述']
                    if d['器物编号'] and ':' in d['器物编号']:
                        a['器物编号'] = d['器物编号']
        
        tomb_entry = {
            "墓葬编号": tomb_id,
            "年代": dynasty,
            "墓向": direction,
            "墓葬形制": tomb_type,
            "墓口长": dims["墓口长"],
            "墓口宽": dims["墓口宽"],
            "墓深": dims["墓深"],
            "备注": "；".join(notes) if notes else "",
            "随葬器物": artifacts
        }
        
        tombs.append(tomb_entry)
        
        if idx < 5 or idx % 50 == 0:
            print(f"  [{idx+1}/{len(tomb_headers)}] {tomb_id} ({dynasty}) - {tomb_type} - {len(artifacts)} artifacts")
    
    return tombs

def export_json(tombs, output_path, report_name):
    """Export to JSON."""
    output = {
        "墓葬列表": tombs,
        "原始文本片段": f"来源：{report_name}，共提取{len(tombs)}座墓葬"
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  JSON: {output_path}")

def export_csv(tombs, output_path):
    """Export to CSV (one row per artifact, utf-8-sig for Excel)."""
    headers = [
        "墓葬编号", "年代", "墓向", "墓葬形制", "墓口长", "墓口宽", "墓深",
        "发掘位置", "层位", "备注",
        "器物编号", "器物名称", "材质", "器型", "数量", "特征描述"
    ]
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for tomb in tombs:
            base = [
                tomb.get('墓葬编号', ''), tomb.get('年代', ''),
                tomb.get('墓向', ''), tomb.get('墓葬形制', ''),
                tomb.get('墓口长', ''), tomb.get('墓口宽', ''),
                tomb.get('墓深', ''), tomb.get('发掘位置', ''),
                tomb.get('层位', ''), tomb.get('备注', '')
            ]
            artifacts = tomb.get('随葬器物', [])
            if artifacts:
                for art in artifacts:
                    row = base + [
                        art.get('器物编号', ''), art.get('器物名称', ''),
                        art.get('材质', ''), art.get('器型', ''),
                        art.get('数量', ''), art.get('特征描述', '')
                    ]
                    writer.writerow(row)
            else:
                writer.writerow(base + ['', '', '', '', '', ''])
    print(f"  CSV: {output_path}")

def export_markdown(tombs, output_path, report_name):
    """Export to Markdown."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# 墓葬数据 — {report_name}\n\n")
        f.write(f"共提取 **{len(tombs)}** 座墓葬\n\n")

        # Summary table
        f.write("## 概览\n\n")
        f.write("| 墓葬编号 | 年代 | 形制 | 尺寸(长×宽×深) | 随葬品数 |\n")
        f.write("|----------|------|------|----------------|----------|\n")
        for t in tombs:
            dim = ""
            if t.get('墓口长'):
                dim = f"{t['墓口长']}×{t.get('墓口宽','')}×{t.get('墓深','')}m"
            art_count = len(t.get('随葬器物', []))
            f.write(f"| {t['墓葬编号']} | {t.get('年代','')} | {t.get('墓葬形制','')} | {dim} | {art_count} |\n")
        f.write("\n")

        # Detail per tomb
        f.write("## 详细记录\n\n")
        for t in tombs:
            f.write(f"### {t['墓葬编号']}\n\n")
            fields = [
                ("年代", t.get('年代', '')),
                ("墓向", t.get('墓向', '')),
                ("墓葬形制", t.get('墓葬形制', '')),
                ("墓口长", t.get('墓口长', '')),
                ("墓口宽", t.get('墓口宽', '')),
                ("墓深", t.get('墓深', '')),
                ("发掘位置", t.get('发掘位置', '')),
                ("层位", t.get('层位', '')),
                ("备注", t.get('备注', '')),
            ]
            for label, val in fields:
                if val:
                    f.write(f"- **{label}**: {val}\n")

            artifacts = t.get('随葬器物', [])
            if artifacts:
                f.write(f"\n**随葬器物** ({len(artifacts)}件)\n\n")
                f.write("| 编号 | 名称 | 材质 | 器型 | 数量 | 特征描述 |\n")
                f.write("|------|------|------|------|------|----------|\n")
                for art in artifacts:
                    desc = art.get('特征描述', '')
                    if len(desc) > 80:
                        desc = desc[:80] + '...'
                    f.write(f"| {art.get('器物编号','')} | {art.get('器物名称','')} | "
                            f"{art.get('材质','')} | {art.get('器型','')} | "
                            f"{art.get('数量','')} | {desc} |\n")
            f.write("\n")
    print(f"  MD:   {output_path}")

def main():
    print("Parsing tomb report...")
    tombs = parse_file()

    # Sort by tomb number (handles prefixed IDs like YSTG4AM1)
    def tomb_sort_key(t):
        id_str = t['墓葬编号']
        m = re.search(r'(\d+)$', id_str)
        if m:
            prefix = re.sub(r'\d+$', '', id_str) or 'Z'
            return (prefix, int(m.group(1)))
        return (id_str, 0)

    tombs.sort(key=tomb_sort_key)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Export all three formats
    print(f"\nExporting {len(tombs)} tombs...")
    export_json(tombs, os.path.join(OUTPUT_DIR, "tombs.json"), REPORT_NAME)
    export_csv(tombs, os.path.join(OUTPUT_DIR, "tombs.csv"))
    export_markdown(tombs, os.path.join(OUTPUT_DIR, "tombs.md"), REPORT_NAME)

    # Summary
    dynasty_counts = {}
    for t in tombs:
        d = t.get('年代', '') or '未知'
        dynasty_counts[d] = dynasty_counts.get(d, 0) + 1
    print("\nBy dynasty:")
    for d, c in sorted(dynasty_counts.items()):
        print(f"  {d}: {c} tombs")

    total_artifacts = sum(len(t.get('随葬器物', [])) for t in tombs)
    print(f"\nTotal artifacts: {total_artifacts}")
    print(f"Output: {OUTPUT_DIR}/")

if __name__ == '__main__':
    main()
