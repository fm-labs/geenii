import click

from geenii.ai import enumerate_models
from rich.console import Console
from rich.table import Table

@click.group()
def models():
    pass

@models.command(name="list")
@click.option("-p","--provider")
@click.option("-l","--locality")
def list_models(provider: str, locality: str):
    """List all available models"""

    ai_models = enumerate_models()

    table = Table(title="Models")
    table.add_column("Name", style="cyan")
    table.add_column("Provider")
    table.add_column("Description", justify="right")
    table.add_column("Locality", justify="right")
    table.add_column("Capabilities", justify="right")

    for m in ai_models:
        if provider is not None and provider != m.provider:
           continue
        if locality is not None and locality != m.locality:
            continue

        table.add_row(m.name, m.provider, m.description, m.locality, ",".join(m.capabilities))
    Console().print(table)