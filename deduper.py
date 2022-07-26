import asyncio
import sys
from typing import Optional

import typer

import utils

app = typer.Typer(
    name="deduper",
    add_completion=False,
    help="PA address-object/group/services deduper",
)


@app.command("xml", help="Gather objects/services via XML")
def xml(
    filename: Optional[str] = typer.Option(
        None, "--filename", "-f", prompt="XML FIlename: "
    )
):
    print("XML Time!")

    try:
        with open(filename) as f:
            configstr = f.read()
    except OSError as e:
        print(e)
        print("\nFile open failed...typo?\n")
        sys.exit(1)

    asyncio.run(utils.run(configstr=configstr))


@app.command("panorama", help="Gather objects/services via Panorama")
def panorama(
    panorama: Optional[str] = typer.Option(
        None,
        "--panorama",
        "-i",
        prompt="Panorama IP/FQDN: ",
        help="Panorama IP/FQDN",
        metavar="x.x.x.x",
    ),
    username: Optional[str] = typer.Option(
        None, "--username", "-u", prompt="Panorama Username: "
    ),
    password: Optional[str] = typer.Option(
        None,
        "--password",
        "-p",
        prompt="Panorama Password: ",
        hide_input=True,
    ),
    future: Optional[str] = typer.Option(None),
):

    asyncio.run(utils.run(panorama=panorama, username=username, password=password))


if __name__ == "__main__":
    app()
