"""Main reader for a cloechain config yaml file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from cloechain.loader import DERIVED_PARAMETERS

REQUIRED_SECTIONS = (
    "probe", "data", "fixed_parameters", "sampled_parameters", "sampler", "output",
)


def _redshift_label(z: float) -> str:
    """Label a redshift according to a naming convention (with no trailing zeros).

    Parameters
    ----------
    z: float
        Redshift value.

    Returns
    -------
    label: str
        Literal string representing the redshift, with no trailing zeros on the right.
    """
    return str(z).rstrip("0")


def _check_redshift_keys_match(keys: set, data: DataConfig, label: str) -> None:
    """Raise an error if ``keys`` does not coincide with the expected redshift keys.

    Parameters
    ----------
    keys: set
        Keys specified in a config section/spec.
    data: DataConfig
        The resolved ``data`` section.
    label: str
        Name of the section/spec, used in the error message.
    """
    expected = set(data.redshifts)
    if keys != expected:
        missing = sorted(expected - keys)
        unexpected = sorted(keys - expected)
        parts = []
        if missing: parts.append(f"missing {missing}")
        if unexpected: parts.append(f"unexpected {unexpected}")
        detail = ", ".join(parts)
        raise ValueError(
            f"'{label}' keys must match 'data.redshifts' {sorted(expected)} "
            f"exactly: {detail}"
        )


def _parse_scale_cuts(scale_cuts: dict[float, Any], data: DataConfig) -> dict[str, Any]:
    """Re-key the raw ``scale_cuts`` section using data labels rather than redshifts.

    Parameters
    ----------
    scale_cuts: dict[float, Any]
        The raw ``scale_cuts`` section of a config yaml file.
    data: DataConfig
        The resolved ``data`` section.

    Returns
    -------
    scale_cuts: dict[str, Any]
        Re-keyed ``scale_cuts`` section, using data labels instead of redshifts.
    """
    _check_redshift_keys_match(set(scale_cuts), data, "scale_cuts")
    label = dict(zip(data.redshifts, data.labels))
    return {label[z]: bounds for z, bounds in scale_cuts.items()}


def _normalize_sampled_parameters(sampled_parameters: dict[str, Any], data: DataConfig) -> dict[str, Any]:
    """Turn per-bin sampled parameters into ordered list, according to data.redshifts.

    Parameters
    ----------
    sampled_parameters: dict[str, Any]
        The raw ``sampled_parameters`` section of a config yaml file.
    data: DataConfig
        The resolved ``data`` section.

    Returns
    -------
    normalized: dict[str, Any]
        Dictionary containing the sampled parameters arranged in lists for nuisance parameters with
        different priors per redshift.
    """
    normalized = {}
    for name, spec in sampled_parameters.items():
        if isinstance(spec, dict) and "dist" not in spec:
            _check_redshift_keys_match(set(spec), data, f"sampled_parameters.{name}")
            spec = [spec[z] for z in data.redshifts]
        normalized[name] = spec
    return normalized


def _auto_enable_derived_parameters(
    derived_parameters: dict[str, bool],
    fixed_parameters: dict[str, Any],
    sampled_parameters: dict[str, Any],
) -> dict[str, bool]:
    """Extend the raw ``derived_parameters`` section with any auto-detected
    relations whose trigger is present in the fixed or sampled parameters.

    Parameters
    ----------
    derived_parameters: dict[str, bool]
        The raw ``derived_parameters`` section of a config yaml file.
    fixed_parameters: dict[str, Any]
        The raw ``fixed_parameters`` section.
    sampled_parameters: dict[str, Any]
        The resolved ``sampled_parameters`` section.

    Returns
    -------
    derived_parameters: dict[str, bool]
        Updated set of derived parameters after auto-detection.
    """
    present = set(fixed_parameters) | set(sampled_parameters)
    auto_enabled = {
        name: True
        for name, relation in DERIVED_PARAMETERS.items()
        if relation.get("trigger") in present
    }
    return {**auto_enabled, **derived_parameters}


@dataclass
class DataConfig:
    """Container for data setup.

    Attributes
    ----------
    redshifts: list[float]
        Redshift values.
    labels: list[str]
        Corresponding redshift labels, with no trailing zeros.
    bao_labels: list[str]
        Corresponding redshift labels, with trailing zeros.
    datavec_FS_template: str or None
        Full-shape (power-spectrum multipoles) data-vector filename
        template, resolved to an absolute path, or ``None`` if not
        given in the config.
    datavec_BAO_template: str or None
        BAO data-vector filename template, resolved to an absolute
        path, or ``None`` if not given in the config.
    covariance_template: str
        Covariance filename template, resolved to an absolute path -- always
        required.
    mixing_template: str or None
        Mixing-matrix filename template, resolved to an absolute path, or
        ``None`` if not given in the config.
    """

    redshifts: list[float]
    labels: list[str]
    bao_labels: list[str]
    datavec_FS_template: Optional[str]
    datavec_BAO_template: Optional[str]
    covariance_template: str
    mixing_template: Optional[str]

    @classmethod
    def from_dict(cls, data: dict, config_dir: Path) -> DataConfig:
        """Build a `DataConfig` object from the raw ``data`` section of a config yaml file.

        Parameters
        ----------
        data: dict
            The ``data`` section parsed from a config yaml file.
        config_dir: Path
            Directory the config file lives in.

        Returns
        -------
        data_config: DataConfig
        """
        for key in ("redshifts", "covariance"):
            if key not in data:
                raise ValueError(f"'data' section is missing required key '{key}'")

        base_directory = config_dir / data.get("base_directory", ".")
        redshifts = list(data["redshifts"])
        labels = [_redshift_label(z) for z in redshifts]
        bao_labels = [str(z) for z in redshifts]

        return cls(
            redshifts=redshifts,
            labels=labels,
            bao_labels=bao_labels,
            datavec_FS_template=(
                str(base_directory / data["datavec_FS"]) if "datavec_FS" in data else None
            ),
            datavec_BAO_template=(
                str(base_directory / data["datavec_BAO"]) if "datavec_BAO" in data else None
            ),
            covariance_template=str(base_directory / data["covariance"]),
            mixing_template=str(base_directory / data["mixing"]) if "mixing" in data else None,
        )


@dataclass
class RunConfig:
    """Container for full setup, including kind of probe, data,
       scale cuts, priors, sampler, and output settings.

    Attributes
    ----------
    probe: dict[str, Any]
        The raw ``probe`` section of the config yaml file.
    data: DataConfig
        The resolved ``data`` section of the config yaml file.
    scale_cuts: dict[str, Any]
        The ``scale_cuts`` section of the config yaml file, re-keyed from
        redshift value to redshift label.
    sampled_parameters: dict[str, Any]
        The ``sampled_parameters`` section of the config yaml file, processed
        to include per-bin entries.
    fixed_parameters: dict[str, Any]
        The raw ``fixed_parameters`` section of the config yaml file.
    sampler: dict[str, Any]
        The raw ``sampler`` section of the config yaml file.
    output: dict[str, Any]
        The raw ``output`` section of the config yaml file.
    raw_text: str
        The original config yaml file in a string format. Warning: this does not
        track any changes made to the config object after loading.
    constraints: dict[str, bool]
        The raw ``constraints`` section of the config yaml file.
    derived_parameters: dict[str, bool]
        The ``derived_parameters`` section of the config yaml file.
    """

    probe: dict[str, Any]
    data: DataConfig
    scale_cuts: dict[str, Any]
    sampled_parameters: dict[str, Any]
    fixed_parameters: dict[str, Any]
    sampler: dict[str, Any]
    output: dict[str, Any]
    raw_text: str
    constraints: dict[str, bool] = field(default_factory=dict)
    derived_parameters: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> RunConfig:
        """Load a config yaml file and build a ``RunConfig`` object out of it.

        Parameters
        ----------
        path: str
            Path to the config yaml file.

        Returns
        -------
        config: RunConfig
            The resolved ``RunConfig`` object.
        """
        config_path = Path(path).resolve()
        raw_text = config_path.read_text()
        raw = yaml.safe_load(raw_text)

        missing = [key for key in REQUIRED_SECTIONS if key not in raw]
        if missing:
            raise ValueError(
                f"Config '{path}' is missing required section(s): {missing}"
            )

        if "kind" not in raw["probe"]:
            raise ValueError("'probe' section is missing required key 'kind'")
        if "kind" not in raw["sampler"]:
            raise ValueError("'sampler' section is missing required key 'kind'")

        data = DataConfig.from_dict(raw["data"], config_dir=config_path.parent)
        sampled_parameters = _normalize_sampled_parameters(raw["sampled_parameters"], data)
        derived_parameters = _auto_enable_derived_parameters(
            raw.get("derived_parameters", {}), raw["fixed_parameters"], sampled_parameters
        )

        scale_cuts = _parse_scale_cuts(raw["scale_cuts"], data) if "scale_cuts" in raw else {}

        return cls(
            probe=raw["probe"],
            data=data,
            scale_cuts=scale_cuts,
            sampled_parameters=sampled_parameters,
            fixed_parameters=raw["fixed_parameters"],
            sampler=raw["sampler"],
            output=raw["output"],
            raw_text=raw_text,
            constraints=raw.get("constraints", {}),
            derived_parameters=derived_parameters,
        )
