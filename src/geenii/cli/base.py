import click

class BaseCli:

    def __init__(self, cli: click.core.Group):
        self.cli = cli

    def success(self, message: str):
        click.secho(message, fg="green")

    def error(self, message: str):
        click.secho(message, fg="red")

    def warning(self, message: str):
        click.secho(message, fg="yellow")

    def info(self, message: str):
        click.secho(message, fg="blue")
