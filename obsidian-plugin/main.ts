/**
 * Archaeological Tomb Parser — Obsidian Plugin
 *
 * Parses Chinese archaeological reports (.md/.txt) in your vault
 * and exports structured tomb data as JSON, CSV, and Markdown.
 */

import { App, Notice, Plugin, PluginSettingTab, Setting, TFile, TFolder } from 'obsidian';
import { TombParser } from './tomb_parser';

interface ArchaeoTombsSettings {
	outputFolder: string; // '' = sibling to source file
	autoOpenMarkdown: boolean;
}

const DEFAULT_SETTINGS: ArchaeoTombsSettings = {
	outputFolder: '',
	autoOpenMarkdown: true,
};

export default class ArchaeoTombsPlugin extends Plugin {
	settings: ArchaeoTombsSettings;

	async onload() {
		await this.loadSettings();

		// Command: parse the currently active file
		this.addCommand({
			id: 'parse-current-file',
			name: 'Parse archaeological tombs (current file)',
			checkCallback: (checking) => {
				const file = this.app.workspace.getActiveFile();
				if (file && (file.extension === 'md' || file.extension === 'txt')) {
					if (!checking) this.parseFile(file);
					return true;
				}
				return false;
			},
		});

		// Right-click menu on files in the file explorer
		this.registerEvent(
			this.app.workspace.on('file-menu', (menu, file) => {
				if (file instanceof TFile && (file.extension === 'md' || file.extension === 'txt')) {
					menu.addItem((item) => {
						item
							.setTitle('Extract tomb data')
							.setIcon('pickaxe')
							.onClick(() => this.parseFile(file));
					});
				}
			}),
		);

		// Settings tab
		this.addSettingTab(new ArchaeoTombsSettingTab(this.app, this));

		// Status bar
		this.addStatusBarItem().setText('');
	}

	onunload() {}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	/**
	 * Parse a file and export tomb data to the vault.
	 */
	async parseFile(file: TFile) {
		new Notice('Parsing tomb data...');

		try {
			const content = await this.app.vault.read(file);
			const parser = new TombParser(file.basename, content);

			// Try auto-extraction for standard M+number headers
			const count = parser.autoExtract();

			if (count === 0) {
				new Notice(
					'No tomb headers (M+number) found with auto-extraction.\n' +
					'Use the MCP server or CLI for custom report formats.',
					8000,
				);
				return;
			}

			// Determine output folder
			let outputFolder: TFolder;
			const folderName = `${file.basename}_tombs`;

			if (this.settings.outputFolder) {
				// Use configured output folder
				const base = this.app.vault.getAbstractFileByPath(this.settings.outputFolder);
				if (base instanceof TFolder) {
					outputFolder = await this.ensureSubfolder(base, folderName);
				} else {
					// Create the configured folder first
					await this.app.vault.createFolder(this.settings.outputFolder);
					const created = this.app.vault.getAbstractFileByPath(this.settings.outputFolder);
					outputFolder = await this.ensureSubfolder(created as TFolder, folderName);
				}
			} else {
				// Sibling to the source file
				const parent = file.parent;
				if (parent) {
					outputFolder = await this.ensureSubfolder(parent, folderName);
				} else {
					outputFolder = await this.ensureSubfolder(
						this.app.vault.getRoot(),
						folderName,
					);
				}
			}

			const basePath = outputFolder.path;

			// Write JSON
			const json = JSON.stringify(parser.toJSON(), null, 2);
			await this.app.vault.create(`${basePath}/tombs.json`, json);

			// Write CSV (with BOM for Excel compatibility)
			const bom = '\uFEFF';
			const csv = bom + parser.toCSV();
			await this.app.vault.create(`${basePath}/tombs.csv`, csv);

			// Write Markdown
			const md = parser.toMarkdown();
			const mdFile = await this.app.vault.create(`${basePath}/tombs.md`, md);

			// Open the Markdown overview
			if (this.settings.autoOpenMarkdown && mdFile) {
				await this.app.workspace.getLeaf(true).openFile(mdFile);
			}

			new Notice(`Parsed ${count} tombs → ${basePath}/`);

			// Update status bar
			const statusBarEl = this.statusBarEl;
			if (statusBarEl) {
				statusBarEl.setText(` tombs: ${count}`);
			}
		} catch (err) {
			console.error('Tomb parser error:', err);
			new Notice(`Error: ${err instanceof Error ? err.message : String(err)}`);
		}
	}

	private async ensureSubfolder(parent: TFolder, name: string): Promise<TFolder> {
		const existing = parent.children.find(
			(f) => f instanceof TFolder && f.name === name,
		);
		if (existing instanceof TFolder) return existing;

		const path = parent.path ? `${parent.path}/${name}` : name;
		await this.app.vault.createFolder(path);
		const created = this.app.vault.getAbstractFileByPath(path);
		if (created instanceof TFolder) return created;
		throw new Error(`Failed to create folder: ${path}`);
	}
}

class ArchaeoTombsSettingTab extends PluginSettingTab {
	plugin: ArchaeoTombsPlugin;

	constructor(app: App, plugin: ArchaeoTombsPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl('h2', { text: 'Archaeological Tomb Parser' });

		new Setting(containerEl)
			.setName('Output folder')
			.setDesc(
				'Where to save parsed tomb data. Leave empty to save next to the source file.',
			)
			.addText((text) =>
				text
					.setPlaceholder('e.g. tomb-data')
					.setValue(this.plugin.settings.outputFolder)
					.onChange(async (value) => {
						this.plugin.settings.outputFolder = value.trim();
						await this.plugin.saveSettings();
					}),
			);

		new Setting(containerEl)
			.setName('Auto-open Markdown')
			.setDesc('Open the tomb overview note after parsing.')
			.addToggle((toggle) =>
				toggle
					.setValue(this.plugin.settings.autoOpenMarkdown)
					.onChange(async (value) => {
						this.plugin.settings.autoOpenMarkdown = value;
						await this.plugin.saveSettings();
					}),
			);
	}
}
