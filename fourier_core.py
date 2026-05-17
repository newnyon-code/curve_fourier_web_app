from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass
class FourierDescriptor:
    coeffs: np.ndarray
    freqs: np.ndarray
    sampled_curve: np.ndarray

    @classmethod
    def from_curve(cls, curve: np.ndarray, n_samples: int) -> "FourierDescriptor":
        z = resample_by_arclength(as_complex(curve), n_samples)
        coeffs = np.fft.fft(z) / len(z)
        freqs = np.rint(np.fft.fftfreq(len(z), d=1.0 / len(z))).astype(int)
        return cls(coeffs.astype(np.complex128), freqs, z)

    @property
    def n_samples(self) -> int:
        return int(len(self.sampled_curve))

    @property
    def max_available_order(self) -> int:
        return int(np.max(np.abs(self.freqs)))

    def mask_for_order(self, order: int) -> np.ndarray:
        return np.abs(self.freqs) <= int(order)

    def sparse_ifft(self, freqs: np.ndarray, coeffs: np.ndarray, n_samples: int) -> np.ndarray:
        spectrum = np.zeros(int(n_samples), dtype=np.complex128)
        for freq, coef in zip(freqs, coeffs):
            spectrum[int(freq) % int(n_samples)] += int(n_samples) * coef
        return np.fft.ifft(spectrum)

    def reconstruct(self, order: int, n_samples: int | None = None) -> np.ndarray:
        count = self.n_samples if n_samples is None else int(n_samples)
        mask = self.mask_for_order(order)
        return self.sparse_ifft(self.freqs[mask], self.coeffs[mask], count)

    def derivative(self, order: int, n_samples: int) -> np.ndarray:
        mask = self.mask_for_order(order)
        freqs = self.freqs[mask]
        coeffs = (2j * np.pi * freqs) * self.coeffs[mask]
        return self.sparse_ifft(freqs, coeffs, int(n_samples))

    def perimeter(self, order: int, n_samples: int) -> float:
        dz = self.derivative(order, n_samples)
        return float(np.mean(np.abs(dz)))

    def energy_ratio(self, order: int) -> float:
        total = float(np.sum(np.abs(self.coeffs) ** 2))
        if total <= 0:
            return 0.0
        kept = float(np.sum(np.abs(self.coeffs[self.mask_for_order(order)]) ** 2))
        return kept / total

    def coefficient_table(self) -> pd.DataFrame:
        order = np.argsort(self.freqs)
        freqs = self.freqs[order]
        coeffs = self.coeffs[order]
        return pd.DataFrame(
            {
                "frequency_k": freqs,
                "real": coeffs.real,
                "imag": coeffs.imag,
                "radius_abs_c": np.abs(coeffs),
                "phase_rad": np.angle(coeffs),
            }
        )


def as_complex(points: np.ndarray) -> np.ndarray:
    arr = np.asarray(points)
    if np.iscomplexobj(arr):
        z = arr.astype(np.complex128).reshape(-1)
    else:
        if arr.ndim != 2 or arr.shape[1] < 2:
            raise ValueError("points must be an array with x and y columns")
        z = arr[:, 0].astype(float) + 1j * arr[:, 1].astype(float)
    mask = np.isfinite(z.real) & np.isfinite(z.imag)
    z = z[mask]
    if len(z) < 3:
        raise ValueError("at least three valid points are required")
    return remove_duplicate_consecutive(z)


def remove_duplicate_consecutive(z: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    z = np.asarray(z, dtype=np.complex128).reshape(-1)
    keep = np.ones(len(z), dtype=bool)
    keep[1:] = np.abs(np.diff(z)) > eps
    out = z[keep]
    if len(out) < 3:
        raise ValueError("too few distinct points")
    return out


def close_curve(z: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    z = remove_duplicate_consecutive(z)
    if abs(z[0] - z[-1]) > eps:
        z = np.concatenate([z, z[:1]])
    return z


def polygon_perimeter(z: np.ndarray) -> float:
    zc = close_curve(z)
    return float(np.sum(np.abs(np.diff(zc))))


def resample_by_arclength(z: np.ndarray, n_samples: int) -> np.ndarray:
    if int(n_samples) < 32:
        raise ValueError("samples must be at least 32")
    zc = close_curve(z)
    seg_len = np.abs(np.diff(zc))
    valid = seg_len > 1e-10
    if not np.all(valid):
        kept = np.concatenate([[True], valid[:-1]])
        zc = close_curve(np.concatenate([zc[:-1][kept], zc[:1]]))
        seg_len = np.abs(np.diff(zc))
    s = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = float(s[-1])
    if total <= 0:
        raise ValueError("curve perimeter is zero")
    target = np.linspace(0.0, total, int(n_samples), endpoint=False)
    x = np.interp(target, s, zc.real)
    y = np.interp(target, s, zc.imag)
    return x + 1j * y


def curve_scale(z: np.ndarray) -> float:
    z = as_complex(z)
    width = float(np.ptp(z.real))
    height = float(np.ptp(z.imag))
    return max(math.hypot(width, height), 1e-12)


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    a = as_complex(a)
    b = as_complex(b)
    if len(a) != len(b):
        raise ValueError("rmse inputs must have the same length")
    return float(np.sqrt(np.mean(np.abs(a - b) ** 2)))


def analyze_orders(descriptor: FourierDescriptor, max_order: int, perimeter_samples: int) -> pd.DataFrame:
    max_order = int(min(max_order, descriptor.max_available_order, descriptor.n_samples // 2 - 1))
    if max_order < 1:
        raise ValueError("max_order must be at least 1")
    z_ref = descriptor.sampled_curve
    reference_perimeter = polygon_perimeter(z_ref)
    scale = curve_scale(z_ref)
    rows = []
    prev_length = np.nan
    for order in range(1, max_order + 1):
        z_hat = descriptor.reconstruct(order, descriptor.n_samples)
        fourier_length = descriptor.perimeter(order, perimeter_samples)
        point_rmse = rmse(z_ref, z_hat)
        length_error = fourier_length - reference_perimeter
        relative_length_error = length_error / reference_perimeter if reference_perimeter else np.nan
        if np.isfinite(prev_length):
            step_change = abs(fourier_length - prev_length) / max(abs(prev_length), 1e-12)
        else:
            step_change = np.nan
        rows.append(
            {
                "N": order,
                "fourier_perimeter": fourier_length,
                "reference_polygon_perimeter": reference_perimeter,
                "length_error": length_error,
                "relative_length_error": relative_length_error,
                "abs_relative_length_error": abs(relative_length_error),
                "rmse": point_rmse,
                "rmse_normalized": point_rmse / scale,
                "relative_step_change": step_change,
                "energy_ratio": descriptor.energy_ratio(order),
            }
        )
        prev_length = fourier_length
    return pd.DataFrame(rows)


def choose_stable_order(order_df: pd.DataFrame, slope_tol: float, rmse_tol: float, energy_tol: float, window: int) -> dict[str, Any]:
    df = order_df.copy().reset_index(drop=True)
    if df.empty:
        raise ValueError("order_df is empty")
    min_error_idx = int(df["abs_relative_length_error"].idxmin())
    min_error_n = int(df.loc[min_error_idx, "N"])
    step = df["relative_step_change"].to_numpy()
    good_quality = (df["rmse_normalized"].to_numpy() <= float(rmse_tol)) & (df["energy_ratio"].to_numpy() >= float(energy_tol))
    stable_idx = None
    for i in range(len(df)):
        if not good_quality[i]:
            continue
        end = i + int(window)
        if end >= len(df):
            continue
        future_steps = step[i + 1 : end + 1]
        if np.all(np.isfinite(future_steps)) and float(np.max(future_steps)) <= float(slope_tol):
            stable_idx = i
            reason = "plateau_start_rule"
            break
    if stable_idx is None:
        step_fill = df["relative_step_change"].fillna(df["relative_step_change"].max())
        score = step_fill + 0.35 * df["rmse_normalized"] + 0.15 * (1.0 - df["energy_ratio"])
        stable_idx = int(score.idxmin())
        reason = "fallback_low_score"
    chosen = df.loc[stable_idx]
    return {
        "recommended_N": int(chosen["N"]),
        "selection_reason": reason,
        "recommended_fourier_perimeter": float(chosen["fourier_perimeter"]),
        "reference_polygon_perimeter": float(chosen["reference_polygon_perimeter"]),
        "recommended_relative_length_error": float(chosen["relative_length_error"]),
        "recommended_rmse_normalized": float(chosen["rmse_normalized"]),
        "recommended_energy_ratio": float(chosen["energy_ratio"]),
        "min_error_N": min_error_n,
        "min_error_relative_length_error": float(df.loc[min_error_idx, "relative_length_error"]),
        "parameters": {
            "slope_tol": float(slope_tol),
            "rmse_tol": float(rmse_tol),
            "energy_tol": float(energy_tol),
            "window": int(window),
        },
    }


def candidate_orders(recommended_n: int, max_order: int) -> list[int]:
    values = {1, max(2, recommended_n // 2), recommended_n, min(max_order, max(recommended_n * 2, recommended_n + 1)), max_order}
    return sorted(int(v) for v in values if 1 <= int(v) <= int(max_order))


def save_curve_csv(path: Path, z: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"x": np.asarray(z).real, "y": np.asarray(z).imag}).to_csv(path, index=False)


def set_equal_axes(ax: plt.Axes) -> None:
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)


def plot_curve_comparison(descriptor: FourierDescriptor, orders: list[int], out_path: Path, title: str) -> None:
    z_ref = close_curve(descriptor.sampled_curve)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.plot(z_ref.real, z_ref.imag, linewidth=2.2, label="input")
    for order in orders:
        z = close_curve(descriptor.reconstruct(int(order), descriptor.n_samples))
        ax.plot(z.real, z.imag, linewidth=1.2, label=f"N={int(order)}")
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    set_equal_axes(ax)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170, format="jpg")
    plt.close(fig)


def plot_error_analysis(order_df: pd.DataFrame, out_path: Path, recommended_n: int, min_error_n: int) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(order_df["N"], order_df["abs_relative_length_error"], marker="o", markersize=3, label="|perimeter relative error|")
    ax.plot(order_df["N"], order_df["rmse_normalized"], marker="s", markersize=3, label="normalized RMSE")
    ax.axvline(recommended_n, linestyle=":", label=f"stable N={recommended_n}")
    ax.axvline(min_error_n, linestyle="--", label=f"min-error N={min_error_n}")
    ax.set_xlabel("Fourier order N")
    ax.set_ylabel("error")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170, format="jpg")
    plt.close(fig)


def run_curve_analysis(curve: np.ndarray, out_dir: Path, label: str, samples: int, max_order: int, perimeter_samples: int, slope_tol: float, rmse_tol: float, energy_tol: float, window: int) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    descriptor = FourierDescriptor.from_curve(curve, int(samples))
    order_df = analyze_orders(descriptor, int(max_order), int(perimeter_samples))
    summary = choose_stable_order(order_df, float(slope_tol), float(rmse_tol), float(energy_tol), int(window))
    recommended_n = int(summary["recommended_N"])
    min_error_n = int(summary["min_error_N"])
    max_used_order = int(order_df["N"].max())
    save_curve_csv(out_dir / "drawn_curve_resampled.csv", descriptor.sampled_curve)
    descriptor.coefficient_table().to_csv(out_dir / "fourier_coefficients.csv", index=False)
    order_df.to_csv(out_dir / "order_analysis.csv", index=False)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    plot_curve_comparison(descriptor, candidate_orders(recommended_n, max_used_order), out_dir / "curve_reconstruction.jpg", f"{label}: Fourier reconstruction")
    plot_error_analysis(order_df, out_dir / "error_vs._N.jpg", recommended_n, min_error_n)
    shutil.copyfile(out_dir / "error_vs._N.jpg", out_dir / "error_vs_N.jpg")
    summary = dict(summary)
    summary["label"] = label
    summary["max_used_order"] = max_used_order
    summary["saved_files"] = {
        "curve_csv": "drawn_curve_resampled.csv",
        "coefficients_csv": "fourier_coefficients.csv",
        "order_analysis_csv": "order_analysis.csv",
        "summary_json": "summary.json",
        "curve_reconstruction": "curve_reconstruction.jpg",
        "error_vs_N": "error_vs._N.jpg",
    }
    return summary
