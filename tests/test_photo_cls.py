import numpy as np
import pytest

pytest.importorskip("cloelike")

from cloechain.probes.photo_cls import _block_sizes, _select_covariance  # noqa: E402


def _labelled_covariance(sizes):
    """Diagonal covariance whose entries tell which block they belong to."""
    labels = {"WL": 1.0, "GGL": 2.0, "GCph": 3.0}
    return np.diag(
        np.concatenate([np.full(sizes[b], labels[b]) for b in ("WL", "GGL", "GCph")])
    )


def test_block_sizes():
    assert _block_sizes(n_pos=6, n_she=6, n_ell=32) == {
        "WL": 21 * 32,
        "GGL": 36 * 32,
        "GCph": 21 * 32,
    }


@pytest.mark.parametrize(
    "kind, blocks",
    [
        ("3x2pt", [1.0, 2.0, 3.0]),
        ("WL", [1.0]),
        ("GGL", [2.0]),
        ("GCph", [3.0]),
        ("2x2pt", [2.0, 3.0]),
    ],
)
def test_select_covariance_from_full_3x2pt(kind, blocks):
    sizes = _block_sizes(n_pos=3, n_she=2, n_ell=4)
    selected = _select_covariance(_labelled_covariance(sizes), kind, sizes)
    assert list(dict.fromkeys(np.diag(selected))) == blocks


def test_select_covariance_of_the_probe_only():
    sizes = _block_sizes(n_pos=3, n_she=2, n_ell=4)
    covariance = np.eye(sizes["WL"])
    assert _select_covariance(covariance, "WL", sizes) is covariance


def test_select_covariance_wrong_size():
    sizes = _block_sizes(n_pos=3, n_she=2, n_ell=4)
    with pytest.raises(ValueError, match="matches neither"):
        _select_covariance(np.eye(5), "WL", sizes)
