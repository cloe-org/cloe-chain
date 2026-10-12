"""Main module to run a sampler from a config file or an in-memory config object."""

from __future__ import annotations

import numpy as np

from cloechain.chain import Chain
from cloechain.config import RunConfig
from cloechain.parameters import build_parameter_dict_for_loglike
from cloechain.priors import build_priors
from cloechain.templates import expand_bin_templates
from cloechain.versions import write_config_with_versions
from cloechain.loader import load_constraint, load_derived_parameter, load_probe, load_sampler


def run_from_config(path: str) -> Chain:
    """Run the sampler described by the input config yaml file.

    Parameters
    ----------
    path: str
        Path to the config yaml file.

    Returns
    -------
    chain: Chain
        The sampled chain, already saved to the output directory
        specified in the config file.
    """
    return run(RunConfig.from_yaml(path))


def run(config: RunConfig) -> Chain:
    """Run the sampler described by a pre-loaded `RunConfig` object.

    Parameters
    ----------
    config: RunConfig
        An pre-loaded running configuration.

    Returns
    -------
    chain: Chain
        The sampled chain, which is additionally saved to the output
        directory specified in the config file.
    """
    probe = load_probe(config.probe["kind"])
    likelihood = probe.build_likelihood(config)
    obs_labels = probe.obs_labels(config)
    vector_parameter_names = probe.vector_parameter_names(likelihood)

    fixed_parameters = config.fixed_parameters
    sampled_parameters = config.sampled_parameters
    # Probes with one scalar parameter per bin expand the '{i}' templates.
    if hasattr(probe, "parameter_names"):
        names = probe.parameter_names(likelihood)
        fixed_parameters = expand_bin_templates(fixed_parameters, names, "fixed_parameters")
        sampled_parameters = expand_bin_templates(
            sampled_parameters, names, "sampled_parameters"
        )
    if getattr(config.data, "noise_free_mock", False):
        probe.use_noise_free_mock(likelihood, fixed_parameters)

    priors = build_priors(sampled_parameters, obs_labels, vector_parameter_names)

    active_derived_parameters = [
        load_derived_parameter(name)
        for name, enabled in config.derived_parameters.items()
        if enabled
    ]
    active_constraints = [
        load_constraint(name) for name, enabled in config.constraints.items() if enabled
    ]

    def loglike_fn(flat_sample: dict[str, float]) -> float:
        parameters = build_parameter_dict_for_loglike(
            flat_sample, priors.layout, fixed_parameters
        )
        for derive in active_derived_parameters:
            derive(parameters)
        if not all(constraint(parameters) for constraint in active_constraints):
            return -np.inf
        try:
            return probe.loglike(likelihood, parameters)
        except (ValueError, RuntimeError):
            return -np.inf

    sampler_module = load_sampler(config.sampler["kind"])
    points, logweight, loglikelihood = sampler_module.run(
        loglike_fn,
        priors,
        config.sampler.get("settings", {}),
        run_settings=config.sampler.get("run_settings", {}),
    )

    chain = Chain.build(priors, points, logweight, loglikelihood)
    chain.save(config.output["directory"], config.output["name"])
    write_config_with_versions(
        config.raw_text,
        config.output["directory"],
        config.output["name"],
        extra_packages=[*probe.tracked_packages(config), *sampler_module.TRACKED_PACKAGES],
    )
    return chain
