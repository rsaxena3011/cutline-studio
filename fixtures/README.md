# fixtures

Cached bundles for fixture mode, the default demo path: per comparison job, the two scene ledgers, the brief, the color targets the fixture engine segments from, and the cached judgments, stored next to the stills they belong to. Masks are not cached; the color-key engine computes them from the real pixels on every run. Fixture mode exists so a demo or a review never depends on a live API call. Live mode is one toggle; a failed live call returns a REVIEW, it does not fall back to these bundles.
