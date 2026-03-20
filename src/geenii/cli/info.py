import click

from geenii.config import APP_VERSION
from geenii.g import get_app_info


@click.command(name="info")
def info():
    """Show general information about Geenii."""
    click.echo("Geenii - A versatile AI agent framework.")
    click.echo(f"Version: {APP_VERSION}")
    click.echo("For more information, visit https://docs.geenii.app")

    app_info = get_app_info()
    flat_info = flatten_dict(app_info)
    click.echo("\nDetailed Information:")
    for key, value in flat_info.items():
        click.echo(f"{key}: {value}")


def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(flatten_dict(item, f"{new_key}{sep}{i}", sep=sep).items())
                else:
                    items.append((f"{parent_key}{sep}{i}", item))
        else:
            items.append((new_key, v))
    return dict(items)
