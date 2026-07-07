import click


@click.group()
def scheduler():
    """Manage and run scheduler."""
    pass


@scheduler.command(name="start")
def start_scheduler():
    """Start scheduler."""
    click.echo("Starting scheduler...")


@scheduler.command(name="stop")
def stop_scheduler():
    """Stop scheduler."""
    click.echo("Stopping scheduler...")


@scheduler.command(name="status")
def status_scheduler():
    """Show scheduler status."""
    click.echo("Scheduler status: UNKNOWN")