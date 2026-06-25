"""Allow ``python -m forensics`` to invoke the CLI."""

from .cli import main

raise SystemExit(main())
