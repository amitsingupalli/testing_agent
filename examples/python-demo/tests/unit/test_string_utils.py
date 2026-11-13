# One hand-written test so the demo starts partially covered:
# `slugify` will show as tested, the rest appear in the gap manifest.

import string_utils


def test_slugify_basic():
    assert string_utils.slugify("Hello, World!") == "hello-world"
