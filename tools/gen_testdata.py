#!/usr/bin/env python3
"""
测试数据生成器
生成与软件各模块对应的模拟数据：
  - GeoTIFF 测试图像（模拟冰间水道、融池、冰脊、冰类型）
  - CSV 测线文件（模拟冰厚度测量）
  - MAT 格式文件（模拟冰厚度反演信号）

运行：python tools/gen_testdata.py
输出目录：data/test/
"""

import os
import struct
import sys

import numpy as np

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "test")
os.makedirs(OUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def write_geotiff(path: str, data: np.ndarray,
                  lat_min: float, lat_max: float,
                  lon_min: float, lon_max: float,
                  nodata: float = None):
    """写极简 GeoTIFF（需 rasterio；否则退化为保存 npy + 元数据 json）"""
    try:
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.crs import CRS

        transform = from_bounds(lon_min, lat_min, lon_max, lat_max,
                                data.shape[1], data.shape[0])
        profile = {
            "driver": "GTiff",
            "dtype": data.dtype,
            "width": data.shape[1],
            "height": data.shape[0],
            "count": 1,
            "crs": CRS.from_epsg(4326),
            "transform": transform,
            "compress": "lzw",
        }
        if nodata is not None:
            profile["nodata"] = nodata

        with rasterio.open(path, "w", **profile) as dst:
            dst.write(data, 1)
        print(f"  GeoTIFF: {path}")

    except ImportError:
        # 退化：保存 numpy + 元数据
        npy_path = path.replace(".tif", ".npy")
        np.save(npy_path, data)
        import json
        meta = {"lat_min": lat_min, "lat_max": lat_max,
                 "lon_min": lon_min, "lon_max": lon_max,
                 "shape": list(data.shape), "dtype": str(data.dtype)}
        with open(path.replace(".tif", "_meta.json"), "w") as f:
            json.dump(meta, f)
        print(f"  NPY (rasterio未安装): {npy_path}")


def smooth(arr: np.ndarray, sigma: float = 5.0) -> np.ndarray:
    from scipy.ndimage import gaussian_filter
    return gaussian_filter(arr.astype(np.float32), sigma=sigma)


# ─────────────────────────────────────────────────────────────
# 数据生成函数
# ─────────────────────────────────────────────────────────────

def gen_ice_channel(rows=512, cols=512):
    """冰间水道：背景为冰（高值），水道为低值窄条"""
    rng = np.random.default_rng(42)
    data = rng.uniform(0.6, 1.0, (rows, cols)).astype(np.float32)
    # 添加3条随机水道
    for _ in range(3):
        cx = rng.integers(50, cols - 50)
        width = rng.integers(5, 20)
        angle = rng.uniform(-0.3, 0.3)
        for r in range(rows):
            c = int(cx + r * angle)
            c = max(0, min(cols - 1, c))
            lo, hi = max(0, c - width), min(cols, c + width)
            data[r, lo:hi] = rng.uniform(0.05, 0.25, hi - lo)
    data = smooth(data, sigma=2)
    path = os.path.join(OUT_DIR, "ice_channel_test.tif")
    write_geotiff(path, data, 75.0, 80.0, -10.0, 10.0, nodata=-9999.0)
    return path


def gen_melt_pond(rows=512, cols=512):
    """海冰融池：散布的低后向散射斑块"""
    rng = np.random.default_rng(7)
    data = rng.uniform(0.5, 0.9, (rows, cols)).astype(np.float32)
    for _ in range(60):
        cy, cx = rng.integers(30, rows - 30), rng.integers(30, cols - 30)
        ry, rx = rng.integers(5, 25), rng.integers(5, 25)
        yy, xx = np.ogrid[-ry:ry + 1, -rx:rx + 1]
        mask = (yy / ry) ** 2 + (xx / rx) ** 2 <= 1
        y1, y2 = max(0, cy - ry), min(rows, cy + ry + 1)
        x1, x2 = max(0, cx - rx), min(cols, cx + rx + 1)
        my1, my2 = ry - (cy - y1), ry + (y2 - cy)
        mx1, mx2 = rx - (cx - x1), rx + (x2 - cx)
        data[y1:y2, x1:x2] = np.where(
            mask[my1:my2, mx1:mx2],
            rng.uniform(0.05, 0.2, (y2 - y1, x2 - x1)),
            data[y1:y2, x1:x2],
        )
    data = smooth(data, sigma=1.5)
    path = os.path.join(OUT_DIR, "melt_pond_test.tif")
    write_geotiff(path, data, 76.0, 79.0, -5.0, 8.0, nodata=-9999.0)
    return path


def gen_ice_type(rows=512, cols=512):
    """海冰类型分类：0=海水 1=一年冰 2=多年冰 3=变形冰"""
    rng = np.random.default_rng(13)
    from scipy.ndimage import label, binary_dilation

    data = rng.choice([0, 1, 2, 3], size=(rows, cols),
                      p=[0.1, 0.45, 0.35, 0.1]).astype(np.uint8)
    # 形态学平滑使其连续
    for cls in range(4):
        mask = data == cls
        dilated = binary_dilation(mask, iterations=8)
        data[dilated & (data == 0)] = cls
    path = os.path.join(OUT_DIR, "ice_type_test.tif")
    write_geotiff(path, data.astype(np.float32), 74.0, 80.0, -15.0, 15.0)
    return path


def gen_ice_ridge(rows=512, cols=512):
    """冰脊参数：粗糙度指数图"""
    rng = np.random.default_rng(99)
    x = np.linspace(0, 4 * np.pi, cols)
    y = np.linspace(0, 4 * np.pi, rows)
    xx, yy = np.meshgrid(x, y)
    base = (np.sin(xx * 1.5) * np.cos(yy) + 1) / 2
    noise = rng.uniform(0, 0.3, (rows, cols))
    data = (base + noise).clip(0, 1).astype(np.float32)
    data = smooth(data, sigma=3)
    path = os.path.join(OUT_DIR, "ice_ridge_test.tif")
    write_geotiff(path, data, 78.0, 83.0, 5.0, 25.0, nodata=-9999.0)
    return path


def gen_track_csv(n_points=200):
    """测线 CSV：模拟极区飞行测量轨迹"""
    rng = np.random.default_rng(55)
    lat0, lon0 = 78.0, 0.0
    lats = lat0 + np.cumsum(rng.uniform(0.01, 0.05, n_points))
    lons = lon0 + np.cumsum(rng.uniform(-0.04, 0.04, n_points))

    # 每点包含：位置、深度、亮温、后向散射
    depths = 1.5 + 0.8 * np.sin(np.linspace(0, 3 * np.pi, n_points)) + \
             rng.normal(0, 0.15, n_points)
    depths = depths.clip(0.1, 5.0)
    tb = 230 + 20 * np.cos(np.linspace(0, 2 * np.pi, n_points)) + \
         rng.normal(0, 5, n_points)
    sigma = -15 + 5 * np.sin(np.linspace(0, 4 * np.pi, n_points)) + \
            rng.normal(0, 1, n_points)

    path = os.path.join(OUT_DIR, "track_test.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("lat,lon,depth,brightness_temp,backscatter\n")
        for i in range(n_points):
            f.write(f"{lats[i]:.6f},{lons[i]:.6f},"
                    f"{depths[i]:.3f},{tb[i]:.2f},{sigma[i]:.3f}\n")
    print(f"  CSV: {path}")
    return path


def gen_multiband_3d(rows=400, cols=400):
    """
    多波段 GeoTIFF（5波段）—— 专为 3D 可视化演示设计
      Band1: 亮温 TB (K)          — 平滑背景场，范围 [200, 260]
      Band2: 海冰密集度 SIC (%)   — 块状分布，范围 [0, 100]
      Band3: 海冰厚度 (m)         — 起伏明显，范围 [0, 5]，适合作 Z 轴
      Band4: 后向散射 σ° (dB)     — 带噪声，范围 [-25, -5]
      Band5: 冰脊强度 RI          — 高频起伏，范围 [0, 1]
    地理范围：北极中心区，78–82°N / -10–10°E
    """
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS

    rng = np.random.default_rng(2024)
    x = np.linspace(0, 2 * np.pi, cols)
    y = np.linspace(0, 2 * np.pi, rows)
    xx, yy = np.meshgrid(x, y)

    # Band1: 亮温 TB —— 大尺度低频场
    tb = (230
          + 15 * np.sin(xx * 0.8) * np.cos(yy * 0.6)
          + 10 * np.cos(xx * 0.3 + yy * 0.5)
          + rng.normal(0, 3, (rows, cols)))
    tb = smooth(tb.astype(np.float32), sigma=8).clip(200, 260)

    # Band2: 海冰密集度 SIC —— 渐变 + 低密集区斑块
    sic_base = 80 + 15 * np.cos(yy * 0.7) - 10 * np.sin(xx * 0.4)
    for _ in range(12):
        cy, cx = rng.integers(40, rows - 40), rng.integers(40, cols - 40)
        r = rng.integers(15, 50)
        yy_d = (np.arange(rows) - cy)[:, None]
        xx_d = (np.arange(cols) - cx)[None, :]
        mask = (yy_d**2 + xx_d**2) < r**2
        sic_base[mask] -= rng.uniform(30, 60)
    sic = smooth(sic_base.astype(np.float32), sigma=5).clip(0, 100)

    # Band3: 海冰厚度 —— 多尺度叠加，适合三维展示
    thickness = (
        2.5
        + 1.5 * np.sin(xx * 1.2) * np.cos(yy * 0.9)
        + 0.8 * np.sin(xx * 2.5 + 0.5) * np.sin(yy * 2.0)
        + 0.4 * np.cos(xx * 4.0) * np.cos(yy * 3.5)
        + rng.normal(0, 0.15, (rows, cols))
    )
    # 加入几个薄冰区（冰间水道）
    for _ in range(3):
        cx = rng.integers(60, cols - 60)
        w  = rng.integers(8, 25)
        angle = rng.uniform(-0.4, 0.4)
        for r in range(rows):
            c = int(cx + r * angle)
            c = max(0, min(cols - 1, c))
            lo, hi = max(0, c - w), min(cols, c + w)
            thickness[r, lo:hi] *= rng.uniform(0.05, 0.25)
    thickness = smooth(thickness.astype(np.float32), sigma=3).clip(0.05, 5.0)

    # Band4: 后向散射 σ° —— 与厚度相关 + 噪声
    sigma0 = -18 + 4 * (thickness / 5.0) + 3 * np.sin(xx * 3 + yy * 2)
    sigma0 += rng.normal(0, 1.5, (rows, cols))
    sigma0 = smooth(sigma0.astype(np.float32), sigma=2).clip(-25, -5)

    # Band5: 冰脊强度 —— 高频起伏
    ridge = (
        0.3 * np.abs(np.sin(xx * 5) * np.cos(yy * 4))
        + 0.2 * np.abs(np.sin(xx * 8 + yy * 6))
        + rng.uniform(0, 0.15, (rows, cols))
    )
    ridge = smooth(ridge.astype(np.float32), sigma=1.5).clip(0, 1)

    bands = [
        (tb.astype(np.float32),       "Brightness_Temperature_K"),
        (sic.astype(np.float32),      "Sea_Ice_Concentration_pct"),
        (thickness.astype(np.float32),"Ice_Thickness_m"),
        (sigma0.astype(np.float32),   "Backscatter_sigma0_dB"),
        (ridge.astype(np.float32),    "Ridge_Intensity"),
    ]

    path = os.path.join(OUT_DIR, "multiband_3d_test.tif")
    transform = from_bounds(-10.0, 78.0, 10.0, 82.0, cols, rows)
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": cols,
        "height": rows,
        "count": len(bands),
        "crs": CRS.from_epsg(4326),
        "transform": transform,
        "compress": "lzw",
    }
    with rasterio.open(path, "w", **profile) as dst:
        for i, (arr, desc) in enumerate(bands, start=1):
            dst.write(arr, i)
        dst.descriptions = tuple(d for _, d in bands)

    # 打印摘要
    print(f"  多波段 GeoTIFF: {path}")
    for i, (arr, desc) in enumerate(bands, start=1):
        print(f"    Band{i} [{desc}]: "
              f"min={arr.min():.3f}  max={arr.max():.3f}  mean={arr.mean():.3f}")
    return path


def gen_mat_signal(n_signals=50):
    """MAT 格式：模拟冰厚度反演信号（FMCW雷达波形）"""
    try:
        from scipy.io import savemat
    except ImportError:
        print("  警告: scipy未安装，跳过MAT格式生成")
        return None

    rng = np.random.default_rng(77)
    n_samples = 12000
    t = np.linspace(0, 1, n_samples)

    signals = []
    true_depths = []
    for _ in range(n_signals):
        depth = rng.uniform(0.5, 4.0)
        f1 = 300e6 + depth * 50e6
        sig = (np.sin(2 * np.pi * f1 * t) * np.exp(-t * 3)
               + rng.normal(0, 0.05, n_samples))
        signals.append(sig.astype(np.float32))
        true_depths.append(depth)

    mat_data = {
        "signals": np.array(signals),
        "true_depths": np.array(true_depths),
        "n_samples": n_samples,
        "description": "模拟FMCW雷达冰厚度测量信号",
    }
    path = os.path.join(OUT_DIR, "thickness_signals.mat")
    savemat(path, mat_data)
    print(f"  MAT: {path}")
    return path


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

def main():
    print(f"测试数据输出目录: {OUT_DIR}\n")

    tasks = [
        ("冰间水道测试图", gen_ice_channel),
        ("海冰融池测试图", gen_melt_pond),
        ("海冰类型分类图", gen_ice_type),
        ("冰脊参数测试图", gen_ice_ridge),
        ("测线CSV数据", gen_track_csv),
        ("MAT信号数据", gen_mat_signal),
        ("多波段3D测试图（5波段）", gen_multiband_3d),
    ]

    for name, fn in tasks:
        print(f"生成: {name}...")
        try:
            fn()
        except Exception as e:
            print(f"  [失败] {e}")

    print("\n全部生成完成。")
    print(f"文件位于: {OUT_DIR}")


if __name__ == "__main__":
    main()
