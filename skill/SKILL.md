# 考古文献解析 Skill

Parse Chinese archaeological reports into structured JSON tomb data.

## When to Use

- User provides a `.md` or `.txt` file from an archaeological report
- User wants to extract tomb (墓葬) information
- Report may contain tomb descriptions in various formats (M+number, prefixed IDs, prose, diagrams)
- Need structured JSON output for database import or analysis

## Prerequisites - IMPORTANT

**This skill accepts markdown (.md) or text (.txt) files as input.**

Before starting, verify the user has provided:
1. A path to a markdown or text file (`.md` or `.txt` extension)
2. The file exists and is readable

If the user provides a PDF or other format, remind them:
> "这个技能需要markdown或txt格式的文件。请先将PDF转换为markdown或txt，然后再运行此技能。"

## Workflow

### Step 0: Verify Input

Check that the user has provided a file path. If not, ask:
- "请提供考古报告的markdown或txt文件路径"

### Step 1: Analyze the Document (CRITICAL - do this FIRST)

**Do NOT blindly run the template.** Every report is different. Analyze structure first:

1. Read the file header/intro to identify:
   - What kind of report (墓葬发掘报告? 城址报告? 遗址报告?)
   - What time periods are covered
   - What excavation areas exist (探方编号)

2. Search for ALL tomb-related patterns, not just the template's expected format:
   ```bash
   # Standard M+number IDs
   grep -n 'M[0-9]' <file>
   # Tomb descriptions in prose
   grep -n '墓' <file> | grep -v '图\|表\|目录'
   # Prefixed tomb IDs (e.g., YSTG4AM1, YSB0120T6BM3)
   grep -nE '[A-Z]+M[0-9]' <file>
   # Diagram-only references
   grep -n '墓坑\|墓穴\|墓室\|墓砖' <file>
   ```

3. Classify the report type:
   - **Tomb-focused report**: Has structured tomb sections with M+number headers → use template directly
   - **Site report with tombs**: Tombs are incidental (城址, 遗址 reports) → write custom parser
   - **Mixed report**: Some structured sections + some incidental mentions → hybrid approach

4. Count what you found and tell the user before proceeding.

### Step 2: Identify Dynasty Context

Search for chapter headers or textual dynasty references:
```bash
grep -n '第[二三四五六七八九十]*章\|汉代\|唐代\|宋代\|元代\|明代\|清代\|南朝\|隋' <file>
```

Dynasty mapping (adapt to your report):
- 第二章 → 汉代 (common, but verify)
- 第三章 → 唐代
- 第四章 → 宋代
- Text mentions like "宋墓"、"唐墓" within tomb descriptions are authoritative

### Step 3: Write or Adapt the Parser

**Use `tomb_parser.py` as your base framework.** It provides:
- `TombParser` class with built-in `export()` (writes JSON + CSV + MD)
- Utility methods: `grep()`, `grep_context()`, `get_section()`
- Classification: `classify_material()`, `classify_vessel_type()`
- Extraction: `extract_direction()`, `extract_dimensions()`, `parse_num()`
- `add_tomb()` / `add_tombs()` for building the dataset

**If the report matches the template format** (M+number headers, `M\d+位于` descriptions):
- Use `template_parse_tombs.py` as-is, just update `INPUT_FILE`, `OUTPUT_DIR`, `DYNASTY_RANGES`

**If the report has a different structure** (most cases):
- Import `TombParser`, write a custom extraction script. Include ALL tombs found.

#### Tomb ID Formats to Handle

| Pattern | Example | Where Found |
|---------|---------|-------------|
| `M\d+` | M1, M32, M317 | Standard tomb reports |
| `[A-Z]+M\d+` | YSTG4AM1, YSB0120T6BJ7M1 | Prefixed by excavation unit |
| Prose description | "宋墓。长方形土坑墓。" | Embedded in paragraph, no header |
| Diagram label only | M4 in 剖面图 | Only in figure, no text |
| Group reference | "现代墓葬41座" | Bulk mention, no individual IDs |

#### What to Include (ALL of these)

1. **Fully described tombs** — has ID, type, dimensions, artifacts
2. **Minimally described tombs** — has ID but no details (note "报告中未提供详细描述")
3. **Diagram-only tombs** — appears in figure labels only (note "仅见于剖面图标注")
4. **Modern/recent tomb groups** — create a single group entry with `分布区域` array
5. **External references** — tombs from other excavations mentioned in passing (note "非本报告主持发掘")

### Step 4: Handle Common Issues

**Text split by images**: PDF-to-markdown often inserts `<div>` image tags mid-sentence:
- `re.sub(r'<div[^>]*>.*?</div>', ' ', text, flags=re.DOTALL)`
- `re.sub(r'\s+', ' ', text)`

**Spaces in tomb IDs**: OCR outputs "M 50" instead of "M50":
- `M\s*\d+` pattern
- `.replace(' ', '')` for normalization

**Line breaks in type names**: "土坑\n竖穴墓" → "土坑 竖穴墓":
- `text.replace(' ', '')` before matching

**Prefixed IDs**: "YSTG4AM1" — the prefix is the excavation unit:
- Regex: `[A-Z]+M(\d+)` to extract, keep full ID as `墓葬编号`

**Unicode issues in descriptions**: OCR may produce `□` or special chars:
- Use unicode escapes in Python strings, or raw string handling

### Step 5: Export (ALL THREE FORMATS)

The parser must export to **JSON, Markdown, and CSV**. Save all three to the same directory:

```bash
mkdir -p ~/Desktop/<report_name>/
```

**JSON** — for database import and programmatic use:
```python
with open(f"{dir}/tombs.json", 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
```

**Markdown** — for human reading and documentation:
```python
with open(f"{dir}/tombs.md", 'w', encoding='utf-8') as f:
    f.write(f"# 墓葬数据 - {report_name}\n\n")
    f.write(f"来源：{source}\n\n")
    for tomb in tombs:
        f.write(f"## {tomb['墓葬编号']}（{tomb['年代']}）\n\n")
        # write fields as table or list
        # write artifacts as sub-table
```

**CSV** — for spreadsheet import (flat structure, one row per artifact):
```python
import csv
with open(f"{dir}/tombs.csv", 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["墓葬编号","年代","墓向","墓葬形制","墓口长","墓口宽","墓深",
                      "发掘位置","层位","备注","器物编号","器物名称","材质","器型","数量","特征描述"])
    for tomb in tombs:
        if tomb['随葬器物']:
            for art in tomb['随葬器物']:
                writer.writerow([tomb['墓葬编号'], tomb['年代'], ...art fields])
        else:
            writer.writerow([tomb['墓葬编号'], tomb['年代'], ...empty art fields])
```

Use `utf-8-sig` encoding for CSV so Excel opens Chinese characters correctly.

## Output Format

```json
{
  "墓葬列表": [
    {
      "墓葬编号": "M32",
      "年代": "汉代",
      "墓向": "8°",
      "墓葬形制": "土坑竖穴墓",
      "墓口长": 3.1,
      "墓口宽": 2.16,
      "墓深": 1.9,
      "发掘位置": "YSTG4A",
      "层位": "开口于第2层下",
      "备注": "",
      "随葬器物": [
        {
          "器物编号": "M32:1",
          "器物名称": "陶壶",
          "材质": "陶器",
          "器型": "壶",
          "数量": 2,
          "特征描述": "泥质灰陶。盘口，束颈较长..."
        }
      ]
    }
  ],
  "原始文本片段": "来源：XXX考古报告，共提取N座墓葬"
}
```

### Group Entry Format (for modern/relocated tomb groups)

```json
{
  "墓葬编号": "现代墓葬群",
  "年代": "近现代",
  "备注": "报告记载共发现N座墓葬，多为近现代已迁葬...",
  "分布区域": [
    {
      "位置": "YSTG2（城圈西北外拐角）",
      "数量标注": "图中标注约6处现代墓坑",
      "备注": "叠压或打破夯土层"
    }
  ],
  "随葬器物": []
}
```

## Material Classification

| Name Keywords | Material |
|---------------|----------|
| 陶, 泥质 | 陶器 |
| 瓷, 白胎, 青花, 釉 | 瓷器 |
| 铜, 青铜 | 青铜器 |
| 铁 | 铁器 |
| 玉, 石, 玛瑙 | 玉石器 |
| 骨, 角, 牙 | 骨角牙器 |
| 金, 银 | 金银器 |
| 钱, 币, 铢, 宝 | 货币 |

## Quality Metrics

These apply to **tomb-focused reports only**. For site reports with incidental tombs, skip these:
- Tombs with type: target >95%
- Tombs with direction: target >95%
- Tombs with dimensions: target >95%
- Tombs with artifacts: target >80%

For site reports, the goal is **completeness** — capture every tomb reference regardless of detail level.

## Files

- `SKILL.md` - this file
- `tomb_parser.py` - reusable framework (`TombParser` class with tri-format export)
- `template_parse_tombs.py` - legacy template for standard M+number tomb reports

## Quick Start (custom parser)

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.agents/skills/考古文献解析"))
from tomb_parser import TombParser

p = TombParser("报告名", "/path/to/input.txt", "/path/to/output_dir")

# Use built-in search helpers to find tombs
matches = p.grep(r'墓葬|M\d{1,3}')
contexts = p.grep_context(r'M\d+位于', after=5)

# Add tombs you extracted
p.add_tomb({
    "墓葬编号": "M1", "年代": "汉代", "墓葬形制": "土坑竖穴墓",
    "墓口长": 3.1, "墓口宽": 2.16, "墓深": 1.9,
    "随葬器物": [{
        "器物编号": "M1:1", "器物名称": "陶壶",
        "材质": "陶器", "器型": "壶", "数量": 2,
        "特征描述": "泥质灰陶。盘口，束颈。"
    }]
})

p.export()  # writes tombs.json + tombs.csv + tombs.md
```
