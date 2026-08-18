"""Claim Intelligence package.

The package preserves the public API of the former
app.intelligence.claims module while organizing Claim Intelligence
behind explicit responsibility boundaries.
"""

from .repository import *
from .repository import _claim_link_identity