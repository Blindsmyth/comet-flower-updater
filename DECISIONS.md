# Project Decisions

## CLI Framework: Click
- **Decision:** Used `click` instead of `typer`.
- **Rationale:** `click` is well-established, has fewer dependencies, and is more than sufficient for the required "inspect" and "dump" commands. It's also highly idiomatic for Python CLIs.

## Package Layout: src/
- **Decision:** Adopted the `src/` layout.
- **Rationale:** Prevents accidental imports of the local package and ensures that tests run against the installed version (installed in editable mode).

## Parser: Manual struct-based
- **Decision:** Implemented a manual parser using the `struct` module instead of a declarative library like `construct`.
- **Rationale:** Keeps the core library dependencies minimal (zero non-standard dependencies for the parser) as requested. `construct` is powerful but was deemed unnecessary for the relatively simple ZDLF structure at this stage.

## Python Version: 3.10+
- **Decision:** Targeted Python 3.10 instead of 3.11.
- **Rationale:** The current development environment is running Python 3.10.6. No 3.11-specific features were required for the MVP.

## Block Parsing: 16-byte Footer
- **Decision:** The parser stops 16 bytes before the end of the file.
- **Rationale:** Empirical evidence and prior art suggest a 16-byte non-block footer. Stopping early prevents the parser from misinterpreting the footer as a new block tag with an invalid length.
