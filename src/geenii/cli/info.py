import click

from geenii.cli.base import BaseCli
from geenii.config import APP_VERSION


class InfoCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)

        @cli.command(name="info")
        def info():
            """Show general information about Geenii."""
            click.echo("Geenii - A versatile AI agent framework.")
            click.echo(f"Version: {APP_VERSION}")
            click.echo("For more information, visit https://docs.geenii.app")
