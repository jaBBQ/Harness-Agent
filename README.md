# Harness Agent

Python scaffold for a Claw-style agent runtime.

## Structure

```text
cmd/
  claw/
    main.py          # Program entry
internal/
  engine/            # MainLoop core implementation
  provider/          # LLM provider abstraction and SDK implementations
  context/           # Token monitoring and dynamic prompt assembly
  tools/             # Tool registry, middleware hooks, minimal tools
  memory/            # File-system backed memory state
  feishu/            # Feishu bot callback handling
pyproject.toml
README.md
```

## Run

```bash
python main.py "hello"
```

Or after installing the package in editable mode:

```bash
pip install -e .
claw "hello"
```
