import click
from api import Ceramic
import json
from dids import dids

# A dids.py containin at least some did is required
# dids = {
#     "dummy": {
#         "did": "did:key:<did>",
#         "seed": "<did_seed>"
#     }
# }

def write_file(data, path):
    """Write data to file"""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

def read_file(path):
    """Read data from file"""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)

@click.group()
def cli():
    """Ceramic cli."""
    pass


@cli.command()
@click.argument("stream_id")
@click.option("--file", default=None, help="Path to the output file")
def read(stream_id, file):
    """Read a stream"""
    api = Ceramic()
    data, _, _ = api.get_data(stream_id)
    if file:
        write_file(data, file)
    click.echo(f"Read stream {stream_id}:\n{json.dumps(data, indent=4)}")


@cli.command()
@click.argument("file")
@click.argument("did_name")
def create(file, did_name):
    """Create a new stream from file"""
    api = Ceramic()
    data = read_file(file)
    did = dids.get(did_name, {})
    stream_id = api.create_stream(did.get("did", ""), did.get("seed", ""), data)
    click.echo(f"Created stream {stream_id}")


@cli.command()
@click.argument("stream_id")
@click.argument("file")
@click.argument("did_name")
def update(stream_id, file, did_name):
    """Update a stream from file."""
    api = Ceramic()
    new_data = read_file(file)
    did = dids.get(did_name, {})
    api.update_stream(did.get("did", ""), did.get("seed", ""), stream_id, new_data)
    click.echo("Updated stream")


if __name__ == "__main__":
    cli()