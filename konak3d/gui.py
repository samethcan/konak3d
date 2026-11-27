"""konak3d masaustu arayuzu (Tkinter, standart kutuphane)."""
import os, sys, queue, threading, traceback, subprocess, json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP = "konak3d"
PAD = {"padx": 10, "pady": 6}

def default_ckpt():
    """mobile_sam.pt dosyasini exe/klasor yaninda arar."""
    roots = [getattr(sys, "_MEIPASS", None), os.path.dirname(sys.executable),
             os.getcwd(), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for r in roots:
        if not r: continue
        for sub in ("", "models", "weights"):
            p = os.path.join(r, sub, "mobile_sam.pt")
            if os.path.exists(p): return p
    return "/tmp/MobileSAM/weights/mobile_sam.pt"

def open_folder(path):
    try:
        if sys.platform.startswith("win"): os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{APP} — ortofotodan 3B bina modeli")
        root.minsize(720, 560)
        self.q = queue.Queue()
        self.busy = False
        self.v = {k: tk.StringVar() for k in ("raster", "units", "aoi", "out", "ckpt")}
        self.v["out"].set(os.path.join(os.path.expanduser("~"), "konak3d_cikti"))
        self.v["ckpt"].set(default_ckpt())
        self.floor = tk.DoubleVar(value=3.0)
        self.fmt = {k: tk.BooleanVar(value=True) for k in ("geojson", "dxf", "glb")}
        self.reuse = tk.BooleanVar(value=False)
        self._build()
        self.root.after(120, self._drain)

    def _row(self, parent, r, label, key, kind, types=None):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", **PAD)
        ttk.Entry(parent, textvariable=self.v[key]).grid(row=r, column=1, sticky="ew", **PAD)
        cmd = (lambda: self._pick_dir(key)) if kind == "dir" else (lambda: self._pick_file(key, types))
        ttk.Button(parent, text="Gözat", command=cmd, width=8).grid(row=r, column=2, **PAD)

    def _build(self):
        f = ttk.Frame(self.root); f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1); f.rowconfigure(7, weight=1)
        self._row(f, 0, "Ortofoto (GeoTIFF)", "raster", "file", [("GeoTIFF", "*.tif *.tiff"), ("Tümü", "*.*")])
        self._row(f, 1, "Kat katmanı", "units", "file",
                  [("Vektör / Netcad", "*.gpkg *.geojson *.json *.shp *.NCZ *.ncz"), ("Tümü", "*.*")])
        self._row(f, 2, "Alan sınırı (isteğe bağlı)", "aoi", "file",
                  [("Sınır", "*.kmz *.kml *.geojson *.json *.gpkg *.shp"), ("Tümü", "*.*")])
        self._row(f, 3, "Çıktı klasörü", "out", "dir")
        self._row(f, 4, "Model dosyası (mobile_sam.pt)", "ckpt", "file", [("PyTorch", "*.pt"), ("Tümü", "*.*")])

        o = ttk.Frame(f); o.grid(row=5, column=0, columnspan=3, sticky="ew", padx=4)
        ttk.Label(o, text="Kat yüksekliği (m)").pack(side="left", padx=(6, 4))
        ttk.Spinbox(o, from_=2.0, to=6.0, increment=0.1, width=6, textvariable=self.floor).pack(side="left")
        for k, t in (("geojson", "GeoJSON"), ("dxf", "DXF (3B)"), ("glb", "GLB")):
            ttk.Checkbutton(o, text=t, variable=self.fmt[k]).pack(side="left", padx=6)
        ttk.Checkbutton(o, text="Önceki tespiti kullan", variable=self.reuse).pack(side="left", padx=6)

        b = ttk.Frame(f); b.grid(row=6, column=0, columnspan=3, sticky="ew", padx=4, pady=(8, 2))
        self.btn = ttk.Button(b, text="Çalıştır", command=self.start); self.btn.pack(side="left", padx=6)
        self.btn_open = ttk.Button(b, text="Çıktı klasörünü aç", command=lambda: open_folder(self.v["out"].get()))
        self.btn_open.pack(side="left", padx=6)
        self.prog = ttk.Progressbar(b, mode="determinate", maximum=8); self.prog.pack(side="left", fill="x", expand=True, padx=10)
        self.status = ttk.Label(b, text="hazır", width=22); self.status.pack(side="left", padx=6)

        lf = ttk.Frame(f); lf.grid(row=7, column=0, columnspan=3, sticky="nsew", padx=10, pady=(4, 10))
        lf.rowconfigure(0, weight=1); lf.columnconfigure(0, weight=1)
        self.log = tk.Text(lf, height=16, wrap="none", font=("Consolas", 10))
        self.log.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(lf, command=self.log.yview); sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set, state="disabled")

    def _pick_file(self, key, types):
        p = filedialog.askopenfilename(filetypes=types or [("Tümü", "*.*")])
        if p: self.v[key].set(p)

    def _pick_dir(self, key):
        p = filedialog.askdirectory()
        if p: self.v[key].set(p)

    def write(self, msg):
        self.log.configure(state="normal"); self.log.insert("end", str(msg) + "\n")
        self.log.see("end"); self.log.configure(state="disabled")

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log": self.write(payload)
                elif kind == "step":
                    i, n = payload; self.prog["value"] = i
                    self.status.configure(text=f"{i}/{n} adım")
                elif kind == "done": self._finish(payload)
                elif kind == "error":
                    self.write(payload); self.status.configure(text="hata")
                    self.busy = False; self.btn.configure(state="normal")
                    messagebox.showerror(APP, "İşlem tamamlanamadı. Günlüğe bakın.")
        except queue.Empty:
            pass
        self.root.after(120, self._drain)

    def _finish(self, qa):
        self.busy = False; self.btn.configure(state="normal"); self.status.configure(text="bitti")
        self.write("")
        self.write(f"bina            : {qa['footprints']}")
        self.write(f"kat eşleşen     : {qa['kat_matched']}")
        self.write(f"birim kapsaması : %{qa['coverage']*100:.1f} (>=%50)   %{qa['coverage30']*100:.1f} (>=%30)")
        self.write(f"taban alanı     : {qa['footprint_m2']:,.0f} m2")
        self.write(f"tahmini inşaat  : {qa['gfa_est_m2']:,.0f} m2")
        messagebox.showinfo(APP, f"Bitti. {qa['footprints']} bina, {len(qa['files'])} dosya yazıldı.")

    def _validate(self):
        if not os.path.exists(self.v["raster"].get()): return "Ortofoto dosyası seçin."
        if not os.path.exists(self.v["units"].get()): return "Kat katmanı dosyası seçin."
        a = self.v["aoi"].get().strip()
        if a and not os.path.exists(a): return "Alan sınırı dosyası bulunamadı."
        if not os.path.exists(self.v["ckpt"].get()): return "mobile_sam.pt bulunamadı. Model dosyasını seçin."
        if not any(v.get() for v in self.fmt.values()): return "En az bir çıktı biçimi seçin."
        return None

    def start(self):
        if self.busy: return
        err = self._validate()
        if err:
            messagebox.showwarning(APP, err); return
        out = self.v["out"].get(); os.makedirs(out, exist_ok=True)
        self.busy = True; self.btn.configure(state="disabled"); self.prog["value"] = 0
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        from . import pipeline
        try:
            qa = pipeline.run(
                self.v["raster"].get(), self.v["units"].get(), self.v["aoi"].get().strip() or None,
                workdir=os.path.join(self.v["out"].get(), "ara"), outdir=self.v["out"].get(),
                floor_h=float(self.floor.get()), ckpt=self.v["ckpt"].get(),
                formats=tuple(k for k, v in self.fmt.items() if v.get()),
                skip_detect=bool(self.reuse.get()),
                log=lambda m: self.q.put(("log", m)),
                on_step=lambda i, n: self.q.put(("step", (i, n))))
            self.q.put(("done", qa))
        except Exception:
            self.q.put(("error", traceback.format_exc()))

def main():
    root = tk.Tk()
    try: ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    except Exception: pass
    App(root); root.mainloop()

if __name__ == "__main__":
    main()
