# konak3d

Ortofotodan bina ayak izi çıkarır, kat bilgisiyle birleştirir ve LoD1 3B model üretir.

Girdi bir ortofoto (GeoTIFF) ve kat sayısı taşıyan bir bina katmanıdır. Çıktı GeoJSON, 3B DXF ve GLB'dir.

**Canlı demo:** [samethcan.github.io/konak3d](https://samethcan.github.io/konak3d/) — tarayıcıda dönen 3B model, kat yüksekliği kaydırıcısı. Sentetik veriyle çalışır.

```
ortofoto.tif ──► detect ──► footprint ──► refine ──┐
                                                   ├──► join ──► export ──► scene
kat katmanı  ──► units / ncz ──────────────────────┤
alan sınırı  ──► aoi ──────────────────────────────┘
```

## Kurulum

```bash
git clone https://github.com/samethcan/konak3d.git
cd konak3d
pip install -e .
# segmentasyon modeli (ayrı depo, Apache-2.0)
git clone https://github.com/ChaoningZhang/MobileSAM /tmp/MobileSAM
pip install -e /tmp/MobileSAM
```

## Masaüstü arayüzü

```bash
konak3d gui
```

Dosyaları seç, kat yüksekliğini gir, Çalıştır'a bas. İlerleme ve günlük pencerede akar, sonunda özet çıkar.
Windows için tek dosyalık `.exe`: `build_windows.bat` dosyasına çift tıklayın, gerisi kendiliğinden ilerler. Ayrıntılar: [BUILD.md](BUILD.md).

## Hızlı başlangıç (sentetik demo)

Depo gerçek veri içermez. `demo/make_demo.py` sentetik bir ortofoto, kat katmanı ve alan sınırı üretir:

```bash
python demo/make_demo.py
konak3d inspect   demo/ortofoto.tif
konak3d aoi       demo/aoi.geojson  --raster demo/ortofoto.tif
konak3d units     demo/units.gpkg   --raster demo/ortofoto.tif
konak3d detect    --raster demo/ortofoto.tif
konak3d footprint --raster demo/ortofoto.tif
konak3d refine    --raster demo/ortofoto.tif
konak3d join      --raster demo/ortofoto.tif --floor-h 3.0
konak3d export    --format geojson,dxf,glb
konak3d scene
```

## Komutlar

| Komut | Yaptığı iş |
|---|---|
| `inspect` | Raster boyutu, koordinat sistemi, GSD, kapsama alanı |
| `aoi` | Alan sınırını (`.kmz` `.kml` `.geojson` `.gpkg` `.shp`) rasterin piksel uzayına taşır |
| `units` | Vektör bina katmanından kat bilgisi okur (`--kat-field`, `--id-field`) |
| `ncz` | Netcad `.NCZ` ikili dosyasından bina çokgeni + kat sayısı okur |
| `detect` | MobileSAM ile karo bazlı maske üretimi; alan, dışbükeylik, dikdörtgenlik, en-boy ve bitki örtüsü (ExG) filtreleri |
| `footprint` | Karo bindirmelerini NMS ile temizler, `buildingregulariser` ile köşeleri dikleştirir |
| `refine` | Kapsanmayan kat birimlerini nokta + kutu istemi olarak verip ikinci segmentasyon yapar (sıkı ve gevşek iki geçiş) |
| `join` | Ayak izi ile kat katmanını örtüşmeye göre eşler, `height_m = kat × floor_h` atar, kapsama ölçer |
| `export` | GeoJSON (EPSG:4326), katmanlı 3B DXF, renkli GLB |
| `scene` | Bina sayısı, taban alanı, tahmini inşaat alanı |
| `gui` | Masaüstü arayüzünü açar |

Ara çıktılar `work/`, nihai çıktılar `out/` altına yazılır. İkisi de `.gitignore` içindedir.

## Kalite ölçütleri

`join` her çalıştığında şunları basar:

- `matched` — kat bilgisi eşlenen ayak izi sayısı
- `unit_cover>=50%` — kat katmanındaki birimlerin kaçının alanının en az yarısı bir ayak iziyle örtüşüyor
- `unit_cover>=30%` — aynısı üçte bir eşikle
- `kat hist` — kat sayısı dağılımı

Her ayak izi `kat_kaynak` alanı taşır: `kat_defteri` ya da `yok(varsayim)`.

## Sınırlar

- `refine` adımı kat katmanının konumlarını istem olarak kullanır. Bu adımda eklenen binalar tam otomatik tespit değildir.
- Yükseklik `kat × floor_h` varsayımıdır; gerçek kat yüksekliği ölçülmez.
- Kat bilgisi eşlenemeyen binalara varsayılan tek kat yüksekliği atanır.
- `.NCZ` okuyucusu tersine mühendislikle yazılmıştır, resmî bir format belgesine dayanmaz. Çıktı ortofotoyla görsel olarak doğrulanmalıdır.
- Ağaç altında kalan ve çok küçük yapılar kaçabilir; spor sahası gibi düz yüzeyler yanlış pozitif verebilir.
- Arayüz Tkinter ile yazıldı ve sahte bir Tk katmanıyla test edildi; gerçek pencere yönetimi hedef makinede denenmelidir.
- GPU gerekmez ama CPU'da yavaştır (1024 px karo, 2 çekirdek: karo başına yaklaşık 3-4 dk).

## Veri ve gizlilik

Bu depoda ortofoto, kadastro, tapu veya kat defteri verisi **yoktur**. Testler sentetik demo verisiyle yapılır.
Kurum verisiyle çalışırken `work/` ve `out/` klasörleri sürüm kontrolüne girmez; veri paylaşımı için kurumunuzun iznini alın.

## Lisans

MIT. MobileSAM ayrı bir depodur ve kendi lisansına tabidir.
