from maimai_py import MaimaiClient

from .maimai_compat import patch_maimai_py_versions


patch_maimai_py_versions()

maimai = MaimaiClient()

__all__ = ["maimai"]
