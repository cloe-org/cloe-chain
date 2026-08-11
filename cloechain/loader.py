"""Loader of different backends for probes, samplers, relations, etc.
"""

from __future__ import annotations

import importlib
from typing import Any

PROBES: dict[str, str] = {
    "GCspectro_Pls": "cloechain.probes.gcspectro_pls",
    "GCspectro_BAO": "cloechain.probes.gcspectro_bao",
    "GCspectro_Pls_BAO": "cloechain.probes.gcspectro_pls_bao",
}

SAMPLERS: dict[str, str] = {
    "nautilus": "cloechain.samplers.nautilus_runner",
}

CONSTRAINTS: dict[str, str] = {
    "negative_w0_wa_sum": "cloechain.constraints:w0_wa_negative",
}

DERIVED_PARAMETERS: dict[str, dict[str, str]] = {
    "bG2_coevolution": {
        "path": "cloechain.derived_parameters:bG2_coevolution",
    },
    "bG2_excursion_set": {
        "path": "cloechain.derived_parameters:bG2_excursion_set",
    },
    "bGam3_coevolution": {
        "path": "cloechain.derived_parameters:bGam3_coevolution",
    },
    "H0_from_h": {
        "path": "cloechain.derived_parameters:H0_from_h", "trigger": "h",
    },
    "Omega_cdm0_from_omch2": {
        "path": "cloechain.derived_parameters:Omega_cdm0_from_omch2", "trigger": "omch2",
    },
    "Omega_b0_from_ombh2": {
        "path": "cloechain.derived_parameters:Omega_b0_from_ombh2", "trigger": "ombh2",
    },
    "As_from_logA": {
        "path": "cloechain.derived_parameters:As_from_logA", "trigger": "logA",
    },
}

BACKGROUNDS: dict[str, str] = {
    "CAMB": "cloelib.cosmology.camb_cosmology:CAMBBackground",
}

PERTURBATIONS: dict[str, str] = {
    "CAMB": "cloelib.cosmology.camb_cosmology:CAMBLinearPerturbations",
}

SPECTRO_POWERS: dict[str, dict[str, str]] = {
    "COMET": {
        "EFT": "cloelib.observables.CometEFT_spectro:CometEFT_SpectroPower",
        "VDG": "cloelib.observables.CometVDG_spectro:CometVDG_SpectroPower",
    },
    "PBJ": {
        "EFT": "cloelib.observables.PBJ_spectro:PBJSpectroPower",
    },
}


def load_from_path(path: str) -> Any:
    """Import attribute/module and return it.

    Parameters
    ----------
    path: str
        Dotted path to a module, in the form ``"module.submodule"``, or to an
        attribute inside a module, in the form ``"module.submodule:attr"``.

    Returns
    -------
    obj: Any
        The imported module, or the attribute inside it if ``path`` ends with ``":attr"``.
    """
    module_name, _, attr_name = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr_name) if attr_name else module


def load_probe(kind: str):
    """Return the module associated to the requested probe kind.

    Parameters
    ----------
    kind: str
        Probe name, to be specified in the config's ``probe.kind``.

    Returns
    -------
    probe: module
        The specified probe module.
    """
    if kind not in PROBES:
        raise KeyError(
            f"Unknown probe kind '{kind}'. Registered probes: {sorted(PROBES)}"
        )
    return load_from_path(PROBES[kind])


def load_background(name: str):
    """Return the background class associated to the requested name.

    Parameters
    ----------
    name: str
        Background name, i.e. the config's ``probe.background``.

    Returns
    -------
    background: type
        Type of Background class.
    """
    if name not in BACKGROUNDS:
        raise KeyError(
            f"Unknown background '{name}'. Registered backgrounds: {sorted(BACKGROUNDS)}"
        )
    return load_from_path(BACKGROUNDS[name])


def load_perturbations(name: str):
    """Return the linear-perturbations class associated to the requested name.

    Parameters
    ----------
    name: str
        Linear perturbationsname, i.e. the config's ``probe.background`` (same to background
        as they are tied together).

    Returns
    -------
    perturbations: type
        Type of LinearPerturbations class.
    """
    if name not in PERTURBATIONS:
        raise KeyError(
            f"Unknown background '{name}'. Registered backgrounds with a "
            f"Perturbations class: {sorted(PERTURBATIONS)}"
        )
    return load_from_path(PERTURBATIONS[name])


def load_spectro_power(code: str, rsd_model: str | None = None):
    """Return the SpectroPower class registered under ``code``/``rsd_model``.

    Parameters
    ----------
    code: str
        External code name, i.e. the config's ``probe.spectro_power.code``.
    rsd_model: str or None
        RSD model, i.e. the config's ``probe.spectro_power.rsd_model``.

    Returns
    -------
    spectro_power: type
        Type of SpectroPower class.
    """
    if code not in SPECTRO_POWERS:
        raise KeyError(
            f"Unknown spectro_power code '{code}'. Registered codes: {sorted(SPECTRO_POWERS)}"
        )
    models = SPECTRO_POWERS[code]
    if rsd_model not in models:
        raise KeyError(
            f"Unknown rsd_model '{rsd_model}' for code '{code}'. "
            f"Registered rsd_models: {sorted(models)}"
        )
    return load_from_path(models[rsd_model])


def load_constraint(name: str):
    """Return the function to obtain the constraint specified in input.

    Parameters
    ----------
    name: str
        Constraint name, one of the config's ``constraints`` keys.

    Returns
    -------
    constraint: Callable[[dict], bool]
        The specified constraint function.
    """
    if name not in CONSTRAINTS:
        raise KeyError(
            f"Unknown constraint '{name}'. Registered constraints: {sorted(CONSTRAINTS)}"
        )
    return load_from_path(CONSTRAINTS[name])


def load_derived_parameter(name: str):
    """Return the function to convert from the input to the internal set of parameters.

    Parameters
    ----------
    name: str
        Derived-parameter relation name, one of the config's
        ``derived_parameters`` keys.

    Returns
    -------
    derived: Callable[[dict], None]
        The specified derived-parameter function.
    """
    if name not in DERIVED_PARAMETERS:
        raise KeyError(
            f"Unknown derived parameter '{name}'. Registered derived "
            f"parameters: {sorted(DERIVED_PARAMETERS)}"
        )
    return load_from_path(DERIVED_PARAMETERS[name]["path"])


def load_sampler(kind: str):
    """Return the module associated to the requested sampler kind.

    Parameters
    ----------
    kind: str
        Sampler name, to be specified in the config's ``sampler.kind``.

    Returns
    -------
    sampler: module
        The specified sampler module.
    """
    if kind not in SAMPLERS:
        raise KeyError(
            f"Unknown sampler kind '{kind}'. Registered samplers: {sorted(SAMPLERS)}"
        )
    return load_from_path(SAMPLERS[kind])
