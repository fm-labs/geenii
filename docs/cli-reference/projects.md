# geenii projects

List the projects configured in the `projects` section of the user settings.

## Synopsis

```
geenii projects <command>
```

## Commands

### list

```
geenii projects list
```

List the configured project directories as a table: path (resolved), whether
the project is trusted, whether the directory exists, and a `*` for the project
containing the current working directory (`GEENII_WORKING_DIR`). Entries that
are not absolute paths are skipped with a warning.

## See Also

- [Configuration](../user-guide/configuration.md) — the `projects` settings key
