# Contributing to geenii

Thanks for your interest in improving geenii! Bug reports, feature ideas,
documentation fixes and code contributions are all welcome.

## Before you start

- **Bugs and feature requests:** open an issue at
  <https://github.com/fm-labs/geenii/issues>. For bugs, include the geenii
  version (`geenii info`), your OS, the provider/model in use and steps to
  reproduce.
- **Larger changes:** please open an issue to discuss the idea first, so we can
  agree on the approach before you invest time in a pull request.
- **Security issues:** do not open a public issue. Contact the maintainers
  privately via the contact address listed on the GitHub profile of
  [fm-labs](https://github.com/fm-labs).

## Development setup

```bash
uv sync --group dev
uv run geenii info
```

See [DEVELOPER.md](DEVELOPER.md) and the [developer guide](docs/developer-guide/)
for architecture, the web server and Docker builds.

## Pull requests

1. Fork the repository and create a branch from `main`.
2. Keep changes focused: one fix or feature per pull request.
3. Add or update tests for behavior you change.
4. Make sure the checks pass locally — CI runs the same:

   ```bash
   uv run ruff check .
   uv run pytest tests/ -v
   ```

5. Update the docs in `docs/` if you change commands, options or behavior.
6. Describe **what** changed and **why** in the pull request, and link the
   related issue.
7. Confirm the Contributor License Agreement (see below) in the pull request
   description.

## License

geenii is licensed under the
[GNU General Public License v3.0 or later](LICENSE). geenii is also offered
under separate commercial license terms by fm-labs (dual licensing).

## Contributor License Agreement (CLA)

Because geenii is dual-licensed, we need the right to distribute every
contribution under both the GPL and the commercial license. Therefore every
contribution must be made under the following agreement. You keep the
copyright in your contribution; you only grant fm-labs the license below.

**By submitting a contribution (code, documentation or other material) to this
project, you agree to the following terms:**

1. **Definitions.** "You" means the individual or legal entity submitting the
   contribution. "Contribution" means any work you submit to the geenii
   project, for example via pull request, patch or issue. "fm-labs" means the
   maintainer and copyright holder of the geenii project.

2. **Copyright license.** You grant fm-labs and recipients of software
   distributed by fm-labs a perpetual, worldwide, non-exclusive, no-charge,
   royalty-free, irrevocable license to reproduce, prepare derivative works
   of, publicly display, publicly perform, sublicense and distribute your
   contribution and such derivative works. This includes the right for
   fm-labs to license your contribution under the GNU General Public License
   and under any other license terms, including proprietary and commercial
   license terms.

3. **Patent license.** You grant fm-labs and recipients of software
   distributed by fm-labs a perpetual, worldwide, non-exclusive, no-charge,
   royalty-free, irrevocable patent license to make, have made, use, offer to
   sell, sell, import and otherwise transfer your contribution, where such
   license applies only to patent claims licensable by you that are
   necessarily infringed by your contribution alone or by its combination
   with the project.

4. **Your representations.** You represent that:
   - the contribution is your original work, or you have the right to submit
     it under these terms;
   - if your employer has rights to intellectual property you create, you
     have received permission to make the contribution on behalf of that
     employer, or your employer has waived such rights;
   - you will clearly identify any third-party material included in your
     contribution, together with its license.

5. **No obligation.** fm-labs is not required to use your contribution.
   Except as stated above, the contribution is provided "as is", without
   warranties or conditions of any kind.

**How to confirm:** include the following line in the description of your
pull request:

```
I have read and agree to the Contributor License Agreement in CONTRIBUTING.md.
```

Pull requests without this confirmation cannot be merged.

## Trademarks

The name "geenii" and related logos are trademarks of fm-labs. See
[TRADEMARKS.md](TRADEMARKS.md) for how they may be used.
