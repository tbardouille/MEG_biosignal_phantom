
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Literal, Optional, Tuple

import time
import numpy as np
import scipy.optimize as so
import mne

MU0 = 4e-7 * np.pi


@dataclass(frozen=True)
class ECDGeometry:
    """Cached MEG coil integration geometry."""
    R: np.ndarray
    N: np.ndarray
    W: np.ndarray
    ch_ptr: np.ndarray
    n_ch: int
    ch_names: Tuple[str, ...]


@dataclass(frozen=True)
class ECDResult:
    """ECD fit output."""
    pos_m: np.ndarray
    moment_A_m: np.ndarray
    gof: float
    sse: float
    meta: Dict[str, Any]


def build_ecd_geometry(
    info: mne.Info,
    *,
    picks: Optional[Iterable[int]] = None,
    acc: Literal["accurate", "normal"] = "accurate",
) -> ECDGeometry:
    """Build coil integration geometry. y must match this channel order."""
    if picks is not None:
        info = mne.pick_info(info, sel=np.array(list(picks), dtype=int), copy=True)

    coils = mne.chpi._create_meg_coils(info["chs"], acc)
    n_ch = len(coils)

    R_list: list[np.ndarray] = []
    N_list: list[np.ndarray] = []
    W_list: list[np.ndarray] = []
    ch_list: list[np.ndarray] = []

    for ci, coil in enumerate(coils):
        rmag = np.asarray(coil["rmag"], dtype=float)
        cosmag = np.asarray(coil["cosmag"], dtype=float)
        w = np.asarray(coil["w"], dtype=float)

        R_list.append(rmag)
        N_list.append(cosmag)
        W_list.append(w)
        ch_list.append(np.full(rmag.shape[0], ci, dtype=np.int32))

    R = np.vstack(R_list)
    N = np.vstack(N_list)
    W = np.concatenate(W_list)
    ch_ptr = np.concatenate(ch_list)

    return ECDGeometry(
        R=R,
        N=N,
        W=W,
        ch_ptr=ch_ptr,
        n_ch=n_ch,
        ch_names=tuple(info["ch_names"]),
    )


def _bcoef_from_basis(D: np.ndarray) -> np.ndarray:
    """Cross(e_axis, D) for axis in {x,y,z}, vectorized over points."""
    Dx = D[:, 0]
    Dy = D[:, 1]
    Dz = D[:, 2]

    C = np.empty((D.shape[0], 3, 3), dtype=float)

    C[:, 0, 0] = 0.0
    C[:, 0, 1] = -Dz
    C[:, 0, 2] = Dy

    C[:, 1, 0] = Dz
    C[:, 1, 1] = 0.0
    C[:, 1, 2] = -Dx

    C[:, 2, 0] = -Dy
    C[:, 2, 1] = Dx
    C[:, 2, 2] = 0.0

    return C


def leadfield_current_dipole(pos_m: np.ndarray, geom: ECDGeometry) -> np.ndarray:
    """
    Current dipole leadfield (infinite medium), integrated over coils:
        B(R) = (mu0/4pi) * (q x (R-r0)) / ||R-r0||^3
    Returns G with shape (n_ch, 3).
    """
    pos_m = np.asarray(pos_m, dtype=float).reshape(3)

    D = geom.R - pos_m[None, :]
    r = np.linalg.norm(D, axis=1)
    inv_r3 = 1.0 / np.maximum(r, 1e-12) ** 3
    scale = (MU0 / (4.0 * np.pi)) * inv_r3

    C = _bcoef_from_basis(D)
    dotCN = np.einsum("paj,pj->pa", C, geom.N)
    meas_points = (geom.W[:, None] * scale[:, None]) * dotCN

    G = np.empty((geom.n_ch, 3), dtype=float)
    for ax in range(3):
        G[:, ax] = np.bincount(geom.ch_ptr, weights=meas_points[:, ax], minlength=geom.n_ch)
    return G


def _solve_moment_and_sse(y: np.ndarray, G: np.ndarray, *, reg: float, yTy: float) -> Tuple[np.ndarray, float]:
    """Solve q and SSE for y ≈ G q."""
    GTG0 = G.T @ G
    GTy = G.T @ y

    GTG = GTG0 + (reg * np.eye(3, dtype=float)) if reg > 0.0 else GTG0
    try:
        q = np.linalg.solve(GTG, GTy)
    except np.linalg.LinAlgError:
        q = np.linalg.lstsq(G, y, rcond=None)[0]

    sse = float(yTy - 2.0 * (q @ GTy) + (q @ (GTG0 @ q)))
    return q, sse


def _make_grid(bounds_m: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]], step_m: float) -> np.ndarray:
    (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds_m
    xs = np.arange(xmin, xmax + 1e-12, step_m, dtype=float)
    ys = np.arange(ymin, ymax + 1e-12, step_m, dtype=float)
    zs = np.arange(zmin, zmax + 1e-12, step_m, dtype=float)
    return np.array(np.meshgrid(xs, ys, zs, indexing="ij"), dtype=float).reshape(3, -1).T


def _clamp_bounds(
    local: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
    global_: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    out = []
    for (l0, l1), (g0, g1) in zip(local, global_):
        out.append((max(g0, l0), min(g1, l1)))
    return (out[0], out[1], out[2])


def _local_bounds(center: np.ndarray, halfwidth: float) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    cx, cy, cz = center
    return ((cx - halfwidth, cx + halfwidth),
            (cy - halfwidth, cy + halfwidth),
            (cz - halfwidth, cz + halfwidth))


def fit_ecd(
    y: np.ndarray,
    info: mne.Info,
    *,
    noise_cov: Optional[mne.Covariance] = None,
    whiten_rank: RankArg = "info",
    bounds_m: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]] = ((-0.20, 0.20), (-0.20, 0.20), (-0.20, 0.20)),
    geom: Optional[ECDGeometry] = None,
    acc: Literal["accurate", "normal"] = "accurate",
    reg: float = 0.0,
    coarse_step_m: float = 0.02,
    fine_halfwidth_m: float = 0.02,
    fine_step_m: float = 0.005,
    very_fine_halfwidth_m: float = 0.005,
    very_fine_step_m: float = 0.001,
    refine: bool = True,
    optimizer_maxiter: int = 200,
    ftol: float = 1e-14,
    gtol: float = 1e-10,
    top_k_starts: int = 1,
    collect_stage_metrics: bool = True,
) -> ECDResult:
    """Fit one dipole position to one or multiple time points."""
    t_total0 = time.perf_counter()

    y = np.asarray(y, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    elif y.ndim != 2:
        raise ValueError("y must be shape (n_ch,) or (n_ch, n_t)")

    n_ch = int(y.shape[0])
    n_t = int(y.shape[1])
    t_center = int(n_t // 2)

    if geom is None:
        geom = build_ecd_geometry(info, acc=acc)

    if tuple(info["ch_names"]) != geom.ch_names:
        raise ValueError("Channel name/order mismatch between info and geometry.")

    if n_ch != geom.n_ch:
        raise ValueError(f"y n_ch ({n_ch}) does not match geom.n_ch ({geom.n_ch}).")

    safe_false = mne.utils._verbose_safe_false()
    cov = noise_cov

    # Why: whitening stability depends on correct rank.
    whitener, _ = mne.cov.compute_whitener(cov, info, rank=whiten_rank, verbose=safe_false)
    W = np.asarray(whitener, dtype=float)

    y = W @ y  # whitened data

    y_mean_t = np.mean(y, axis=0)
    y0 = y - y_mean_t[None, :]
    sst_t = np.sum(y0 * y0, axis=0) + 1e-30

    timing_ms: Dict[str, float] = {}
    n_eval: Dict[str, int] = {}
    stage_best: Dict[str, Dict[str, Any]] = {}

    def gof_by_time(y_hat: np.ndarray) -> np.ndarray:
        y_hat_mean_t = np.mean(y_hat, axis=0)
        resid0 = (y) - (y_hat)
        sse0_t = np.sum(resid0 * resid0, axis=0)
        return 1.0 - (sse0_t / sst_t)

    def solve_time_stack(G_w: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
            # One shared q across all time points:
            #   argmin_q Σ_t ||y_t - G_w q||^2 + reg*||q||^2
            # Closed-form using sums (stable + fast).
            y_sum = np.sum(y, axis=1)  # (n_ch,)
            GTG = G_w.T @ G_w
            A = (n_t * GTG) + (reg * np.eye(3))
            b = G_w.T @ y_sum
            q_shared = np.linalg.solve(A, b)  # (3,)

            y_hat = G_w @ q_shared  # (n_ch,)
            resid = y - y_hat[:, None]
            sse_sum = float(np.sum(resid * resid))

            q_all = np.tile(q_shared[:, None], (1, n_t))
            return q_shared.copy(), sse_sum, q_all

    def consider_best(stage: str, pos: np.ndarray, q_all: np.ndarray, sse_sum: float, G_w: np.ndarray) -> None:
        if not collect_stage_metrics:
            return
        y_hat = G_w @ q_all
        stage_best[stage] = {
            "pos_m": pos.copy(),
            "sse": float(sse_sum),
            "gof": float(np.mean(gof_by_time(y_hat))),
        }

    # Coarse grid
    t0 = time.perf_counter()
    grid = _make_grid(bounds_m, coarse_step_m)
    n_eval["coarse"] = int(grid.shape[0])

    best_sse = np.inf
    best_pos = grid[0].copy()
    best_q_all = np.zeros((3, n_t), dtype=float)
    scored: list[tuple[float, np.ndarray, np.ndarray]] = []

    for pos in grid:
        G_w = W @ leadfield_current_dipole(pos, geom)
        _, sse_sum, q_all = solve_time_stack(G_w)
        scored.append((sse_sum, pos, q_all))
        if sse_sum < best_sse:
            best_sse = sse_sum
            best_pos = pos.copy()
            best_q_all = q_all.copy()
            consider_best("coarse", best_pos, best_q_all, best_sse, G_w)

    timing_ms["coarse_grid"] = (time.perf_counter() - t0) * 1000.0
    scored.sort(key=lambda t: t[0])
    starts = [p.copy() for _, p, _ in scored[: max(1, int(top_k_starts))]]

    # Fine grids
    def run_local_grid(stage_name: str, center: np.ndarray, halfwidth: float, step: float) -> Tuple[np.ndarray, np.ndarray, float]:
        local = _clamp_bounds(_local_bounds(center, halfwidth), bounds_m)
        g = _make_grid(local, step)
        n_eval[stage_name] = n_eval.get(stage_name, 0) + int(g.shape[0])

        local_best_sse = np.inf
        local_best_pos = center.copy()
        local_best_q_all = np.zeros((3, n_t), dtype=float)

        for pos in g:
            G_w = W @ leadfield_current_dipole(pos, geom)
            _, sse_sum, q_all = solve_time_stack(G_w)
            if sse_sum < local_best_sse:
                local_best_sse = sse_sum
                local_best_pos = pos.copy()
                local_best_q_all = q_all.copy()
                consider_best(stage_name, local_best_pos, local_best_q_all, local_best_sse, G_w)
        return local_best_pos, local_best_q_all, float(local_best_sse)

    t0 = time.perf_counter()
    best_sse = np.inf
    best_pos = starts[0].copy()
    best_q_all = np.zeros((3, n_t), dtype=float)

    for s in starts:
        pos_f, q_f, _ = run_local_grid("fine", s, fine_halfwidth_m, fine_step_m)
        pos_v, q_v, sse_v = run_local_grid("very_fine", pos_f, very_fine_halfwidth_m, very_fine_step_m)
        if sse_v < best_sse:
            best_sse = sse_v
            best_pos = pos_v.copy()
            best_q_all = q_v.copy()

    timing_ms["fine_grid"] = (time.perf_counter() - t0) * 1000.0

    # Continuous refinement
    t0 = time.perf_counter()

    def obj(pos_vec: np.ndarray) -> float:
        pos = np.asarray(pos_vec, dtype=float)
        G_w = W @ leadfield_current_dipole(pos, geom)
        _, sse_sum, _ = solve_time_stack(G_w)
        return float(sse_sum)

    opt_meta: Dict[str, Any] = {"refine": bool(refine)}
    if refine:
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds_m
        res = so.minimize(
            obj,
            x0=best_pos,
            method="L-BFGS-B",
            bounds=((xmin, xmax), (ymin, ymax), (zmin, zmax)),
            options={"maxiter": int(optimizer_maxiter), "ftol": float(ftol), "gtol": float(gtol)},
        )
        opt_meta.update(
            status=int(res.status),
            success=bool(res.success),
            message=str(res.message),
            nfev=int(getattr(res, "nfev", -1)),
            nit=int(getattr(res, "nit", -1)),
            fun=float(res.fun),
        )
        n_eval["refine_nfev"] = int(opt_meta["nfev"])
        best_pos = np.asarray(res.x, dtype=float)

    timing_ms["refine"] = (time.perf_counter() - t0) * 1000.0

    # Final metrics
    G_w = W @ leadfield_current_dipole(best_pos, geom)
    q_center, best_sse, q_all = solve_time_stack(G_w)
    y_hat = G_w @ q_all
    gof_t = gof_by_time(y_hat)
    gof_avg = float(np.mean(gof_t))

    if collect_stage_metrics:
        stage_best["final"] = {"pos_m": best_pos.copy(), "sse": float(best_sse), "gof": float(gof_avg)}

    timing_ms["total_fit"] = (time.perf_counter() - t_total0) * 1000.0

    meta: Dict[str, Any] = {
        **opt_meta,
        "timing_ms": timing_ms,
        "n_eval": n_eval,
        "stage_best": stage_best,
        "gof_by_time": gof_t.tolist(),
        "gof_avg": float(gof_avg),
        "t_center": int(t_center),
    }

    return ECDResult(
        pos_m=best_pos,
        moment_A_m=q_center,
        gof=float(gof_avg),
        sse=float(best_sse),
        meta=meta,
    )


def fit_ecd_leastsq(
    y: np.ndarray,
    info: mne.Info,
    *,
    init_pos_m: np.ndarray,
    whiten_rank: RankArg = "info",
    noise_cov: Optional[mne.Covariance] = None,
    geom: Optional[ECDGeometry] = None,
    acc: Literal["accurate", "normal"] = "accurate",
    reg: float = 0.0,
    bounds: Optional[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]] = None,
    optimizer_maxiter: int = 200,
    ftol: float = 1e-15,
    gtol: float = 1e-15,
    collect_stage_metrics: bool = True,
) -> ECDResult:
    """
    Fit one dipole position using ONLY continuous optimization (scipy.optimize.least_squares).

    Same inputs/outputs as before.
    """
    t_total0 = time.perf_counter()

    y = np.asarray(y, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    elif y.ndim != 2:
        raise ValueError("y must be shape (n_ch,) or (n_ch, n_t)")

    init_pos_m = np.asarray(init_pos_m, dtype=float).reshape(3)

    n_ch = int(y.shape[0])
    n_t = int(y.shape[1])
    t_center = int(n_t // 2)

    if geom is None:
        geom = build_ecd_geometry(info, acc=acc)

    if len(info["ch_names"]) != geom.n_ch:
        raise ValueError(
            f"info['ch_names'] length ({len(info['ch_names'])}) does not match geom.n_ch ({geom.n_ch}). "
            "Use the same picked info to build geometry and y."
        )

    if tuple(info["ch_names"]) != geom.ch_names:
        bad = [(i, a, b) for i, (a, b) in enumerate(zip(info["ch_names"], geom.ch_names)) if a != b]
        raise ValueError(
            "Channel name/order mismatch between info and geometry. "
            f"First mismatches: {bad[:10]}"
        )

    if n_ch != geom.n_ch:
        raise ValueError(f"y n_ch ({n_ch}) does not match geom.n_ch ({geom.n_ch}).")

    safe_false = mne.utils._verbose_safe_false()

    if noise_cov is None:
        W = np.eye(len(info["ch_names"]), dtype=float)
    else:
        whitener, _ = mne.cov.compute_whitener(noise_cov, info, rank=whiten_rank, verbose=safe_false)
        W = np.asarray(whitener, dtype=float)

    y = W @ y  
    sst_t = np.sum(y * y, axis=0) + 1e-30
    print(sst_t)

    timing_ms: Dict[str, float] = {}
    stage_best: Dict[str, Dict[str, Any]] = {}

    def gof_by_time(y_hat: np.ndarray) -> np.ndarray:
        
        resid0 = (y) - (y_hat)
        sse0_t = np.sum(resid0* resid0, axis=0)
        return 1.0 - (sse0_t / sst_t)

    def solve_time_stack(G_w: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray]:
            # One shared q across all time points:
            #   argmin_q Σ_t ||y_t - G_w q||^2 + reg*||q||^2
            # Closed-form using sums (stable + fast).
            y_sum = np.sum(y, axis=1)  # (n_ch,)
            GTG = G_w.T @ G_w
            A = (n_t * GTG) + (reg * np.eye(3))
            b = G_w.T @ y_sum
            q_shared = np.linalg.solve(A, b)  # (3,)

            y_hat = G_w @ q_shared  # (n_ch,)
            resid = y - y_hat[:, None]
            sse_sum = float(np.sum(resid * resid))

            q_all = np.tile(q_shared[:, None], (1, n_t))
            return q_shared.copy(), sse_sum, q_all, resid

    def residuals(pos_vec: np.ndarray) -> np.ndarray:
        pos = np.asarray(pos_vec, dtype=float).reshape(3)
        G_w = W @ leadfield_current_dipole(pos, geom)
        _, _, _, resid = solve_time_stack(G_w)
        return resid.reshape(-1)

    # least sq
    t0 = time.perf_counter()

    if bounds is None:
        lb = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
        ub = np.array([np.inf, np.inf, np.inf], dtype=float)
        method = "lm"  # fastest unconstrained
    else:
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
        lb = np.array([xmin, ymin, zmin], dtype=float)
        ub = np.array([xmax, ymax, zmax], dtype=float)
        method = "trf"

    res = so.least_squares(
        residuals,
        x0=init_pos_m,
        bounds=(lb, ub),
        method=method,
        max_nfev=int(optimizer_maxiter),
        ftol=float(ftol),
        gtol=float(gtol),
        xtol=float(ftol),
    )

    timing_ms["least_squares"] = (time.perf_counter() - t0) * 1000.0

    best_pos = np.asarray(res.x, dtype=float).reshape(3)

# metrics

    G_w = W @ leadfield_current_dipole(best_pos, geom)
    q_center, best_sse, q_all, _ = solve_time_stack(G_w)

    y_hat = G_w @ q_all
    gof_t = gof_by_time(y_hat)

    if gof_t.size == 3:
        print(f"GOFs at time: -1ms = {gof_t[0]:.4f}, 0ms = {gof_t[1]:.4f}, 1ms = {gof_t[2]:.4f}")
    else:
        gof_str = ", ".join(f"t{ti}={g:.4f}" for ti, g in enumerate(gof_t.tolist()))
        print(f"GOFs by time ({gof_t.size}): {gof_str}")

    gof_avg = float(np.mean(gof_t))

   

    if collect_stage_metrics:
        stage_best["final"] = {"pos_m": best_pos.copy(), "sse": float(best_sse), "gof": float(gof_avg)}

    timing_ms["total_fit"] = (time.perf_counter() - t_total0) * 1000.0

    meta: Dict[str, Any] = {
        "refine": True,
        "method": f"least_squares({method})",
        "status": int(getattr(res, "status", -1) or -1),
        "success": bool(getattr(res, "success", False)),
        "message": str(getattr(res, "message", "")),
        "nfev": int(getattr(res, "nfev", -1) or -1),
        "njev": int(getattr(res, "njev", -1) or -1),  # <-- fix None
        "cost": float(getattr(res, "cost", np.nan)),
        "fun": float(best_sse),
        "timing_ms": timing_ms,
        "stage_best": stage_best,
        "gof_by_time": gof_t.tolist(),
        "gof_avg": float(gof_avg),
        "t_center": int(t_center),
    }


    return ECDResult(
        pos_m=best_pos,
        moment_A_m=q_center,
        gof=float(gof_avg),
        sse=float(best_sse),
        meta=meta,
    )

### Function used in report.

def fit_ecd_leastsq_scaled(
    y: np.ndarray,
    info: mne.Info,
    *,
    init_pos_m: np.ndarray,
    whiten_rank: RankArg = "info",
    noise_cov: Optional[mne.Covariance] = None,
    geom: Optional[ECDGeometry] = None,
    acc: Literal["accurate", "normal"] = "accurate",
    reg: float = 0.0,
    bounds: Optional[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]] = None,
    optimizer_maxiter: int = 200,
    ftol: float = 1e-12,
    gtol: float = 1e-12,
    collect_stage_metrics: bool = True,
) -> ECDResult:
    """
    Same as fit_ecd_leastsq, but rescales y to avoid numerical "bottoming out"
    when ||y||^2 ~ 1e-24 in physical units.

    Position optimum is unchanged by scalar scaling; q and SSE are unscaled back.
    """
    t_total0 = time.perf_counter()

    y = np.asarray(y, dtype=float)
    if y.ndim == 1:
        y = y.reshape(-1, 1)
    elif y.ndim != 2:
        raise ValueError("y must be shape (n_ch,) or (n_ch, n_t)")

    init_pos_m = np.asarray(init_pos_m, dtype=float).reshape(3)

    n_ch = int(y.shape[0])
    n_t = int(y.shape[1])
    t_center = int(n_t // 2)

    if geom is None:
        geom = build_ecd_geometry(info, acc=acc)

    if tuple(info["ch_names"]) != geom.ch_names:
        bad = [(i, a, b) for i, (a, b) in enumerate(zip(info["ch_names"], geom.ch_names)) if a != b]
        raise ValueError("Channel name/order mismatch between info and geometry. "
                         f"First mismatches: {bad[:10]}")

    if n_ch != geom.n_ch:
        raise ValueError(f"y n_ch ({n_ch}) does not match geom.n_ch ({geom.n_ch}).")

    safe_false = mne.utils._verbose_safe_false()

    if noise_cov is None:
        W = np.eye(len(info["ch_names"]), dtype=float)
    else:
        
        whitener, _ = mne.cov.compute_whitener(noise_cov, info, rank=whiten_rank, verbose=safe_false)
        W = np.asarray(whitener, dtype=float)

    y = W @ y

    
    y_rms = float(np.sqrt(np.mean(y * y)) + 1e-30)
    data_scale = 1.0 / y_rms
    y = y * data_scale

    # GOF terms 
    sst_t = np.sum(y * y, axis=0) + 1e-30

    timing_ms: Dict[str, float] = {}
    stage_best: Dict[str, Dict[str, Any]] = {}

    def gof_by_time(y_hat: np.ndarray) -> np.ndarray:
        resid = y - y_hat
        sse_t = np.sum(resid * resid, axis=0)
        return 1.0 - (sse_t / sst_t)

    def solve_time_stack(G_w: np.ndarray) -> Tuple[np.ndarray, float, np.ndarray, np.ndarray]:
        y_sum = np.sum(y, axis=1)  # (n_ch,)
        GTG = G_w.T @ G_w
        A = (n_t * GTG) + (reg * np.eye(3))
        b = G_w.T @ y_sum
        q_shared = np.linalg.solve(A, b)

        y_hat_1 = G_w @ q_shared
        resid = y - y_hat_1[:, None]
        sse_sum = float(np.sum(resid * resid))

        q_all = np.tile(q_shared[:, None], (1, n_t))
        return q_shared.copy(), sse_sum, q_all, resid

    def residuals(pos_vec: np.ndarray) -> np.ndarray:
        pos = np.asarray(pos_vec, dtype=float).reshape(3)
        G_w = W @ leadfield_current_dipole(pos, geom)
        _, _, _, resid = solve_time_stack(G_w)
        return resid.reshape(-1)

    t0 = time.perf_counter()

    
    if bounds is None:
        lb = np.array([-np.inf, -np.inf, -np.inf], dtype=float)
        ub = np.array([np.inf, np.inf, np.inf], dtype=float)
    else:
        (xmin, xmax), (ymin, ymax), (zmin, zmax) = bounds
        lb = np.array([xmin, ymin, zmin], dtype=float)
        ub = np.array([xmax, ymax, zmax], dtype=float)

    res = so.least_squares(
        residuals,
        x0=init_pos_m,
        bounds=(lb, ub),
        method="trf", # slightly better for this problem
        max_nfev=int(optimizer_maxiter),
        ftol=float(ftol),
        gtol=float(gtol),
        xtol=float(ftol),
        x_scale=0.01,      # meters-scale step guidance (~1 cm)
        diff_step=1e-4,    
    )

    timing_ms["least_squares"] = (time.perf_counter() - t0) * 1000.0

    best_pos = np.asarray(res.x, dtype=float).reshape(3)

    # Final metrics
    G_w = W @ leadfield_current_dipole(best_pos, geom)
    q_center, best_sse, q_all, _ = solve_time_stack(G_w)

    y_hat = G_w @ q_all
    gof_t = gof_by_time(y_hat)
    gof_avg = float(np.mean(gof_t))

    # Unscale
    q_center = q_center / data_scale
    best_sse = float(best_sse / (data_scale * data_scale))

    if collect_stage_metrics:
        stage_best["final"] = {"pos_m": best_pos.copy(), "sse": float(best_sse), "gof": float(gof_avg)}

    timing_ms["total_fit"] = (time.perf_counter() - t_total0) * 1000.0

    meta: Dict[str, Any] = {
        "refine": True,
        "method": "least_squares(trf, scaled_y)",
        "status": int(getattr(res, "status", -1) or -1),
        "success": bool(getattr(res, "success", False)),
        "message": str(getattr(res, "message", "")),
        "nfev": int(getattr(res, "nfev", -1) or -1),
        "njev": int(getattr(res, "njev", -1) or -1),
        "cost": float(getattr(res, "cost", np.nan)),
        "fun": float(best_sse),
        "timing_ms": timing_ms,
        "stage_best": stage_best,
        "gof_by_time": gof_t.tolist(),
        "gof_avg": float(gof_avg),
        "t_center": int(t_center),
        "data_rms_before_scale": float(y_rms),
        "data_scale_applied": float(data_scale),
    }

    return ECDResult(
        pos_m=best_pos,
        moment_A_m=q_center,
        gof=float(gof_avg),
        sse=float(best_sse),
        meta=meta,
    )
