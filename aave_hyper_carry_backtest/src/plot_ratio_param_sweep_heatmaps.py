from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _load_table(path: Path) -> pd.DataFrame:
    if str(path).lower().endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _nice(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}k"
    return f"{v:.2f}"


def _metric_panel(
    df: pd.DataFrame,
    metric: str,
    out_path: Path,
    title: str,
    cmap: str,
    centered_zero: bool = False,
) -> None:
    levers = sorted(df["hyper_short_leverage"].unique())
    overlays = sorted(df["overlay_borrow_ratio"].unique())
    hypers = sorted(df["hyper_borrow_ratio"].unique())

    n = len(levers)
    ncols = 4
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.1 * ncols, 3.5 * nrows), constrained_layout=True)
    axes = np.atleast_1d(axes).reshape(nrows, ncols)

    vals = df[metric].to_numpy(dtype=float)
    if centered_zero:
        vmax = float(np.nanpercentile(np.abs(vals), 95))
        vmin = -vmax
    else:
        vmin = float(np.nanpercentile(vals, 5))
        vmax = float(np.nanpercentile(vals, 95))
        if np.isclose(vmin, vmax):
            vmin = float(np.nanmin(vals))
            vmax = float(np.nanmax(vals))
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-9

    mappable = None
    for idx, lev in enumerate(levers):
        r = idx // ncols
        c = idx % ncols
        ax = axes[r, c]
        sub = df[df["hyper_short_leverage"] == lev]
        piv = sub.pivot(index="overlay_borrow_ratio", columns="hyper_borrow_ratio", values=metric)
        piv = piv.reindex(index=overlays, columns=hypers)
        arr = piv.to_numpy(dtype=float)
        img = ax.imshow(arr, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        mappable = img

        # mark best cell for this leverage
        best_idx = np.nanargmax(arr)
        br, bc = np.unravel_index(best_idx, arr.shape)
        ax.scatter([bc], [br], marker="*", color="white", s=90, edgecolors="black", linewidths=0.6)

        ax.set_title(f"lev={lev:.2f}")
        ax.set_xticks(np.arange(len(hypers)))
        ax.set_xticklabels([f"{x:.2f}" for x in hypers], rotation=90, fontsize=7)
        ax.set_yticks(np.arange(len(overlays)))
        ax.set_yticklabels([f"{x:.2f}" for x in overlays], fontsize=7)
        ax.set_xlabel("hyper_borrow_ratio")
        ax.set_ylabel("overlay_borrow_ratio")

    for idx in range(len(levers), nrows * ncols):
        r = idx // ncols
        c = idx % ncols
        axes[r, c].axis("off")

    fig.suptitle(title, fontsize=14, fontweight="bold")
    cbar = fig.colorbar(mappable, ax=axes.ravel().tolist(), shrink=0.86, pad=0.01)
    cbar.ax.set_title(metric, fontsize=9)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _max_over_leverage_panel(df: pd.DataFrame, metric: str, out_path: Path, title: str) -> None:
    overlays = sorted(df["overlay_borrow_ratio"].unique())
    hypers = sorted(df["hyper_borrow_ratio"].unique())

    agg = (
        df.sort_values(metric, ascending=False)
        .groupby(["overlay_borrow_ratio", "hyper_borrow_ratio"], as_index=False)
        .first()
    )
    piv_metric = agg.pivot(index="overlay_borrow_ratio", columns="hyper_borrow_ratio", values=metric).reindex(index=overlays, columns=hypers)
    piv_lev = agg.pivot(index="overlay_borrow_ratio", columns="hyper_borrow_ratio", values="hyper_short_leverage").reindex(index=overlays, columns=hypers)

    arr = piv_metric.to_numpy(dtype=float)
    vmin = float(np.nanpercentile(arr, 5))
    vmax = float(np.nanpercentile(arr, 95))
    if np.isclose(vmin, vmax):
        vmin = float(np.nanmin(arr))
        vmax = float(np.nanmax(arr))
    if np.isclose(vmin, vmax):
        vmax = vmin + 1e-9

    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    img = ax.imshow(arr, origin="lower", aspect="auto", cmap="viridis", vmin=vmin, vmax=vmax)

    for i in range(len(overlays)):
        for j in range(len(hypers)):
            v = arr[i, j]
            if np.isnan(v):
                continue
            lev = float(piv_lev.iloc[i, j])
            ax.text(j, i, f"{_nice(v)}\nL{lev:.2f}", ha="center", va="center", fontsize=7, color="white")

    ax.set_title(title)
    ax.set_xticks(np.arange(len(hypers)))
    ax.set_xticklabels([f"{x:.2f}" for x in hypers], rotation=90)
    ax.set_yticks(np.arange(len(overlays)))
    ax.set_yticklabels([f"{x:.2f}" for x in overlays])
    ax.set_xlabel("hyper_borrow_ratio")
    ax.set_ylabel("overlay_borrow_ratio")
    cb = fig.colorbar(img, ax=ax, shrink=0.86)
    cb.ax.set_title(metric, fontsize=9)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot heatmaps for ratio-structure parameter sweep results")
    parser.add_argument("--input", required=True, help="Path to grid_results.parquet/csv")
    parser.add_argument("--out-dir", default="", help="Output directory")
    args = parser.parse_args()

    src = Path(args.input)
    df = _load_table(src)
    required = {"overlay_borrow_ratio", "hyper_borrow_ratio", "hyper_short_leverage", "end_equity", "net_carry_pnl"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing columns in input: {sorted(missing)}")

    out_dir = Path(args.out_dir) if args.out_dir else src.parent / "heatmaps"
    out_dir.mkdir(parents=True, exist_ok=True)

    _metric_panel(
        df=df,
        metric="end_equity",
        out_path=out_dir / "heatmap_facets_end_equity.png",
        title="End Equity by (overlay, hyper) for each leverage",
        cmap="viridis",
        centered_zero=False,
    )
    _metric_panel(
        df=df,
        metric="net_carry_pnl",
        out_path=out_dir / "heatmap_facets_net_carry_pnl.png",
        title="Net Carry PnL by (overlay, hyper) for each leverage",
        cmap="coolwarm",
        centered_zero=True,
    )
    _metric_panel(
        df=df,
        metric="min_health_factor",
        out_path=out_dir / "heatmap_facets_min_health_factor.png",
        title="Min Health Factor by (overlay, hyper) for each leverage",
        cmap="magma",
        centered_zero=False,
    )
    _max_over_leverage_panel(
        df=df,
        metric="end_equity",
        out_path=out_dir / "heatmap_max_over_leverage_end_equity.png",
        title="Best End Equity over leverage (text shows best metric and leverage)",
    )
    _max_over_leverage_panel(
        df=df,
        metric="net_carry_pnl",
        out_path=out_dir / "heatmap_max_over_leverage_net_carry_pnl.png",
        title="Best Net Carry PnL over leverage (text shows best metric and leverage)",
    )

    print(f"saved heatmaps to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
