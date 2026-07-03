# 考古文献解析 / Archaeological Tomb Parser

从中国考古报告中提取结构化墓葬数据。
Extract structured tomb data from Chinese archaeological reports.

**三种使用方式 / Three ways to use:**

| 方式 | 适合谁 | 语言 |
|------|--------|------|
| [MCP 服务器](#mcp-服务器) | AI 代理用户（Claude、Cursor、Kimi 等） | Python |
| [Obsidian 插件](#obsidian-插件) | 笔记软件用户 | TypeScript |
| [命令行/技能](#命令行技能) | 开发者、AI Agent 技能 | Python |

**输出格式 / Output formats**: JSON + CSV + Markdown

---

## MCP 服务器

让任何 AI 代理调用 `parse_tombs` 工具解析考古报告。

### 安装

```bash
cd mcp-server
uv pip install -r requirements.txt
```

### 运行

```bash
# stdio 模式（MCP 客户端使用）
uv run python -m archaeo_doc_parser.server

# HTTP 模式（远程访问）
uv run python -m archaeo_doc_parser.server --transport http --port 8000
```

### 客户端配置

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "archaeo-doc-parser": {
      "command": "uv",
      "args": ["run", "python", "-m", "archaeo_doc_parser.server"],
      "cwd": "/path/to/archaeo-tomb-parser/mcp-server"
    }
  }
}
```

**Cursor / Kimi Code**: 同上，指向 `uv run python -m archaeo_doc_parser.server`。

### 工具列表

| 工具 | 说明 | 免费 | Pro |
|------|------|------|-----|
| `parse_document` | PDF/图片 → Markdown | ✅ | ✅ |
| `parse_tombs` | .md/.txt → 结构化墓葬 JSON | ✅ | ✅ |
| `parse_batch` | 批量解析 | ❌ | ✅ |
| `get_task_status` | 任务状态查询 | ❌ | ✅ |
| `get_supported_formats` | 格式列表 | ✅ | ✅ |

> `parse_tombs` 不需要 API 密钥，纯本地解析。
> `MINERU_TOKEN` 仅用于 MinerU PDF→MD 功能（可选）。

### API 密钥（可选）

如需使用 MinerU PDF 解析功能，在配置中添加：
```json
{
  "env": {
    "MINERU_TOKEN": "your-token-here"
  }
}
```
获取地址: https://mineru.net → API管理

---

## Obsidian 插件

在 Obsidian 笔记中直接解析考古报告。

### 安装

```bash
cd obsidian-plugin
npm install
npm run build
# 将 main.js、manifest.json、styles.css 复制到:
# <你的vault>/.obsidian/plugins/archaeo-tombs/
```

然后在 Obsidian 设置 → 社区插件 中启用。

### 使用

1. 打开一个考古报告（`.md` 或 `.txt`）
2. `Ctrl/Cmd+P` → "Parse archaeological tombs"
3. 或在文件资源管理器中右键 → "Extract tomb data"
4. 输出到 `<文件名>_tombs/` 文件夹

### 设置

- **输出文件夹**: 留空则保存在源文件旁，或指定 vault 内路径
- **自动打开 Markdown**: 解析后自动打开概览笔记

---

## 命令行/技能

### 独立使用

```bash
# 直接运行示例
cd skill
python tomb_parser.py
```

### 作为 AI Agent 技能

将 `skill/` 目录复制到你的 agent 技能目录：
```bash
cp -r skill/ ~/.agents/skills/考古文献解析/
```

### Python 框架用法

```python
from tomb_parser import TombParser

p = TombParser("报告名", "/path/to/input.txt", "/path/to/output_dir")

# 搜索辅助
matches = p.grep(r'墓葬|M\d{1,3}')
contexts = p.grep_context(r'M\d+位于', after=5)

# 添加墓葬
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

p.export()  # 输出 tombs.json + tombs.csv + tombs.md
```

---

## 输出格式

### JSON
```json
{
  "墓葬列表": [
    {
      "墓葬编号": "YSTG4AM1",
      "年代": "宋代",
      "墓葬形制": "长方形土坑墓",
      "墓口长": null,
      "随葬器物": [
        {
          "器物编号": "YSTG4AM1:1",
          "器物名称": "青白釉罐",
          "材质": "瓷器",
          "器型": "罐",
          "数量": 1,
          "特征描述": "完整。直口，竖颈..."
        }
      ]
    }
  ]
}
```

### CSV
Excel 兼容（utf-8-sig 编码），每行一件随葬品，无随葬品的墓葬留空。

### Markdown
包含概览表格和每座墓葬的详细记录。

---

## 示例

`examples/yangzhou_tombs/` — 扬州城遗址考古发掘报告 1999~2013 年的解析结果。

- 6 条墓葬记录
- 4 件随葬品
- 涵盖：唐代墓、宋代墓、现代墓葬群、图表标注墓、外部参考墓

---

## 支持的墓葬 ID 格式

| 格式 | 示例 | 来源 |
|------|------|------|
| `M+数字` | M1, M32, M317 | 标准墓葬报告 |
| `前缀+M+数字` | YSTG4AM1, YSB0120T6BJ7M1 | 探方编号前缀 |
| 散文描述 | "宋墓。长方形土坑墓。" | 段落内嵌，无标题 |
| 仅图表标注 | M4 in 剖面图 | 仅见于图中 |
| 群组引用 | "现代墓葬41座" | 批量提及，无独立编号 |

---

## 项目结构

```
archaeo-tomb-parser/
├── mcp-server/              # MCP 服务器
│   ├── archaeo_doc_parser/  # Python 包
│   │   ├── server.py        # MCP 工具定义
│   │   ├── mineru.py        # MinerU API 客户端
│   │   └── tomb_parser.py   # 解析框架
│   ├── pyproject.toml
│   └── requirements.txt
├── obsidian-plugin/         # Obsidian 插件
│   ├── main.ts              # 插件入口
│   ├── tomb_parser.ts       # TypeScript 解析框架
│   ├── manifest.json
│   └── package.json
├── skill/                   # AI Agent 技能
│   ├── SKILL.md             # 工作流程文档
│   ├── tomb_parser.py       # Python 框架
│   └── template_parse_tombs.py
├── examples/                # 示例输出
│   └── yangzhou_tombs/
└── README.md
```

---

## 许可证 / License

MIT

---

## 贡献 / Contributing

欢迎提交 Issue 和 Pull Request！

如有问题，请在 GitHub Issues 中反馈。
