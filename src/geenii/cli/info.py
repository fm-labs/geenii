import click

from geenii.config import APP_VERSION

@click.command(name="info")
def info():
    """Show general information about Geenii."""
    click.echo("Geenii - A versatile AI agent framework.")
    click.echo(f"Version: {APP_VERSION}")
    click.echo("For more information, visit https://docs.geenii.app")
