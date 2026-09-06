from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import shutil
import traceback
from datetime import datetime

from src.datamind.pipeline import run_pipeline


class DataMindDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DataMind 公募基金自动分析")
        self.root.geometry("760x420")

        self.input_var = tk.StringVar(value="data/sample_xbrl")
        self.output_excel_var = tk.StringVar(value="output/fund_competitor_report.xlsx")
        self.output_brief_var = tk.StringVar(value="output/fund_competitor_report.md")
        self.fund_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="准备就绪")
        self.upload_staging_dir = Path("data/uploaded_reports")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="DataMind 公募基金自动化分析", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(frame, text="取数 -> 清洗 -> 分析 -> 图表报告导出", fg="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))

        tk.Label(frame, text="报告目录(XBRL/XML/PDF)").grid(row=2, column=0, sticky="w")
        tk.Entry(frame, textvariable=self.input_var, width=72).grid(row=2, column=1, sticky="we", padx=8)
        tk.Button(frame, text="选目录", command=self._pick_input_dir).grid(row=2, column=2)

        tk.Button(frame, text="选择报告文件(支持PDF)", command=self._pick_input_files).grid(row=3, column=0, columnspan=3, sticky="we", pady=(10, 0))

        tk.Label(frame, text="Excel输出").grid(row=4, column=0, sticky="w", pady=(10, 0))
        tk.Entry(frame, textvariable=self.output_excel_var, width=72).grid(row=4, column=1, sticky="we", padx=8, pady=(10, 0))
        tk.Button(frame, text="浏览", command=self._pick_excel_output).grid(row=4, column=2, pady=(10, 0))

        tk.Label(frame, text="简报输出").grid(row=5, column=0, sticky="w", pady=(10, 0))
        tk.Entry(frame, textvariable=self.output_brief_var, width=72).grid(row=5, column=1, sticky="we", padx=8, pady=(10, 0))
        tk.Button(frame, text="浏览", command=self._pick_brief_output).grid(row=5, column=2, pady=(10, 0))

        tk.Label(frame, text="基金白名单(逗号分隔，可选)").grid(row=6, column=0, sticky="w", pady=(10, 0))
        tk.Entry(frame, textvariable=self.fund_var, width=72).grid(row=6, column=1, columnspan=2, sticky="we", padx=8, pady=(10, 0))

        tk.Button(frame, text="一键生成竞品报告", command=self._run_pipeline_async, bg="#1177CC", fg="white").grid(row=7, column=0, columnspan=3, sticky="we", pady=(18, 10))

        tk.Label(frame, textvariable=self.status_var, anchor="w", fg="#222").grid(row=8, column=0, columnspan=3, sticky="we")
        frame.columnconfigure(1, weight=1)

    def _pick_input_dir(self) -> None:
        selected = filedialog.askdirectory(title="选择报告目录(XBRL/XML/PDF)")
        if selected:
            self.input_var.set(selected)

    def _pick_input_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="选择报告文件",
            filetypes=[
                ("Report files", "*.xbrl *.xml *.pdf"),
                ("XBRL", "*.xbrl"),
                ("XML", "*.xml"),
                ("PDF", "*.pdf"),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return

        if self.upload_staging_dir.exists():
            shutil.rmtree(self.upload_staging_dir)
        self.upload_staging_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for src in selected:
            src_path = Path(src)
            if src_path.suffix.lower() not in {".xbrl", ".xml", ".pdf"}:
                continue
            shutil.copy2(src_path, self.upload_staging_dir / src_path.name)
            copied += 1

        if copied == 0:
            messagebox.showwarning("提示", "未选择可解析文件，请选择 .xbrl/.xml/.pdf")
            return

        self.input_var.set(str(self.upload_staging_dir))
        self.status_var.set(f"已导入 {copied} 个文件到临时目录")

    def _pick_excel_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="选择Excel输出路径",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if selected:
            self.output_excel_var.set(selected)

    def _pick_brief_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="选择简报输出路径",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md")],
        )
        if selected:
            self.output_brief_var.set(selected)

    def _run_pipeline_async(self) -> None:
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self) -> None:
        try:
            self.status_var.set("处理中，请稍候...")
            whitelist = [x.strip() for x in self.fund_var.get().split(",") if x.strip()]
            input_path = Path(self.input_var.get())
            excel_path = Path(self.output_excel_var.get())
            brief_path = Path(self.output_brief_var.get())

            try:
                cleaned_df = run_pipeline(
                    input_dir=input_path,
                    output_excel=excel_path,
                    output_markdown=brief_path,
                    fund_whitelist=whitelist or None,
                )
            except PermissionError:
                # If output files are locked by Excel/WPS, fallback to timestamped names.
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                fallback_excel = excel_path.with_name(f"{excel_path.stem}_{stamp}{excel_path.suffix}")
                fallback_brief = brief_path.with_name(f"{brief_path.stem}_{stamp}{brief_path.suffix}")
                cleaned_df = run_pipeline(
                    input_dir=input_path,
                    output_excel=fallback_excel,
                    output_markdown=fallback_brief,
                    fund_whitelist=whitelist or None,
                )
                self.output_excel_var.set(str(fallback_excel))
                self.output_brief_var.set(str(fallback_brief))
                messagebox.showwarning(
                    "文件占用",
                    "原输出文件可能被Excel/WPS占用，已自动切换为带时间戳的新文件。",
                )

            total_funds = int(cleaned_df["fund_name"].nunique()) if not cleaned_df.empty else 0
            total_companies = int(cleaned_df["company"].nunique()) if not cleaned_df.empty else 0
            self.status_var.set(f"完成: 记录数={len(cleaned_df)}, 基金数={total_funds}, 公司数={total_companies}")
            messagebox.showinfo(
                "执行成功",
                f"已生成报告\nExcel: {self.output_excel_var.get()}\n简报: {self.output_brief_var.get()}",
            )
        except Exception as ex:
            self.status_var.set("执行失败")
            messagebox.showerror("错误", str(ex))


def main() -> None:
    try:
        root = tk.Tk()
        DataMindDesktopApp(root)
        root.mainloop()
    except Exception:
        log_dir = Path("output")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "gui_error.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"GUI startup failed. Check log: {log_path}")
        raise


if __name__ == "__main__":
    main()
