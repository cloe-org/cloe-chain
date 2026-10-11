"""Wrapper for the angular power spectrum likelihoods of
`cloelike.EuclidLikelihood_photo_Cls`: cosmic shear (``WL``), photometric
galaxy clustering (``GCph``), galaxy-galaxy lensing (``GGL``) and their
combinations ``2x2pt`` (GGL + GCph) and ``3x2pt`` (WL + GGL + GCph)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import trapezoid

import euclidlib as el

from cloelike.EuclidLikelihood_photo_Cls import (
    EuclidLikelihood_2x2pt,
    EuclidLikelihood_3x2pt,
    EuclidLikelihood_GCph,
    EuclidLikelihood_GGL,
    EuclidLikelihood_WL,
)

from cloechain.config import PHOTO_BLOCKS, RunConfig
from cloechain.loader import (
    load_background,
    load_nonlinear_perturbations,
    load_perturbations,
)

_LIKELIHOODS = {
    "WL": EuclidLikelihood_WL,
    "GCph": EuclidLikelihood_GCph,
    "GGL": EuclidLikelihood_GGL,
    "2x2pt": EuclidLikelihood_2x2pt,
    "3x2pt": EuclidLikelihood_3x2pt,
}

# Blocks of each probe, in the order cloelike concatenates them in the data
# vector (and so in the covariance): WL, GGL, GCph.
_BLOCKS = {
    "WL": ("WL",),
    "GCph": ("GCph",),
    "GGL": ("GGL",),
    "2x2pt": ("GGL", "GCph"),
    "3x2pt": ("WL", "GGL", "GCph"),
}

# Sampled parameters each baryonic boost reads, passed as `baryon_kwargs`.
_BARYON_BOOST_PARAMETERS = {
    "HMcode2020": ("log10TAGN",),
    "FLAMINGO": ("fgas_sigma", "Mstar_sigma", "jet_fraction"),
}

_PERTURBATIONS_PACKAGES = {
    "CAMB": "camb",
    "HMcode2020Emu": "HMcode2020Emu",
    "EE2": "euclidemu2",
}


def obs_labels(cfg: RunConfig) -> list[str]:
    """Observable bin labels, used to lay out per-redshift nuisance
    parameters. The photometric likelihoods take one scalar parameter per
    tomographic bin instead (see `cloechain.templates`), so there are none.

    Parameters
    ----------
    cfg: RunConfig
        The run's parsed configuration.

    Returns
    -------
    labels: list[str]
        Empty list.
    """
    return []


def _load_nz(path: str, z_grid: np.ndarray) -> np.ndarray:
    """Read the n(z) of every tomographic bin, normalise them and resample
    them on ``z_grid``.

    Parameters
    ----------
    path: str
        Path of the n(z) file.
    z_grid: np.ndarray
        Redshift grid to resample on.

    Returns
    -------
    nz: np.ndarray
        Array of shape ``(n_bins, len(z_grid))``.
    """
    z, nz = el.phz.redshift_distributions(path)
    return np.array(
        [np.interp(z_grid, z, nz[b] / trapezoid(nz[b], z)) for b in sorted(nz)]
    )


def _block_sizes(n_pos: int, n_she: int, n_ell: int) -> dict[str, int]:
    """Length of each block of the data vector.

    Parameters
    ----------
    n_pos: int
        Number of positions bins.
    n_she: int
        Number of shear bins.
    n_ell: int
        Number of multipoles per spectrum.

    Returns
    -------
    sizes: dict[str, int]
    """
    return {
        "WL": n_she * (n_she + 1) // 2 * n_ell,
        "GGL": n_pos * n_she * n_ell,
        "GCph": n_pos * (n_pos + 1) // 2 * n_ell,
    }


def _load_covariance(path: str, key: str | None) -> np.ndarray:
    """Read the covariance matrix from a ``.npz`` or ``.npy`` file.

    Parameters
    ----------
    path: str
        Path of the covariance file.
    key: str or None
        Array to read from a ``.npz`` file, optional if it holds only one.

    Returns
    -------
    covariance: np.ndarray
    """
    suffix = Path(path).suffix
    if suffix == ".npy":
        return np.load(path)
    if suffix != ".npz":
        raise ValueError(
            f"Unsupported covariance file '{path}': expected a .npz or .npy file"
        )
    with np.load(path) as arrays:
        if key is None:
            if len(arrays.files) != 1:
                raise ValueError(
                    f"Covariance file '{path}' holds several arrays "
                    f"{arrays.files}: set 'data.covariance_key'"
                )
            key = arrays.files[0]
        return arrays[key]


def _select_covariance(
    covariance: np.ndarray, kind: str, sizes: dict[str, int]
) -> np.ndarray:
    """Return the covariance of the probe's blocks.

    Parameters
    ----------
    covariance: np.ndarray
        Covariance of either exactly the probe's blocks, or of the full 3x2pt
        data vector (blocks ordered WL, GGL, GCph).
    kind: str
        Probe kind.
    sizes: dict[str, int]
        Length of each block, see `_block_sizes`.

    Returns
    -------
    covariance: np.ndarray
    """
    n_probe = sum(sizes[block] for block in _BLOCKS[kind])
    n_full = sum(sizes[block] for block in _BLOCKS["3x2pt"])
    if covariance.shape == (n_probe, n_probe):
        return covariance
    if covariance.shape != (n_full, n_full):
        raise ValueError(
            f"Covariance of shape {covariance.shape} matches neither the "
            f"{kind} data vector ({n_probe}) nor the 3x2pt one ({n_full})"
        )
    start = 0
    indices = []
    for block in _BLOCKS["3x2pt"]:
        if block in _BLOCKS[kind]:
            indices.append(np.arange(start, start + sizes[block]))
        start += sizes[block]
    indices = np.concatenate(indices)
    return covariance[np.ix_(indices, indices)]


def _build_scale_cuts(cfg: RunConfig, cells: dict) -> dict[tuple, list[float]]:
    """Multipole range of every spectrum of the probe, keyed as the data.

    Parameters
    ----------
    cfg: RunConfig
        The run's parsed configuration.
    cells: dict
        The angular power spectra, keyed as ``("SHE", "SHE", 1, 2)``.

    Returns
    -------
    scale_cuts: dict[tuple, list[float]]
    """
    kind = cfg.probe["kind"]
    missing = [block for block in _BLOCKS[kind] if block not in cfg.scale_cuts]
    if missing:
        raise ValueError(f"'scale_cuts' is missing the range of block(s) {missing}")
    prefixes = {PHOTO_BLOCKS[block]: block for block in _BLOCKS[kind]}
    overrides = cfg.scale_cuts["overrides"]
    unknown = [key for key in overrides if key not in cells]
    if unknown:
        raise ValueError(f"'scale_cuts.overrides' has pairs not in the data: {unknown}")
    return {
        key: overrides.get(key, cfg.scale_cuts[prefixes[key[:2]]])
        for key in cells
        if key[:2] in prefixes
    }


def _build_settings(cfg: RunConfig, scale_cuts: dict) -> dict[str, Any]:
    """Likelihood settings: the config's ``probe.settings``, plus the scale
    cuts and the parameters the chosen baryonic model reads.

    Parameters
    ----------
    cfg: RunConfig
        The run's parsed configuration.
    scale_cuts: dict
        Output of `_build_scale_cuts`.

    Returns
    -------
    settings: dict[str, Any]
    """
    settings = dict(cfg.probe.get("settings", {}))
    settings["scale_cuts"] = scale_cuts
    baryon_boost = cfg.probe.get("baryon_boost")
    if baryon_boost is not None:
        settings.setdefault("nonlinear_param_keys", ())
        settings.setdefault(
            "baryon_param_keys", _BARYON_BOOST_PARAMETERS.get(baryon_boost, ())
        )
    elif cfg.probe["nonlinear_perturbations"] == "EE2":
        # EE2 has no baryonic feedback, unlike cloelike's default (log10TAGN).
        settings.setdefault("nonlinear_param_keys", ())
    return settings


def build_likelihood(cfg: RunConfig):
    """Build the photometric likelihood instance for this run.

    Parameters
    ----------
    cfg: RunConfig
        The run's parsed configuration.

    Returns
    -------
    likelihood: EuclidLikelihood_WL, _GCph, _GGL, _2x2pt or _3x2pt
        The built likelihood instance.
    """
    kind = cfg.probe["kind"]
    data_cfg = cfg.data
    mode = cfg.probe.get("mode", "coupled")
    uses_pos = any("POS" in PHOTO_BLOCKS[block] for block in _BLOCKS[kind])
    uses_she = any("SHE" in PHOTO_BLOCKS[block] for block in _BLOCKS[kind])

    z_grid = np.linspace(
        data_cfg.z_grid["min"], data_cfg.z_grid["max"], int(data_cfg.z_grid["num"])
    )
    dndz_pos = _load_nz(data_cfg.nz_positions, z_grid)
    dndz_she = _load_nz(data_cfg.nz_shear, z_grid)

    cells = el.le3.pk_wl.angular_power_spectra(data_cfg.cells)
    scale_cuts = _build_scale_cuts(cfg, cells)
    ells = np.asarray(cells[next(iter(scale_cuts))].ell)

    sizes = _block_sizes(dndz_pos.shape[0], dndz_she.shape[0], len(ells))
    covariance = _select_covariance(
        _load_covariance(data_cfg.covariance, data_cfg.covariance_key), kind, sizes
    )

    data: dict[str, Any] = {"cells": cells, "ells": ells, "z_arr": z_grid, "cov": covariance}
    if uses_pos:
        data["dndz_pos"] = dndz_pos
    if uses_she:
        data["dndz_she"] = dndz_she
    if mode == "coupled":
        if data_cfg.mixing is None:
            raise ValueError("'data.mixing' is required for 'probe.mode: coupled'")
        data["mixmat"] = el.le3.pk_wl.mixing_matrices(data_cfg.mixing)

    background_name = cfg.probe["background"]
    return _LIKELIHOODS[kind](
        data=data,
        settings=_build_settings(cfg, scale_cuts),
        Background=load_background(background_name),
        LinPerturbations=load_perturbations(
            cfg.probe.get("linear_perturbations", background_name)
        ),
        NonLinPerturbations=load_nonlinear_perturbations(
            cfg.probe["nonlinear_perturbations"], cfg.probe.get("baryon_boost")
        ),
        mode=mode,
    )


def parameter_names(likelihood) -> list[str]:
    """Every parameter name the likelihood reads, used to expand the ``{i}``
    templates of the config (see `cloechain.templates`).

    Parameters
    ----------
    likelihood: EuclidLikelihood_WL, _GCph, _GGL, _2x2pt or _3x2pt
        A likelihood instance built by `build_likelihood`.

    Returns
    -------
    names: list[str]
    """
    names = [
        *likelihood._BACKGROUND_PARAM_KEYS,
        *likelihood.nonlinear_param_keys,
        *likelihood.baryon_param_keys,
    ]
    for attribute in ("full_she_keys", "optional_she_keys", "full_pos_keys", "optional_pos_keys"):
        names.extend(getattr(likelihood, attribute, []))
    return list(dict.fromkeys(names))


def use_noise_free_mock(likelihood, fiducial: dict[str, Any]) -> None:
    """Replace the data vector with the theory at ``fiducial``, so that the
    posterior is centred on it whatever model generated the data file.

    Parameters
    ----------
    likelihood: EuclidLikelihood_WL, _GCph, _GGL, _2x2pt or _3x2pt
        A likelihood instance built by `build_likelihood`.
    fiducial: dict[str, Any]
        Full parameter dictionary of the fiducial point.
    """
    theory = np.asarray(likelihood.get_theory_vector_masked(fiducial))
    likelihood.get_data_vector_masked = lambda: theory


def loglike(likelihood, parameters: dict[str, Any]) -> float:
    """Evaluate log-likelihood on the given parameters.

    Parameters
    ----------
    likelihood: EuclidLikelihood_WL, _GCph, _GGL, _2x2pt or _3x2pt
        An instance of the likelihood.
    parameters: dict[str, Any]
        Full parameter dictionary in the format returned by
        `cloechain.parameters.build_parameter_dict_for_loglike`.

    Returns
    -------
    loglike: float
        The log-likelihood value.
    """
    return float(likelihood.loglike(parameters))


def vector_parameter_names(likelihood) -> set[str]:
    """Return names of nuisance parameters (one value per observable bin).
    The photometric nuisance parameters are scalars, one name per bin.

    Parameters
    ----------
    likelihood: EuclidLikelihood_WL, _GCph, _GGL, _2x2pt or _3x2pt
        A likelihood instance built by `build_likelihood`.

    Returns
    -------
    names: set[str]
        Empty set.
    """
    return set()


def tracked_packages(cfg: RunConfig) -> list[str]:
    """Physics-engine package(s) this run's theory model uses.

    Parameters
    ----------
    cfg: RunConfig
        The run's parsed configuration.

    Returns
    -------
    packages: list[str]
        List of package names to track versions for.
    """
    engines = [
        cfg.probe["background"],
        cfg.probe.get("linear_perturbations", cfg.probe["background"]),
        cfg.probe["nonlinear_perturbations"],
    ]
    packages = [_PERTURBATIONS_PACKAGES[e] for e in engines if e in _PERTURBATIONS_PACKAGES]
    if cfg.probe.get("baryon_boost") == "FLAMINGO":
        packages.append("FlamingoBaryonResponseEmulator")
    settings = cfg.probe.get("settings", {})
    if settings.get("ia_model") == "TATT" or settings.get("galaxy_bias_model") == "nonlinear":
        packages.append("fast-pt")
    return list(dict.fromkeys(packages))
