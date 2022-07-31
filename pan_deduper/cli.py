import asyncio
import platform
import sys
from typing import Optional

import typer

from pan_deduper.utils import run_deduper

app = typer.Typer(
    name="deduper",
    add_completion=False,
    help="PA address-object/group/services deduper",
)

# friggin windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@app.command("xml", help="Gather objects/services via XML")
def xml(
    filename: Optional[str] = typer.Option(
        None, "--filename", "-f", prompt="XML FIlename: ",
    ),
    deep: bool = typer.Option(
        None,
        "--deep",
        "-d",
    )

):
    print("\n\tXML Time!\n")

    try:
        with open(filename) as f:
            configstr = f.read()
    except OSError as e:
        print(e)
        print("\nFile open failed...typo?\n")
        sys.exit(1)

    asyncio.run(run_deduper(configstr=configstr, deep=deep))


@app.command("panorama", help="Gather objects/services via Panorama")
def panorama(
    panorama_ip: Optional[str] = typer.Option(
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
    deep: bool = typer.Option(
        None,
        "--deep",
        "-d",
    )
):
    print("\n\tPanorama Time!\n")
    asyncio.run(run_deduper(panorama=panorama_ip, username=username, password=password, deep=deep))


if __name__ == "__main__":
    app()
