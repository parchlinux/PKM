# Contributing

## Code of Conduct

Be respectful, inclusive, and constructive. Harassment or
discriminatory behavior will not be tolerated.

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Make your changes
4. Run the application to verify it works
5. Commit with a clear message
6. Push and open a pull request

## Code Style

- Follow PEP 8
- Use descriptive variable names (full words, not abbreviations)
- Wrap user-facing strings with `_()` for i18n
- Keep methods focused and under 50 lines where possible
- Avoid CSS - use Adwaita widgets and built-in style classes


## Architecture

```
main.py          # Entry point (thin)
pkm/
  app.py         # Application class, dependency checks
  window.py      # Main window, UI layout, user interactions
  kernels.py     # Kernel discovery, pacman queries
  terminal_dialog.py  # VTE terminal dialog for install/remove
```

## Testing

There is no test suite yet. Run `python3 main.py` and manually
verify install/remove flows work. A test suite is planned for v0.2.
