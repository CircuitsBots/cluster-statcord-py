from collections import namedtuple


__title__ = "cluster-statcord-py"
__author__ = "CircuitSacul"
__license__ = "MIT"
__version__ = "1.0.1"

name = "cluster_statcord"

VersionInfo = namedtuple(
    "VersionInfo", "major minor micro releaselevel serial"
)
version_info = VersionInfo(
    major=3, minor=0, micro=7, releaselevel="final", serial=0
)
