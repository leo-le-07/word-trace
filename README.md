# Word Trace

Letter-tracing worksheets for A4. Drop images named after their word into
`~/Documents/WordTrace/input/`, then:

    uv run wordtrace

One page per image, one timestamped PDF in `output/`, sources moved to
`processed/`. Tune the layout with `uv run wordtrace --preview`.
Optional `~/.wordtrace.toml`: `home = "/path/to/WordTrace"`.
