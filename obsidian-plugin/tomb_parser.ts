/**
 * tomb_parser.ts — Reusable tomb data parser for Chinese archaeological reports.
 * TypeScript port of the Python tomb_parser.py framework.
 */

export interface Artifact {
	器物编号: string;
	器物名称: string;
	材质: string;
	器型: string;
	数量: number;
	特征描述: string;
}

export interface Tomb {
	墓葬编号: string;
	年代: string;
	墓向: string;
	墓葬形制: string;
	墓口长: number | null;
	墓口宽: number | null;
	墓深: number | null;
	发掘位置: string;
	层位: string;
	备注: string;
	随葬器物: Artifact[];
	[key: string]: unknown; // allow extra fields like 分布区域
}

export interface ParseResult {
	墓葬列表: Tomb[];
	原始文本片段: string;
}

// ── Classification ──────────────────────────────────────────────

export function classifyMaterial(name: string): string {
	const rules: [string[], string][] = [
		[['陶', '泥质', '灰陶', '红陶'], '陶器'],
		[['瓷', '白胎', '青花', '釉', '窑'], '瓷器'],
		[['铜', '青铜'], '青铜器'],
		[['铁'], '铁器'],
		[['玉', '石', '玛瑙', '绿松石', '翡翠'], '玉石器'],
		[['骨', '角', '牙'], '骨角牙器'],
		[['漆', '木'], '漆木器'],
		[['金', '银'], '金银器'],
		[['钱', '币', '铢', '宝', '贝'], '货币'],
		[['料', '琉璃', '玻璃'], '料器'],
	];
	for (const [keywords, material] of rules) {
		if (keywords.some(k => name.includes(k))) return material;
	}
	return '其他';
}

export function classifyVesselType(name: string): string {
	const types: Record<string, string> = {
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
	};
	for (const [key, val] of Object.entries(types)) {
		if (name.includes(key)) return val;
	}
	return name;
}

// ── Extraction helpers ──────────────────────────────────────────

export function parseNum(s: string | null | undefined): number | null {
	if (!s) return null;
	s = s.trim();
	if (s.includes('~')) {
		const parts = s.split('~');
		try {
			return Math.round(((parseFloat(parts[0]) + parseFloat(parts[1])) / 2) * 100) / 100;
		} catch { return null; }
	}
	const n = parseFloat(s);
	return isNaN(n) ? null : n;
}

export function extractDirection(text: string): string {
	const patterns = [
		/方向\s*\$?\s*(\d+)\s*\^?\{?\\?circ\}?\s*\$?°?/,
		/方向\s*(\d+)°/,
		/方向\s*(南北向|东西向|南向|北向|东向|西向)/,
	];
	for (const pat of patterns) {
		const m = text.match(pat);
		if (m) {
			return /^\d+$/.test(m[1]) ? `${m[1]}°` : m[1];
		}
	}
	return '';
}

export function extractDimensions(text: string): { 墓口长: number | null; 墓口宽: number | null; 墓深: number | null } {
	const result = { 墓口长: null as number | null, 墓口宽: null as number | null, 墓深: null as number | null };
	const m = text.match(/(?:南北)?长\s*([\d.]+)\s*[、，]\s*(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)\s*[、，]\s*(?:残)?深\s*([\d.]+(?:~[\d.]+)?)/);
	if (m) {
		result.墓口长 = parseNum(m[1]);
		result.墓口宽 = parseNum(m[2]);
		result.墓深 = parseNum(m[3]);
	}
	return result;
}

// ── TombParser class ────────────────────────────────────────────

export class TombParser {
	reportName: string;
	text: string;
	lines: string[];
	tombs: Tomb[] = [];
	sourceNote = '';

	constructor(reportName: string, text: string) {
		this.reportName = reportName;
		this.text = text;
		this.lines = text.split('\n');
	}

	addTomb(tomb: Partial<Tomb>): void {
		const defaults: Tomb = {
			墓葬编号: '', 年代: '', 墓向: '', 墓葬形制: '',
			墓口长: null, 墓口宽: null, 墓深: null,
			发掘位置: '', 层位: '', 备注: '', 随葬器物: [],
		};
		const entry: Tomb = { ...defaults, ...tomb };
		entry.随葬器物 = (entry.随葬器物 || []).map(a => {
			const defaults: Artifact = { 器物编号: '', 器物名称: '', 材质: '', 器型: '', 数量: 1, 特征描述: '' };
			return { ...defaults, ...a };
		});
		this.tombs.push(entry);
	}

	grep(pattern: RegExp): Array<[number, string]> {
		const results: Array<[number, string]> = [];
		for (let i = 0; i < this.lines.length; i++) {
			if (pattern.test(this.lines[i])) {
				results.push([i + 1, this.lines[i]]);
			}
		}
		return results;
	}

	grepContext(pattern: RegExp, before = 3, after = 10): string[] {
		const matches: string[] = [];
		for (let i = 0; i < this.lines.length; i++) {
			if (pattern.test(this.lines[i])) {
				const start = Math.max(0, i - before);
				const end = Math.min(this.lines.length, i + after + 1);
				matches.push(this.lines.slice(start, end).join('\n'));
			}
		}
		return matches;
	}

	getSection(startLine: number, endLine: number): string {
		return this.lines.slice(startLine - 1, endLine).join('\n');
	}

	sortTombs(): void {
		this.tombs.sort((a, b) => {
			const mA = a.墓葬编号.match(/(\d+)$/);
			const mB = b.墓葬编号.match(/(\d+)$/);
			if (mA && mB) {
				const prefixA = a.墓葬编号.replace(/\d+$/, '') || 'Z';
				const prefixB = b.墓葬编号.replace(/\d+$/, '') || 'Z';
				if (prefixA !== prefixB) return prefixA.localeCompare(prefixB);
				return parseInt(mA[1]) - parseInt(mB[1]);
			}
			return a.墓葬编号.localeCompare(b.墓葬编号);
		});
	}

	toJSON(): ParseResult {
		this.sortTombs();
		return {
			墓葬列表: this.tombs,
			原始文本片段: this.sourceNote || `来源：${this.reportName}，共提取${this.tombs.length}座墓葬`,
		};
	}

	toCSV(): string {
		this.sortTombs();
		const headers = [
			'墓葬编号', '年代', '墓向', '墓葬形制', '墓口长', '墓口宽', '墓深',
			'发掘位置', '层位', '备注', '器物编号', '器物名称', '材质', '器型', '数量', '特征描述',
		];
		const rows: string[] = [headers.join(',')];

		for (const t of this.tombs) {
			const base = [
				t.墓葬编号, t.年代, t.墓向, t.墓葬形制,
				t.墓口长 ?? '', t.墓口宽 ?? '', t.墓深 ?? '',
				t.发掘位置, t.层位, t.备注,
			].map(v => csvEscape(String(v ?? '')));

			if (t.随葬器物.length > 0) {
				for (const a of t.随葬器物) {
					const art = [a.器物编号, a.器物名称, a.材质, a.器型, a.数量, a.特征描述]
						.map(v => csvEscape(String(v ?? '')));
					rows.push([...base, ...art].join(','));
				}
			} else {
				rows.push([...base, '', '', '', '', '', ''].join(','));
			}
		}
		return rows.join('\n');
	}

	toMarkdown(): string {
		this.sortTombs();
		const lines: string[] = [];
		lines.push(`# 墓葬数据 — ${this.reportName}\n`);
		lines.push(`共提取 **${this.tombs.length}** 条墓葬记录\n`);

		lines.push('## 概览\n');
		lines.push('| 墓葬编号 | 年代 | 形制 | 尺寸(长×宽×深) | 随葬品数 |');
		lines.push('|----------|------|------|----------------|----------|');
		for (const t of this.tombs) {
			const dim = t.墓口长 ? `${t.墓口长}×${t.墓口宽 ?? ''}×${t.墓深 ?? ''}m` : '';
			lines.push(`| ${t.墓葬编号} | ${t.年代} | ${t.墓葬形制} | ${dim} | ${t.随葬器物.length} |`);
		}
		lines.push('');

		lines.push('## 详细记录\n');
		for (const t of this.tombs) {
			lines.push(`### ${t.墓葬编号}\n`);
			for (const label of ['年代', '墓向', '墓葬形制', '墓口长', '墓口宽', '墓深', '发掘位置', '层位', '备注'] as const) {
				const val = t[label];
				if (val) lines.push(`- **${label}**: ${val}`);
			}
			if (t.随葬器物.length > 0) {
				lines.push(`\n**随葬器物** (${t.随葬器物.length}件)\n`);
				lines.push('| 编号 | 名称 | 材质 | 器型 | 数量 | 特征描述 |');
				lines.push('|------|------|------|------|------|----------|');
				for (const a of t.随葬器物) {
					const desc = a.特征描述.length > 80 ? a.特征描述.slice(0, 80) + '...' : a.特征描述;
					lines.push(`| ${a.器物编号} | ${a.器物名称} | ${a.材质} | ${a.器型} | ${a.数量} | ${desc} |`);
				}
			}
			lines.push('');
		}
		return lines.join('\n');
	}

	/**
	 * Auto-extract tombs from standard M+number header format.
	 * For custom formats, use addTomb() directly.
	 */
	autoExtract(): number {
		const tombHeaders: Array<[number, string]> = [];
		for (let i = 0; i < this.lines.length; i++) {
			const m = this.lines[i].match(/^#{1,3}\s*(?:[一二三四五六七八九十百千]+、\s*)?(M\s*\d+)\b/);
			if (m) {
				tombHeaders.push([i + 1, m[1].replace(/\s/g, '')]);
			}
		}

		for (let idx = 0; idx < tombHeaders.length; idx++) {
			const [lineNum, tombId] = tombHeaders[idx];
			const start = lineNum - 1;
			const end = idx + 1 < tombHeaders.length ? tombHeaders[idx + 1][0] - 1 : this.lines.length;
			const block = this.lines.slice(start, end).join('\n');
			const blockClean = block.replace(/<div[^>]*>.*?<\/div>/gs, ' ').replace(/\s+/g, ' ');

			let tombType = '';
			for (const t of ['土坑竖穴砖椁墓', '土坑竖穴墓', '土坑洞室墓', '砖室墓', '石室墓', '长方形土坑墓']) {
				if (blockClean.replace(/\s/g, '').includes(t)) { tombType = t; break; }
			}

			this.addTomb({
				墓葬编号: tombId,
				墓葬形制: tombType,
				...extractDimensions(blockClean),
			});
		}
		return this.tombs.length;
	}
}

// ── Utils ───────────────────────────────────────────────────────

function csvEscape(s: string): string {
	if (s.includes(',') || s.includes('"') || s.includes('\n')) {
		return '"' + s.replace(/"/g, '""') + '"';
	}
	return s;
}
