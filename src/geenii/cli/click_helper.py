import click

def click_success(message: str):
    click.secho(message, fg="green")

def click_error(message: str):
    click.secho(message, fg="red")

def click_warning(message: str):
    click.secho(message, fg="yellow")

def click_info(message: str):
    click.secho(message, fg="blue")
