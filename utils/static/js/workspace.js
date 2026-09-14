"use strict";

(() => {
    const media = new Map();

    class MaintenanceWorkspace {
        constructor(root) {
            this.root = root;
            this.standalone = root.dataset.workspaceStandalone !== undefined;
            this.active = null;
            this.status = root.querySelector("[data-workspace-status]");
            root.addEventListener("click", (event) => this.onClick(event));
            root.addEventListener("submit", (event) => {
                if (!this.standalone && this.active && event.target === this.active.form) {
                    event.preventDefault();
                    this.save();
                }
            });
            for (const type of ["input", "change"]) {
                root.addEventListener(type, (event) => {
                    if (this.active?.form?.contains(event.target) && !this.active.busy) {
                        this.active.dirty = true;
                        this.announce("Unsaved changes in this section.");
                    }
                });
            }
            root.addEventListener("keydown", (event) => {
                if (!this.standalone && event.key === "Escape" && !event.defaultPrevented && this.active?.editor.contains(event.target)) {
                    if (Array.from(this.active.editor.querySelectorAll("select")).some((select) => select.tomselect?.isOpen)) return;
                    event.preventDefault();
                    this.cancel();
                }
            });
            window.addEventListener("beforeunload", (event) => {
                if (this.active?.dirty) {
                    event.preventDefault();
                    event.returnValue = "";
                }
            });
        }

        announce(message, error = false) {
            const local = this.active?.editor.querySelector("[data-workspace-local-status]");
            for (const status of [this.status, local]) {
                if (!status) continue;
                status.textContent = message;
                status.className = error ? "alert alert-danger" : "small text-muted mb-3";
            }
        }

        onClick(event) {
            const link = event.target.closest("[data-workspace-edit]");
            if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && (!event.button || event.button === 0)) {
                event.preventDefault();
                this.open(link);
                return;
            }
            if (!this.standalone && event.target.closest("[data-workspace-cancel]") && this.active) {
                event.preventDefault();
                this.cancel();
            }
            const add = event.target.closest("[data-workspace-add]");
            if (add && this.active && !this.active.busy) {
                event.preventDefault();
                this.addRow(add.closest("[data-workspace-formset]"));
            }
            const paste = event.target.closest("[data-workspace-paste-apply]");
            if (paste && this.active && !this.active.busy) {
                event.preventDefault();
                this.applyPaste(paste.closest("[data-workspace-paste]"));
            }
        }

        async request(url, options, section) {
            const target = new URL(url, window.location.href);
            if (target.origin !== window.location.origin) throw new Error("Unexpected section origin");
            const response = await fetch(url, {
                credentials: "same-origin",
                ...options,
                headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
            });
            if ((!response.ok && response.status !== 422) || response.redirected) throw new Error("Section request failed");
            const data = await response.json();
            if (data.section !== section || typeof data.html !== "string" || typeof data.saved !== "boolean") throw new Error("Unexpected section response");
            if (response.status === 422 && data.saved) throw new Error("Unexpected save response");
            return data;
        }

        async open(link) {
            if (this.active?.busy) return;
            if (this.active && (this.active.link === link || this.active.key === link.dataset.workspaceEdit)) {
                this.active.focusName = link.dataset.workspaceFocus;
                this.focusEditor(this.active);
                return;
            }
            if (this.active && !this.cancel()) return;
            const card = link.closest("[data-workspace-section]") || this.root.querySelector(`[data-workspace-section="${link.dataset.workspaceEdit}"]`);
            if (!card) return;
            const active = {
                card, link, key: card.dataset.workspaceSection, focusName: link.dataset.workspaceFocus,
                summary: card.querySelector("[data-workspace-summary]"),
                editor: card.querySelector("[data-workspace-editor]"),
                dirty: false, busy: true,
            };
            this.active = active;
            card.setAttribute("aria-busy", "true");
            this.announce("Loading section editor…");
            try {
                const data = await this.request(link.href, { method: "GET" }, active.key);
                if (data.saved) throw new Error("Expected editor");
                await this.mountEditor(active, data.html);
                active.summary.hidden = true;
                active.editor.hidden = false;
                this.setExpanded(active, true);
                this.announce("Edit this section, then save or cancel. Other sections are unchanged.");
                this.focusEditor(active);
            } catch (error) {
                this.close(active);
                this.announce("Could not open the editor. Try again, or use the full-page editor link below the section heading.", true);
                link.focus();
            } finally {
                active.busy = false;
                card.removeAttribute("aria-busy");
            }
        }

        fragment(html) {
            const template = document.createElement("template");
            template.innerHTML = html;
            return template.content;
        }

        trustedMediaURL(value, kind) {
            const base = new URL(this.root.dataset.staticUrl, window.location.href);
            const url = new URL(value, window.location.href);
            const extension = kind === "script" ? ".js" : ".css";
            if (!/^https?:$/.test(url.protocol) || url.origin !== base.origin || !url.pathname.startsWith(`${base.pathname}django_tomselect/`) || !url.pathname.endsWith(extension) || url.search || url.hash) {
                throw new Error("Untrusted editor media");
            }
            return url;
        }

        loadAsset(element, kind) {
            const url = this.trustedMediaURL(element.getAttribute(kind === "script" ? "src" : "href"), kind);
            if (media.has(url.href)) return media.get(url.href);
            const existing = Array.from(document.querySelectorAll(kind === "script" ? "script[src]" : 'link[rel="stylesheet"]')).find((node) => (kind === "script" ? node.src : node.href) === url.href);
            if (existing) return Promise.resolve();
            const promise = new Promise((resolve, reject) => {
                const node = document.createElement(kind === "script" ? "script" : "link");
                if (kind === "script") {
                    node.src = url.href;
                    node.async = false;
                } else {
                    node.rel = "stylesheet";
                    node.href = url.href;
                }
                node.onload = resolve;
                node.onerror = () => {
                    node.remove();
                    media.delete(url.href);
                    reject(new Error("Editor asset unavailable"));
                };
                document.head.appendChild(node);
            });
            media.set(url.href, promise);
            return promise;
        }

        async loadMedia(fragment) {
            if (!fragment.querySelector("select[data-workspace-select]")) return;
            for (const template of fragment.querySelectorAll("template[data-workspace-media]")) {
                await Promise.all(Array.from(template.content.querySelectorAll('link[rel="stylesheet"]'), (link) => this.loadAsset(link, "style")));
                for (const script of template.content.querySelectorAll("script[src]")) await this.loadAsset(script, "script");
                template.remove();
            }
        }

        stripScripts(fragment) {
            fragment.querySelectorAll("script").forEach((script) => script.remove());
            fragment.querySelectorAll("template").forEach((template) => {
                if (template.dataset.workspaceMedia === undefined) this.stripScripts(template.content);
            });
        }

        initializeWidgets(container) {
            for (const field of container.querySelectorAll("input, select, textarea")) {
                if (field.type === "hidden") continue;
                field.classList.add(field.type === "checkbox" ? "form-check-input" : field.tagName === "SELECT" ? "form-select" : "form-control");
                if (field.id && field.closest("[data-workspace-field]")) {
                    field.setAttribute("aria-describedby", `${field.id}_helptext ${field.id}_errors`);
                }
            }
            for (const select of container.querySelectorAll("select[data-workspace-select]")) {
                if (select.tomselect) continue;
                if (!window.TomSelect) throw new Error("Select editor unavailable");
                new window.TomSelect(select, this.autocompleteSettings(select));
            }
        }

        autocompleteSettings(select) {
            const workspace = this;
            const valueField = select.dataset.valueField || "id";
            const labelField = select.dataset.labelField === "label" ? "label" : "name";
            return {
                valueField,
                labelField,
                searchField: [labelField],
                create: false,
                loadThrottle: 300,
                preload: false,
                openOnFocus: true,
                maxOptions: 15,
                placeholder: "Type to search…",
                plugins: select.multiple ? ["remove_button"] : ["clear_button"],
                shouldLoad: (query) => query.trim().length > 0,
                render: {
                    option: (data, escape) => `<div>${escape(data[labelField])}</div>`,
                    item: (data, escape) => `<div>${escape(data[labelField])}</div>`,
                    not_loading: () => '<div class="no-results">Type to search for an existing entry.</div>',
                },
                async load(query, callback) {
                    if (!query.trim()) {
                        callback([]);
                        return;
                    }
                    try {
                        callback(await workspace.searchOptions(select, query));
                    } catch (error) {
                        if (this.loadedSearches) delete this.loadedSearches[query];
                        callback([]);
                        const label = select.labels?.[0]?.textContent.trim() || "this field";
                        if (select.isConnected !== false) workspace.announce(`Could not search ${label}. Existing selections have been kept. Check your connection and try again.`, true);
                    }
                },
            };
        }

        async searchOptions(select, query) {
            const valueField = select.dataset.valueField || "id";
            const labelField = select.dataset.labelField === "label" ? "label" : "name";
            const url = new URL(select.dataset.autocompleteUrl, window.location.href);
            if (!select.dataset.autocompleteUrl || url.origin !== window.location.origin || !/^https?:$/.test(url.protocol) || url.username || url.password) throw new Error("Untrusted autocomplete endpoint");
            url.searchParams.set("q", query);
            url.searchParams.set("page", "1");
            const response = await fetch(url.href, {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!response.ok || response.redirected) throw new Error("Search request failed");
            const data = await response.json();
            if (!Array.isArray(data.results)) throw new Error("Unexpected search response");
            return data.results.filter((result) => result &&
                (typeof result[valueField] === "string" || Number.isFinite(result[valueField])) &&
                String(result[valueField]) !== "" && typeof result[labelField] === "string"
            ).slice(0, 15).map((result) => ({
                [valueField]: String(result[valueField]),
                [labelField]: result[labelField],
            }));
        }

        async mountEditor(active, html) {
            const fragment = this.fragment(html);
            await this.loadMedia(fragment);
            this.stripScripts(fragment);
            active.editor.replaceChildren(fragment);
            active.form = active.editor.querySelector("form[data-workspace-section-form]");
            if (!active.form) throw new Error("Missing section form");
            this.initializeWidgets(active.editor);
        }

        focusEditor(active) {
            const field = (active.focusName && active.form?.elements?.namedItem(active.focusName)) || active.editor.querySelector('input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])');
            if (field?.tomselect) field.tomselect.focus();
            else if (field) field.focus();
            else active.editor.querySelector("[data-workspace-form-title]")?.focus();
        }

        setBusy(active, busy) {
            active.busy = busy;
            active.card.setAttribute("aria-busy", String(busy));
            const fields = active.form.querySelector("[data-workspace-fields]");
            if (fields) fields.disabled = busy;
            for (const select of active.form.querySelectorAll("select[data-workspace-select]")) {
                if (busy) select.tomselect?.disable();
                else select.tomselect?.enable();
            }
        }

        async save() {
            const active = this.active;
            if (!active || active.busy) return;
            const body = new FormData(active.form);
            this.setBusy(active, true);
            this.announce("Saving section…");
            let reloading = false;
            try {
                const data = await this.request(active.form.action, { method: "POST", body }, active.key);
                this.setBusy(active, false);
                if (!data.saved) {
                    active.dirty = true;
                    this.mergeErrors(active, data.html);
                    this.announce("Please correct the errors below. Your entries and selected files have been kept; nothing was saved.", true);
                    return;
                }
                if ("workspaceReload" in this.root.dataset) {
                    reloading = true;
                    active.dirty = false;
                    this.setBusy(active, true);
                    this.announce(data.message || "Section saved. Refreshing…");
                    window.location.reload();
                    return;
                }
                this.replaceSummary(active, data.html);
                if (data.title) {
                    document.title = `BRIT · ${data.title}`;
                    this.root.querySelectorAll("[data-workspace-title]").forEach((title) => { title.textContent = data.title; });
                }
                active.dirty = false;
                this.close(active);
                this.announce(data.message || "Section saved.");
                active.link.focus();
            } catch (error) {
                this.announce("Changes were not saved or could not be confirmed. Your entries and selected files are still here. Check your connection and try again before leaving.", true);
            } finally {
                if (!reloading) this.setBusy(active, false);
            }
        }

        mergeErrors(active, html) {
            const fragment = this.fragment(html);
            this.stripScripts(fragment);
            const returned = new Map(Array.from(fragment.querySelectorAll("[data-workspace-errors]"), (node) => [node.dataset.workspaceErrors, node]));
            let first = null;
            for (const node of active.form.querySelectorAll("[data-workspace-errors]")) {
                const error = returned.get(node.dataset.workspaceErrors);
                node.innerHTML = error ? error.innerHTML : "";
                const field = active.form.elements.namedItem(node.dataset.workspaceErrors);
                if (field?.setAttribute) {
                    if (node.textContent.trim()) field.setAttribute("aria-invalid", "true");
                    else field.removeAttribute("aria-invalid");
                }
                if (node.textContent.trim()) {
                    const details = node.closest("details");
                    if (details) details.open = true;
                    if (!first) first = field?.focus && field.type !== "hidden" ? field : node;
                }
            }
            if (first?.tomselect) first.tomselect.focus();
            else first?.focus();
        }

        replaceSummary(active, html) {
            const fragment = this.fragment(html);
            this.stripScripts(fragment);
            active.summary.replaceChildren(fragment);
        }

        async addRow(formset) {
            const active = this.active;
            const total = formset.querySelector('input[name$="-TOTAL_FORMS"]');
            const max = formset.querySelector('input[name$="-MAX_NUM_FORMS"]');
            const index = Number(total.value);
            if (max?.value && index >= Number(max.value)) {
                this.announce("The maximum number of rows has been reached.", true);
                return;
            }
            const template = formset.querySelector("template[data-workspace-empty]");
            const fragment = this.fragment(template.innerHTML.replace(/__prefix__/g, String(index)));
            this.stripScripts(fragment);
            const row = fragment.querySelector("[data-workspace-row]");
            formset.querySelector("[data-workspace-rows]").appendChild(fragment);
            total.value = String(index + 1);
            active.dirty = true;
            this.announce("Row added. Changes are not saved yet.");
            try {
                await this.loadMedia(active.editor);
                if (this.active !== active) return;
                this.initializeWidgets(row);
                if (active.busy) {
                    row.querySelectorAll("select[data-workspace-select]").forEach((select) => select.tomselect?.disable());
                } else {
                    this.focusEditor({ editor: row });
                }
            } catch (error) {
                if (this.active === active) this.announce("Row added, but search could not load. Your entries are kept. You need JavaScript search to choose new entries; check your connection and retry.", true);
            }
        }

        parsePaste(text) {
            return text
                .split(/\r?\n/)
                .map((line) => {
                    const cells = line.split("\t");
                    return (cells.length === 1 ? cells[0].split(";") : cells).map((cell) => cell.trim());
                })
                .filter((cells) => cells.some((cell) => cell !== ""));
        }

        isPasteHeader(cells, columns) {
            const numeric = ["average", "standard_deviation", "sample_size"];
            return numeric.some((name) => {
                const index = columns.indexOf(name);
                const cell = index >= 0 ? cells[index] : undefined;
                return cell !== undefined && cell !== "" && !Number.isFinite(Number(cell.replace(",", ".")));
            });
        }

        async resolveReference(select, name) {
            const valueField = select.dataset.valueField || "id";
            const labelField = select.dataset.labelField === "label" ? "label" : "name";
            const results = await this.searchOptions(select, name);
            const matches = results.filter((result) => result[labelField].trim().toLowerCase() === name.trim().toLowerCase());
            if (matches.length !== 1 || !select.tomselect) return false;
            select.tomselect.addOption(matches[0]);
            select.tomselect.addItem(String(matches[0][valueField]));
            return true;
        }

        flagPasteField(row, column, text) {
            const field = row.querySelector(`[name$="-${column}"]`);
            const errors = field && row.querySelector(`[data-workspace-errors="${field.name}"]`);
            if (errors) errors.textContent = `No match for "${text}" — pick an existing entry.`;
        }

        async applyPaste(panel) {
            const active = this.active;
            const input = panel.querySelector("[data-workspace-paste-input]");
            const formset = this.active.editor.querySelector(`[data-workspace-formset="${input.dataset.pasteFormset}"]`);
            const columns = (input.dataset.pasteColumns || "").split(",").map((name) => name.trim()).filter(Boolean);
            if (!formset || !columns.length) return;
            let lines = this.parsePaste(input.value);
            if (lines.length && this.isPasteHeader(lines[0], columns)) lines = lines.slice(1);
            if (!lines.length) {
                this.announce("Nothing to add — paste one row per line.", true);
                return;
            }
            const numeric = ["average", "standard_deviation", "sample_size"];
            let unresolved = 0;
            for (const cells of lines) {
                await this.addRow(formset);
                if (this.active !== active) return;
                const row = formset.querySelector("[data-workspace-rows]").lastElementChild;
                for (const [index, column] of columns.entries()) {
                    const text = cells[index];
                    if (text === undefined || text === "") continue;
                    const field = row.querySelector(`[name$="-${column}"]`);
                    if (!field) continue;
                    if (field.matches("select[data-workspace-select]")) {
                        try {
                            if (await this.resolveReference(field, text)) continue;
                        } catch (error) { /* fall through to flag */ }
                        unresolved += 1;
                        this.flagPasteField(row, column, text);
                    } else {
                        field.value = numeric.includes(column) ? text.replace(",", ".") : text;
                    }
                }
            }
            input.value = "";
            active.dirty = true;
            this.announce(unresolved
                ? `Added ${lines.length} rows. ${unresolved} name${unresolved === 1 ? "" : "s"} could not be matched — pick ${unresolved === 1 ? "it" : "them"} manually before saving.`
                : `Added ${lines.length} row${lines.length === 1 ? "" : "s"}. Review them, then save the section.`,
            unresolved > 0);
        }

        setExpanded(active, expanded) {
            active.link.setAttribute("aria-expanded", String(expanded));
            this.root.querySelectorAll(`[data-workspace-edit="${active.key}"]`).forEach((link) => {
                link.setAttribute("aria-expanded", String(expanded));
            });
        }

        close(active) {
            for (const select of active.editor.querySelectorAll("select[data-workspace-select]")) select.tomselect?.destroy();
            active.editor.innerHTML = "";
            active.editor.hidden = true;
            active.summary.hidden = false;
            this.setExpanded(active, false);
            this.active = null;
        }

        cancel() {
            const active = this.active;
            if (!active) return true;
            if (active.busy) return false;
            if (active.dirty && !window.confirm("Discard unsaved changes in this section?")) return false;
            this.close(active);
            this.announce("Editing cancelled. Saved information is unchanged.");
            active.link.focus();
            return true;
        }
    }

    window.MaintenanceWorkspace = MaintenanceWorkspace;
    const start = async () => {
        for (const root of document.querySelectorAll("[data-workspace]")) new MaintenanceWorkspace(root);
        for (const root of document.querySelectorAll("[data-workspace-standalone]")) {
            const workspace = new MaintenanceWorkspace(root);
            const form = root.querySelector("form[data-workspace-section-form]");
            try {
                await workspace.loadMedia(root);
                workspace.initializeWidgets(root);
            } catch (error) {
                workspace.announce("Search could not load. Existing selections and other fields can still be saved, but choosing new entries requires JavaScript search. Check your connection and reload to retry.", true);
            }
            workspace.active = { form, editor: root, dirty: false, busy: false };
            root.addEventListener("submit", () => { workspace.active.dirty = false; }, true);
            root.addEventListener("click", (event) => {
                if (!event.target.closest("[data-workspace-cancel]")) return;
                if (workspace.active.dirty && !window.confirm("Discard unsaved changes?")) event.preventDefault();
                else workspace.active.dirty = false;
            }, true);
        }
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
    else start();
})();
